"""Bounded traversal with actual synthetic Codex subprocesses and saved resume."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
WALKER = ROOT / "skills/project-improvement-agent/scripts/walk_history.py"
PEER = ROOT / "tests/walk_peer.py"


class WalkTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name).resolve()
        self.output = self.root / "private"
        self.plan = self.root / "plan.json"
        self.log = self.root / "peer.jsonl"
        executable = self.root / "codex"
        executable.write_text("#!" + sys.executable + "\nimport runpy\nrunpy.run_path("
                              + repr(str(PEER)) + ", run_name='__main__')\n", encoding="utf-8")
        executable.chmod(0o700)
        self.env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ["PATH"], PIA_WALK_LOG=str(self.log))

    def invoke(self, expected=0, mode="normal", probes=512, resume=False, inject=None, allow_finalization=False, **options):
        if resume:
            args = ["--resume", str(self.output)]
        else:
            plan = {"schema_version": 1, "thread_id": "walk-test", "through_turn_id": "two", "max_probes": 24,
                    "max_bytes": 4194304, "max_seconds": 30, "max_records": 100, **options}
            self.plan.write_text(json.dumps(plan), encoding="utf-8")
            args = ["--plan", str(self.plan), "--output", str(self.output)]
        launcher = [str(WALKER)]
        if inject is not None:
            launcher = ["-c", "import sys, time\n"
                        + "sys.path.insert(0, " + repr(str(WALKER.parent)) + ")\n"
                        + "import walk_history as walker\n" + inject + "\n"
                        + "raise SystemExit(walker.main(sys.argv[1:]))"]
        result = subprocess.run([sys.executable, "-B", *launcher, *args, "--max-probes-this-run", str(probes)],
                                capture_output=True, text=True, env=dict(self.env, PIA_WALK_MODE=mode), timeout=12)
        report = json.loads(result.stdout)
        code = result.returncode
        if expected == 0 and allow_finalization and code == 1 and "finalization_witness" in report:
            verified = self.verify_capture(report)
            report.update(coverage_status=verified["coverage_status"], derived_verification=verified)
            code = 0
        self.assertEqual(code, expected, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertNotIn("PRIVATE_", result.stdout)
        self.assertNotIn("one-next", result.stdout)
        self.assertEqual(report["snapshot_consistency"], "unverified")
        self.assertEqual(report["mutation_check"], "turn_inventory_only")
        return report

    def state(self):
        return json.loads((self.output / "state.json").read_bytes())

    def transcript(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def assert_private_receipts(self):
        state = self.state()
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
        for file in self.output.rglob("*"):
            if file.is_file():
                self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600)
                self.assertNotIn(b"PRIVATE_", file.read_bytes())
        for entry in state["journal"]:
            if entry["kind"] != "probe":
                continue
            folder = self.output / entry["slot"]
            receipt = json.loads((folder / "receipt.json").read_bytes())
            self.assertTrue(receipt["cleanup"]["group_gone"])
            self.assertTrue(receipt["cleanup"]["reaped"])
            with self.assertRaises(ProcessLookupError):
                os.kill(receipt["cleanup"]["pid"], 0)
            for name in ("records", "receipt"):
                self.assertEqual(hashlib.sha256((folder / (name + ".json")).read_bytes()).hexdigest(),
                                 entry[name + "_sha256"])

    def test_orderly_resume_checks_inventory_and_finishes_original_cursor(self):
        first = self.invoke(probes=2)
        self.assertEqual(first["coverage_status"], "partial")
        self.assertEqual(first["usage"]["probes"], 2)
        self.assertEqual(self.state()["coverage"]["item_cursor"], "one-next")
        boundary = len(self.transcript())
        complete = self.invoke(resume=True)
        self.assertEqual(complete["coverage_status"], "complete_observed")
        self.assertEqual(complete["usage"]["probes"], 6)
        self.assertEqual(complete["usage"]["source_list_calls"], 6)
        self.assertEqual(complete["usage"]["initialize_calls"], 6)
        self.assertEqual(complete["usage"]["selected_items"], 3)
        self.assertEqual(complete["usage"]["user_items"], 2)
        self.assertEqual(complete["usage"]["nonuser_items"], 1)
        transcript = self.transcript()
        self.assertTrue(all(row["argv"] == ["app-server", "--stdio"] for row in transcript if "pid" in row))
        resumed = [row for row in transcript[boundary:] if row.get("method", "").startswith("thread/")]
        self.assertEqual(resumed[0]["method"], "thread/turns/list")
        self.assertEqual(resumed[1]["params"]["cursor"], "one-next")
        self.assertFalse(any(row.get("params", {}).get("turnId") == "after" for row in transcript))
        self.assertEqual([row["turn_id"] for row in self.state()["coverage"]["closed_item_scopes"]], ["one", "two"])
        self.assertEqual(json.loads((self.output / "probe-0002/records.json").read_bytes())[0]["text_parts"],
                         ["Exact π 🌱\n  "])
        self.assert_private_receipts()

    def test_complete_digest_tracks_projection_and_survives_resume(self):
        self.invoke(probes=2)
        self.assertIsNone(self.state()["coverage"]["observation_sha256"])
        self.invoke(resume=True)
        resumed = self.state()["coverage"]["observation_sha256"]

        self.output = self.root / "fresh"
        self.invoke()
        self.assertRegex(resumed, r"^[a-f0-9]{64}$")
        self.assertEqual(resumed, self.state()["coverage"]["observation_sha256"])

        self.output = self.root / "changed-item"
        self.invoke(mode="assistant")
        self.assertNotEqual(resumed, self.state()["coverage"]["observation_sha256"])

    def test_resume_mid_inventory_revalidates_before_items(self):
        first = self.invoke(mode="long_inventory", probes=1)
        self.assertEqual(first["usage"]["source_list_calls"], 1)
        self.assertEqual(self.state()["coverage"]["inventory_cursor"], "inventory-20")
        boundary = len(self.transcript())
        second = self.invoke(mode="long_inventory", resume=True, probes=4)
        self.assertEqual(second["coverage_status"], "partial")
        resumed = [row for row in self.transcript()[boundary:] if row.get("method", "").startswith("thread/")]
        self.assertEqual([row["method"] for row in resumed], ["thread/turns/list"] * 3 + ["thread/items/list"])
        self.assertEqual([row["params"].get("cursor") for row in resumed[:3]],
                         ["inventory-20", None, "inventory-20"])
        self.assertEqual(resumed[3]["params"]["turnId"], "older-0")
        self.assert_private_receipts()

    def test_changed_cutoff_reuses_saved_method_without_reading_excluded_turn(self):
        result = self.invoke(through_turn_id="one")
        self.assertEqual(result["coverage_status"], "complete_observed")
        self.assertEqual([row["turn_id"] for row in self.state()["coverage"]["observed_inventory"]], ["one"])
        self.assertFalse(any(row.get("params", {}).get("turnId") == "two" for row in self.transcript()))
        self.assert_private_receipts()

    def test_term_during_actual_probe_preserves_boundary_and_reaps(self):
        plan = {"schema_version": 1, "thread_id": "walk-test", "through_turn_id": "two",
                "max_probes": 10, "max_bytes": 4194304, "max_seconds": 30, "max_records": 100}
        self.plan.write_text(json.dumps(plan), encoding="utf-8")
        process = subprocess.Popen([sys.executable, "-B", str(WALKER), "--plan", str(self.plan),
                                    "--output", str(self.output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, env=dict(self.env, PIA_WALK_MODE="pending"))
        try:
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                if self.log.exists() and '"method": "thread/items/list"' in self.log.read_text():
                    break
                time.sleep(0.03)
            else:
                self.fail("Item probe did not start")
            self.assertIsNotNone(self.state()["pending"])
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=6)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(stderr, "")
        report = json.loads(stdout)
        self.assertEqual(report["coverage_status"], "partial")
        self.assertEqual(report["usage"]["probes"], 2)
        self.assertEqual(report["usage"]["failed_probes"], 1)
        self.assertIsNone(self.state()["coverage"]["item_cursor"])
        self.assertIsNone(self.state()["pending"])
        self.assert_private_receipts()

    def test_precondition_refusal_never_launches(self):
        for options in ({"max_records": True}, {"max_probes": 1025}, {"max_bytes": 536870913},
                        {"max_seconds": 1.5}, {"through_turn_id": None}, {"page_strategy": "unsafe"},
                        {"operation": "thread/start"}):
            with self.subTest(options=options):
                self.assertEqual(self.invoke(expected=2, **options)["coverage_status"], "error")
                self.assertFalse(self.log.exists())
                self.assertFalse(self.output.exists())

    def test_retry_is_only_preauthorized_at_same_byte_boundary(self):
        blocked = self.invoke(expected=1, mode="fallback")
        self.assertEqual(blocked["reason"], "byte_limit")
        self.assertEqual(blocked["usage"]["failed_probes"], 1)
        self.output = self.root / "adaptive"
        self.log.unlink()
        passed = self.invoke(mode="fallback", page_strategy="standard_then_single_then_large")
        self.assertEqual(passed["coverage_status"], "complete_observed")
        self.assertEqual(passed["usage"]["failed_probes"], 2)
        requests = [row["params"] for row in self.transcript() if row.get("method") == "thread/items/list"]
        self.assertEqual([row["limit"] for row in requests[:3]], [20, 1, 1])
        self.assertTrue(all(row["turnId"] == "one" and "cursor" not in row for row in requests[:3]))
        self.assertEqual(requests[3]["cursor"], "one-next")
        self.assert_private_receipts()

    def test_recovered_single_item_size_survives_resume_until_turn_end(self):
        for mode, expected_failures in (("batch_halve", 1), ("fallback", 2)):
            with self.subTest(mode=mode):
                self.output = self.root / mode
                self.log.unlink(missing_ok=True)
                first = self.invoke(mode=mode, probes=2 + expected_failures,
                                    page_strategy="standard_then_single_then_large")
                self.assertEqual(first["coverage_status"], "partial")
                self.assertEqual(first["usage"]["failed_probes"], expected_failures)
                self.assertEqual(self.state()["coverage"]["item_cursor"], "one-next")
                boundary = len(self.transcript())
                result = self.invoke(mode=mode, resume=True)
                self.assertEqual(result["coverage_status"], "complete_observed")
                requests = [row["params"] for row in self.transcript()[boundary:]
                            if row.get("method") == "thread/items/list"]
                self.assertEqual([(p["turnId"], p.get("cursor"), p["limit"]) for p in requests],
                                 [("one", "one-next", 1), ("two", None, 20)])
                for entry in self.state()["journal"]:
                    if entry["kind"] == "probe":
                        receipt = json.loads((self.output / entry["slot"] / "receipt.json").read_bytes())
                        if receipt["plan"]["cursor"] == "one-next":
                            self.assertEqual(receipt["plan"]["read_mode"], "standard")
                            self.assertEqual(receipt["plan"]["max_bytes"], 131072)
                self.assertEqual(result["usage"]["selected_items"], 2)
                self.assertEqual(result["usage"]["user_items"], 1)

    def test_large_batch_halves_same_cursor_across_resume_then_resets(self):
        first = self.invoke(mode="batch_halve", probes=3, max_bytes=32 * 1024 * 1024,
                            page_strategy="bounded_large_pages")
        self.assertEqual(first["coverage_status"], "partial")
        self.assertEqual(first["usage"]["failed_probes"], 2)
        self.assertEqual(self.state()["coverage"]["item_batch_limit"], 5)
        self.assertIsNone(self.state()["coverage"]["item_cursor"])
        final = self.invoke(mode="batch_halve", resume=True)
        self.assertEqual(final["coverage_status"], "complete_observed")
        self.assertEqual(final["usage"]["failed_probes"], 4)
        self.assertEqual(final["usage"]["selected_items"], 2)
        item_requests = [row["params"] for row in self.transcript() if row.get("method") == "thread/items/list"]
        self.assertEqual([row["limit"] for row in item_requests], [20, 10, 5, 2, 1, 20, 20])
        self.assertTrue(all(row["turnId"] == "one" and "cursor" not in row for row in item_requests[:5]))
        self.assertEqual(item_requests[5]["cursor"], "one-next")
        for entry in self.state()["journal"]:
            if entry["kind"] == "probe":
                receipt = json.loads((self.output / entry["slot"] / "receipt.json").read_bytes())
                is_item = receipt["plan"]["operation"] == "items"
                self.assertEqual(receipt["plan"]["read_mode"], "large_batch_page" if is_item else "standard")
                self.assertEqual(receipt["plan"]["max_bytes"], 4194304 if is_item else 131072)
        self.assert_private_receipts()

    def test_large_batch_stops_at_unaccepted_single_item(self):
        result = self.invoke(expected=1, mode="batch_single_overcap", max_bytes=32 * 1024 * 1024,
                             page_strategy="bounded_large_pages")
        self.assertEqual(result["coverage_status"], "partial")
        self.assertEqual(result["reason"], "byte_limit")
        self.assertEqual(result["usage"]["probes"], 6)
        self.assertEqual(result["usage"]["failed_probes"], 5)
        self.assertEqual(result["usage"]["selected_items"], 0)
        self.assertIsNone(self.state()["coverage"]["item_cursor"])
        self.assertEqual(self.state()["coverage"]["closed_item_scopes"], [])
        self.assertEqual([row["params"]["limit"] for row in self.transcript()
                          if row.get("method") == "thread/items/list"], [20, 10, 5, 2, 1])
        self.assert_private_receipts()

    def test_invalid_or_mutating_scope_never_completes(self):
        for mode, reason, options in (
            ("active", "nonterminal_selected_turn", {}),
            ("missing_cutoff", "cutoff_missing", {"through_turn_id": "missing"}),
            ("item_duplicate", "duplicate_or_wrong_item", {}),
            ("cycle", "cursor_no_progress", {}),
            ("final_changed", "selected_inventory_changed", {}),
        ):
            with self.subTest(mode=mode, reason=reason):
                self.output = self.root / reason
                self.log.unlink(missing_ok=True)
                result = self.invoke(expected=1, mode=mode, **options)
                self.assertEqual(result["coverage_status"], "partial")
                self.assertEqual(result["reason"], reason)
                self.assert_private_receipts()

    def test_changed_inventory_stops_resume_before_items(self):
        self.invoke(probes=2)
        boundary = len(self.transcript())
        resumed = self.invoke(expected=1, resume=True, mode="changed")
        self.assertEqual(resumed["reason"], "selected_inventory_changed")
        self.assertFalse(any(row.get("method") == "thread/items/list" for row in self.transcript()[boundary:]))

    def test_saved_budget_does_not_reset(self):
        first = self.invoke(probes=2, max_probes=3)
        self.assertEqual(first["usage"]["probes"], 2)
        second = self.invoke(resume=True)
        self.assertEqual(second["reason"], "probe_limit")
        self.assertEqual(second["usage"]["probes"], 3)
        boundary = len(self.transcript())
        third = self.invoke(resume=True)["usage"]
        for name in ("probes", "received_bytes", "accepted_records", "reader_elapsed_us"):
            self.assertEqual(third[name], second["usage"][name])
        self.assertGreater(third["orchestration_elapsed_us"], second["usage"]["orchestration_elapsed_us"])
        self.assertEqual(len(self.transcript()), boundary)

    def test_predispatch_persistence_time_counts_and_prevents_launch(self):
        report = self.invoke(max_seconds=4, inject="""
publish = walker.publish
def slow_publish(directory, name, raw, replace=False):
    if name == "state.json" and b'"probe_pending"' in raw:
        time.sleep(0.6)
    return publish(directory, name, raw, replace)
walker.publish = slow_publish
""")
        self.assertEqual(report["reason"], "insufficient_time_after_predispatch")
        self.assertEqual(report["usage"]["probes"], 0)
        self.assertGreaterEqual(report["usage"]["orchestration_elapsed_us"], 600_000)
        self.assertIsNone(self.state()["pending"])
        self.assertFalse(self.log.exists())

    def test_resume_persistence_and_replay_charge_without_extra_source_reads(self):
        first = self.invoke(probes=1, max_probes=1)
        boundary = len(self.transcript())
        resumed = self.invoke(resume=True, inject="""
replay = walker.replay
def slow_replay(*args):
    time.sleep(0.35)
    return replay(*args)
walker.replay = slow_replay
""")
        self.assertEqual(resumed["reason"], "probe_limit")
        self.assertEqual(len(self.transcript()), boundary)
        first_usage, usage = first["usage"], resumed["usage"]
        self.assertGreaterEqual(usage["orchestration_elapsed_us"] - first_usage["orchestration_elapsed_us"], 350_000)
        self.assertEqual(usage["elapsed_us"], usage["reader_elapsed_us"] + usage["orchestration_elapsed_us"]
                         + usage["finalization_reserve_us"])

    def test_closing_overrun_retains_uncertainty_and_actual_time(self):
        report = self.invoke(expected=1, max_seconds=1, inject="""
publish = walker.publish
def slow_publish(directory, name, raw, replace=False):
    if name == "state.json" and b'"reason":"wall_limit"' in raw:
        time.sleep(1.05)
    return publish(directory, name, raw, replace)
walker.publish = slow_publish
""")
        self.assertEqual(report["coverage_status"], "partial")
        self.assertEqual(report["reason"], "elapsed_accounting_exceeded")
        self.assertGreater(report["usage"]["elapsed_us"], 1_000_000)
        self.assertGreaterEqual(report["measured_elapsed_us_before_summary"], report["usage"]["elapsed_us"])
        self.assertTrue((self.output / ".invocation").is_file())
        self.assertEqual(self.state()["coverage_status"], "partial")
        self.assertEqual(self.invoke(expected=2, resume=True)["reason"], "uncertain_previous_invocation")
        self.assertFalse(self.log.exists())

    def test_amended_ceiling_keeps_explicit_512_budget(self):
        result = self.invoke(max_probes=512, probes=1, inject="""
next_plan = walker.Progress.next_plan
def at_512(self):
    before = self.used["probes"]
    self.used["probes"] = 512
    try:
        return next_plan(self)
    finally:
        self.used["probes"] = before
walker.Progress.next_plan = at_512
""")
        self.assertEqual(result["reason"], "probe_limit")
        self.assertFalse(self.log.exists())
        self.output = self.root / "amended"
        self.assertEqual(self.invoke(max_probes=1024, probes=1)["usage"]["probes"], 1)

    def test_explicit_byte_ceiling_preserves_chosen_128_mib_limit(self):
        result = self.invoke(max_bytes=134217728, probes=1, inject="""
next_plan = walker.Progress.next_plan
def at_old_limit(self):
    before = self.used["received_bytes"]
    self.used["received_bytes"] = 134217728
    try:
        return next_plan(self)
    finally:
        self.used["received_bytes"] = before
walker.Progress.next_plan = at_old_limit
""")
        self.assertEqual(result["reason"], "byte_limit")
        self.assertFalse(self.log.exists())
        self.assertEqual(self.state()["plan"]["max_bytes"], 134217728)
        self.output = self.root / "amended-bytes"
        self.assertEqual(self.invoke(max_bytes=536870912, probes=1)["usage"]["probes"], 1)
        self.assertEqual(self.state()["plan"]["max_bytes"], 536870912)
        receipt = json.loads((self.output / "probe-0001/receipt.json").read_bytes())
        self.assertEqual(receipt["plan"]["max_bytes"], 131072)
        self.assert_private_receipts()

    def test_walker_keeps_assistant_rows_minimized(self):
        report = self.invoke(mode="assistant")
        self.assertEqual(report["coverage_status"], "complete_observed")
        first_page = self.output / "probe-0002"
        records = json.loads((first_page / "records.json").read_bytes())
        assistant = records[1]
        self.assertEqual(assistant["type"], "agentMessage")
        self.assertEqual(assistant["role"], "assistant")
        self.assertIn("serialized_item_sha256", assistant)
        self.assertNotIn("assistant_text", assistant)
        self.assertNotIn("assistant_phase", assistant)
        self.assertNotIn("assistant_text_selection", json.loads((first_page / "receipt.json").read_bytes())["plan"])
        self.assert_private_receipts()

    def test_range_selects_only_after_anchor_and_has_distinct_digest(self):
        result = self.invoke(mode="range", after_turn_id="one", allow_finalization=True)
        self.assertEqual(result["coverage_status"], "complete_observed")
        state = self.state()["coverage"]
        self.assertEqual([row["turn_id"] for row in state["observed_inventory"]], ["two"])
        self.assertEqual([row["turn_id"] for row in state["closed_item_scopes"]], ["two"])
        self.assertEqual(state["observed_anchor"]["turn_id"], "one")
        self.assertEqual(state["earlier_item_coverage"], "excluded")
        self.assertEqual(result["range"], {"after_turn_id": "one", "through_turn_id": "two",
                                          "start_exclusive": True, "end_inclusive": True})
        self.assertEqual([row["params"]["turnId"] for row in self.transcript()
                          if row.get("method") == "thread/items/list"], ["two"])
        first_digest = result.get("derived_verification", state)["observation_sha256"]
        self.assert_private_receipts()
        self.output = self.root / "changed-range"
        self.log.unlink()
        changed = self.invoke(mode="range", after_turn_id="two", through_turn_id="three", allow_finalization=True)
        changed_digest = changed.get("derived_verification", self.state()["coverage"])["observation_sha256"]
        self.assertNotEqual(changed_digest, first_digest)
        self.assertEqual([row["params"]["turnId"] for row in self.transcript()
                          if row.get("method") == "thread/items/list"], ["three"])

    def test_range_resume_rechecks_anchor_and_replays_without_earlier_bodies(self):
        first = self.invoke(mode="range_long", after_turn_id="one", probes=1)
        self.assertEqual(first["coverage_status"], "partial")
        self.assertIsNone(self.state()["coverage"]["observation_sha256"])
        final = self.invoke(mode="range_long", resume=True, allow_finalization=True)
        self.assertEqual(final["coverage_status"], "complete_observed")
        self.assertEqual(final["usage"]["selected_items"], 1)
        self.assertEqual([row["params"]["turnId"] for row in self.transcript()
                          if row.get("method") == "thread/items/list"], ["two"])
        self.assert_private_receipts()

    def test_equal_range_endpoints_complete_empty_only_after_revalidation(self):
        first = self.invoke(mode="range", after_turn_id="one", through_turn_id="one", probes=1)
        self.assertEqual(first["coverage_status"], "partial")
        self.assertIsNone(self.state()["coverage"]["observation_sha256"])
        final = self.invoke(mode="range", resume=True, allow_finalization=True)
        self.assertEqual(final["coverage_status"], "complete_observed")
        self.assertEqual(final["usage"]["selected_items"], 0)
        self.assertEqual(self.state()["coverage"]["observed_inventory"], [])
        self.assertEqual(self.state()["coverage"]["closed_item_scopes"], [])
        self.assertFalse(any(row.get("method") == "thread/items/list" for row in self.transcript()))

    def test_invalid_absent_reversed_or_changed_range_anchor_never_completes(self):
        for anchor in (None, False, [], "bad id"):
            with self.subTest(anchor=anchor):
                self.assertEqual(self.invoke(expected=2, after_turn_id=anchor)["reason"], "invalid_walk_after_turn")
                self.assertFalse(self.log.exists())
                self.assertFalse(self.output.exists())
        for label, mode, anchor, reason in (
            ("absent", "range", "missing", "after_turn_missing_or_reversed"),
            ("reversed", "range", "three", "after_turn_missing_or_reversed"),
            ("active", "range_anchor_active", "one", "nonterminal_selected_turn"),
            ("changed", "range_anchor_changed", "one", "selected_inventory_changed")):
            with self.subTest(label=label):
                self.output = self.root / label
                self.log.unlink(missing_ok=True)
                result = self.invoke(expected=1, mode=mode, after_turn_id=anchor)
                self.assertEqual(result["coverage_status"], "partial")
                self.assertEqual(result["reason"], reason)
                self.assertIsNone(self.state()["coverage"]["observation_sha256"])
                self.assertFalse(any(row.get("params", {}).get("turnId") == "one" for row in self.transcript()))
        self.output = self.root / "changed-before-resume-items"
        self.log.unlink()
        self.invoke(mode="range_anchor_changed", after_turn_id="one", probes=1)
        resumed = self.invoke(expected=1, mode="range_anchor_changed", resume=True)
        self.assertEqual(resumed["reason"], "selected_inventory_changed")
        self.assertFalse(any(row.get("method") == "thread/items/list" for row in self.transcript()))

    def verify_capture(self, captured, expected=0, inject=None):
        capture = self.root / ("capture-%d.json" % getattr(self, "capture_number", 0))
        self.capture_number = getattr(self, "capture_number", 0) + 1
        capture.write_text(json.dumps(captured), encoding="utf-8")
        capture.chmod(0o600)
        launcher = [str(WALKER)]
        if inject is not None:
            launcher = ["-c", "import sys, time\n"
                        + "sys.path.insert(0, " + repr(str(WALKER.parent)) + ")\n"
                        + "import walk_history as walker\n" + inject + "\n"
                        + "raise SystemExit(walker.main(sys.argv[1:]))"]
        result = subprocess.run([sys.executable, "-B", *launcher, "--verify-finalization", str(self.output),
                                 "--capture", str(capture)], capture_output=True, text=True, env=self.env, timeout=20)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def delayed_terminal(self, **options):
        return self.invoke(expected=1, inject="""
publish = walker.publish
slow_done = False
def slow_publish(directory, name, raw, replace=False):
    global slow_done
    if name == "state.json" and b'"reason":"selected_scope_end"' in raw and not slow_done:
        slow_done = True
        time.sleep(0.4)
    return publish(directory, name, raw, replace)
walker.publish = slow_publish
""", **options)

    def run_hashes(self):
        return {str(path.relative_to(self.output)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.output.rglob("*") if path.is_file()}

    def test_witnessed_terminal_verifies_readonly_and_repeated_without_provider_calls(self):
        captured = self.delayed_terminal()
        self.assertEqual(captured["coverage_status"], "partial")
        self.assertIn("finalization_witness", captured)
        self.assertEqual(self.state()["coverage"]["phase"], "done")
        hashes = self.run_hashes()
        transcript = self.log.read_bytes()
        first = self.verify_capture(captured)
        second = self.verify_capture(captured)
        self.assertEqual(first["observation_sha256"], second["observation_sha256"])
        self.assertEqual(first["stored_collection_usage"], self.state()["coverage"]["usage"])
        self.assertIsNone(first["exact_closing_elapsed_seconds"])
        self.assertEqual(first["stored_coverage_status"], "partial")
        self.assertEqual(hashes, self.run_hashes())
        self.assertEqual(transcript, self.log.read_bytes())
        self.assertEqual(self.invoke(expected=2, resume=True)["reason"], "uncertain_previous_invocation")
        self.assert_private_receipts()

    def test_witnessed_changed_range_keeps_digest_scope_and_ignores_captured_summary_claims(self):
        captured = self.delayed_terminal(mode="range", after_turn_id="one")
        captured["measured_elapsed_us_before_summary"] = 0
        captured["usage"] = {"probes": 0, "elapsed_us": 0}
        verified = self.verify_capture(captured)
        self.assertEqual(verified["range"]["after_turn_id"], "one")
        self.assertEqual(verified["earlier_item_coverage"], "excluded")
        self.assertEqual(verified["stored_collection_usage"]["selected_items"], 1)
        self.assertGreater(verified["stored_collection_usage"]["probes"], 0)
        self.assertNotIn("measured_elapsed_us_before_summary", verified)

    def test_verification_rejects_missing_bad_tampered_or_locked_evidence(self):
        captured = self.delayed_terminal()
        hashes = self.run_hashes()
        for replacement in (None, {}, {**captured["finalization_witness"], "nonce": "0" * 64},
                            {**captured["finalization_witness"], "elapsed_us": 0}):
            with self.subTest(witness=replacement):
                self.assertEqual(self.verify_capture({"finalization_witness": replacement}, expected=2)["verification_status"], "failed")
        for name in ("state.json", "plan.json", "probe-0001/records.json", "probe-0001/receipt.json"):
            path = self.output / name
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            self.assertEqual(self.verify_capture(captured, expected=2)["verification_status"], "failed")
            path.write_bytes(original)
        with (self.output / ".lock").open("rb") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.verify_capture(captured, expected=2)["reason"], "walk_writer_active")
        active = self.verify_capture(captured, expected=2, inject="walker.os.kill = lambda pid, signal: None")
        self.assertEqual(active["reason"], "finalization_origin_active")
        public_capture = self.verify_capture(captured, expected=2, inject="walker.Path(sys.argv[-1]).chmod(0o644)")
        self.assertEqual(public_capture["reason"], "invalid_private_file")
        marker_path = self.output / ".invocation"
        original = marker_path.read_bytes()
        marker = json.loads(original)
        marker["pid"] = 2 ** 64
        marker_path.write_text(json.dumps(marker))
        bad_pid = json.loads(json.dumps(captured))
        bad_pid["finalization_witness"]["marker_sha256"] = hashlib.sha256(marker_path.read_bytes()).hexdigest()
        self.assertEqual(self.verify_capture(bad_pid, expected=2)["reason"], "invalid_finalization_marker")
        marker_path.write_bytes(original)
        self.assertEqual(hashes, self.run_hashes())

    def test_verification_separate_byte_and_wall_limits_refuse_without_writes(self):
        captured = self.delayed_terminal()
        hashes = self.run_hashes()
        small = self.verify_capture(captured, expected=2, inject='walker.VERIFY_LIMITS = {**walker.VERIFY_LIMITS, "bytes": 1}')
        self.assertEqual(small["reason"], "verification_byte_limit")
        slow = self.verify_capture(captured, expected=2, inject="""
walker.VERIFY_LIMITS = {**walker.VERIFY_LIMITS, "seconds": 0.1}
replay = walker.replay
def slow_replay(*args, **kwargs):
    time.sleep(0.15)
    return replay(*args, **kwargs)
walker.replay = slow_replay
""")
        self.assertEqual(slow["reason"], "verification_wall_limit")
        self.assertEqual(hashes, self.run_hashes())

    def test_nonterminal_or_overdeadline_collection_releases_no_witness(self):
        partial = self.invoke(probes=1)
        self.assertNotIn("finalization_witness", partial)
        self.assertEqual(self.verify_capture(partial, expected=2)["reason"], "invalid_finalization_witness")
        self.output = self.root / "overdeadline"
        late = self.invoke(expected=1, max_seconds=30, inject="""
publish = walker.publish
monotonic_ns = time.monotonic_ns
clock_offset = 0
slow_terminal = False
slow_setup = False
def controlled_monotonic_ns():
    return monotonic_ns() + clock_offset

def slow_publish(directory, name, raw, replace=False):
    global slow_terminal, slow_setup, clock_offset
    if name == "state.json" and b'"reason":"ready"' in raw and not slow_setup:
        slow_setup = True
        time.sleep(1.2)
    result = publish(directory, name, raw, replace)
    if name == "state.json" and b'"reason":"selected_scope_end"' in raw and not slow_terminal:
        slow_terminal = True
        time.sleep(0.4)
    if name == walker.INVOCATION_MARKER and b'"terminal_commitment"' in raw:
        # Advance only after the genuine last marker write and fsync returned.
        # A generous collection allowance keeps slow setup from skipping this stage.
        clock_offset = 31 * walker.MICROS * 1000
    return result

time.monotonic_ns = controlled_monotonic_ns
walker.publish = slow_publish
""")
        self.assertNotIn("finalization_witness", late)
        self.assertEqual(late["coverage_status"], "partial")
        self.assertEqual(late["reason"], "finalization_time_uncertain")
        state = self.state()
        self.assertEqual(state["coverage"]["phase"], "done")
        self.assertIsNone(state["pending"])
        self.assertGreaterEqual(state["coverage"]["usage"]["orchestration_elapsed_us"], 1_200_000)
        self.assertGreater(late["measured_elapsed_us_before_summary"], 30 * 1_000_000)
        marker = json.loads((self.output / ".invocation").read_bytes())
        self.assertIn("terminal_commitment", marker)
        self.assertEqual(marker["terminal_state_sha256"], hashlib.sha256((self.output / "state.json").read_bytes()).hexdigest())
        self.assertEqual(self.verify_capture(late, expected=2)["reason"], "invalid_finalization_witness")

    def test_resume_rejects_file_mutation_rollback_pending_and_live_lock(self):
        self.invoke(probes=2)
        before = len(self.transcript())
        saved = (self.output / "state.json").read_bytes()
        records = self.output / "probe-0002/records.json"
        real_records = records.read_bytes()
        records.write_bytes(real_records + b" ")
        self.assertEqual(self.invoke(expected=2, resume=True)["reason"], "probe_evidence_hash_mismatch")
        records.write_bytes(real_records)
        state = self.state()
        state["pending"] = {"slot": "probe-0003"}
        (self.output / "state.json").write_text(json.dumps(state))
        self.assertEqual(self.invoke(expected=2, resume=True)["reason"], "uncertain_pending_probe")
        (self.output / "state.json").write_bytes(saved)
        extra = self.output / "probe-0003"
        shutil.copytree(self.output / "probe-0002", extra)
        self.assertEqual(self.invoke(expected=2, resume=True)["reason"], "unexpected_walk_files")
        shutil.rmtree(extra)
        with (self.output / ".lock").open("rb") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.invoke(expected=2, resume=True)["reason"], "walk_writer_active")
        self.assertEqual(len(self.transcript()), before)


if __name__ == "__main__":
    unittest.main()
