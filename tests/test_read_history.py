"""Actual child-process checks for the private selected-history reader."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

from history_peer import assistant_rows


ROOT = Path(__file__).resolve().parents[1]
READER = ROOT / "skills/project-improvement-agent/scripts/read_history.py"
PEER = ROOT / "tests/history_peer.py"


class ReadHistoryTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        # macOS can select a temporary root through a textual path alias.
        self.root = Path(scratch.name).resolve()
        self.transcript = self.root / "peer.jsonl"
        self.output = self.root / "private"
        self.plan = self.root / "plan.json"
        command = self.root / "codex"
        command.write_text("#!" + sys.executable + "\nimport runpy\nrunpy.run_path("
                           + repr(str(PEER)) + ", run_name='__main__')\n", encoding="utf-8")
        command.chmod(0o700)
        self.env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ["PATH"],
                        PIA_TEST_TRANSCRIPT=str(self.transcript))

    def invoke(self, scenario="success", output=None, omit=(), **overrides):
        plan = {"schema_version": 1, "thread_id": "fake-chat", "operation": "items", "turn_id": "fake-turn",
                "page_size": 2, "max_pages": 2, "max_records": 4, **overrides}
        for field in omit:
            del plan[field]
        plan_bytes = json.dumps(plan).encode()
        self.plan.write_bytes(plan_bytes)
        result = subprocess.run([sys.executable, "-B", str(READER), "--plan", str(self.plan),
                                 "--output", str(output or self.output)], capture_output=True, text=True,
                                env=dict(self.env, PIA_TEST_SCENARIO=scenario), timeout=8)
        self.assertEqual(self.plan.read_bytes(), plan_bytes)
        self.assertNotIn("PRIVATE_", result.stdout + result.stderr)
        self.assertNotIn("Exact user text", result.stdout + result.stderr)
        self.assertNotIn("opaque#1", result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        return result, json.loads(result.stdout)

    def private(self, code, result):
        self.assertEqual(result.returncode, code, result.stdout)
        data = self.output / "records.json"
        receipt_file = self.output / "receipt.json"
        receipt = json.loads(receipt_file.read_bytes())
        self.assertEqual(receipt["records_sha256"], hashlib.sha256(data.read_bytes()).hexdigest())
        self.assertEqual(receipt["plan_sha256"], hashlib.sha256(self.plan.read_bytes()).hexdigest())
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(data.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(receipt_file.stat().st_mode), 0o600)
        self.assertNotIn(b"PRIVATE_", data.read_bytes() + receipt_file.read_bytes())
        self.assertEqual(receipt["received_bytes"], receipt["stdout_bytes"] + receipt["stderr_bytes"])
        self.assertLessEqual(receipt["received_bytes"], receipt["plan"]["max_bytes"])
        self.assertTrue(receipt["cleanup"]["reaped"])
        self.assertTrue(receipt["cleanup"]["group_gone"])
        with self.assertRaises(ProcessLookupError):
            os.kill(receipt["cleanup"]["pid"], 0)
        return receipt, json.loads(data.read_bytes())

    def test_two_pages_preserve_text_ids_and_exact_cursor(self):
        result, summary = self.invoke(cursor="opaque initial")
        receipt, rows = self.private(0, result)
        self.assertEqual(summary["status"], "complete")
        self.assertEqual([row["item_id"] for row in rows], ["first", "proof", "second"])
        self.assertEqual(rows[0]["text_parts"], ["Exact user text\nπ\t  "])
        self.assertEqual(rows[0]["omitted_nontext_parts"], 1)
        self.assertEqual(rows[0]["turn_id"], "fake-turn")
        self.assertEqual(rows[0]["started_at_ms"], 10)
        self.assertIsNone(rows[0]["completed_at_ms"])
        self.assertEqual(rows[0]["role"], "user")
        self.assertNotIn("text_parts", rows[1])
        self.assertRegex(rows[1]["serialized_item_sha256"], r"^[a-f0-9]{64}$")
        transcript = [json.loads(line) for line in self.transcript.read_text().splitlines()]
        self.assertEqual(transcript[0]["argv"], ["app-server", "--stdio"])
        methods = [row["method"] for row in transcript[1:]]
        self.assertEqual(methods, ["initialize", "initialized", "thread/items/list", "thread/items/list"])
        self.assertEqual(transcript[3]["params"]["cursor"], "opaque initial")
        self.assertEqual(transcript[4]["params"]["cursor"], "opaque#1 ?\t")
        self.assertEqual(receipt["accepted_pages"][0]["next_cursor"], "opaque#1 ?\t")
        self.assertIsNone(receipt["last_safe_cursor"])

    def test_turns_accept_optional_view_omission(self):
        result, _ = self.invoke(operation="turns", turn_id=None)
        receipt, rows = self.private(0, result)
        self.assertEqual(receipt["requests"][0]["params"]["itemsView"], "notLoaded")
        self.assertEqual(rows[0]["turn_id"], "fake-turn")
        self.assertEqual(rows[0]["started_at_seconds"], 8)

    def test_turns_accept_explicit_not_loaded_and_refuse_other_views(self):
        for scenario, code in (("turn_view_explicit", 0), ("turn_view_full", 1), ("turn_view_summary", 1)):
            with self.subTest(scenario=scenario):
                self.output = self.root / scenario
                result, _ = self.invoke(scenario, operation="turns", turn_id=None)
                receipt, rows = self.private(code, result)
                self.assertEqual(receipt["reason"], "selected_scope_end" if code == 0 else "invalid_turn_record")
                self.assertEqual(len(rows), int(code == 0))

    def test_record_budget_reduces_next_requested_limit(self):
        result, _ = self.invoke(max_records=3)
        receipt, rows = self.private(0, result)
        self.assertEqual([r["params"]["limit"] for r in receipt["requests"]], [2, 1])
        self.assertEqual(len(rows), 3)

    def test_bounded_partial_keeps_validated_cursor(self):
        result, _ = self.invoke(max_pages=1)
        receipt, rows = self.private(0, result)
        self.assertEqual(receipt["status"], "partial")
        self.assertEqual(receipt["reason"], "page_limit")
        self.assertEqual(receipt["last_safe_cursor"], "opaque#1 ?\t")
        self.assertEqual(len(rows), 2)

    def test_invalid_second_pages_do_not_advance(self):
        for scenario, reason in (("repeat", "cursor_no_progress"), ("dup_record", "record_no_progress"),
                                 ("mixed_limit", "byte_limit")):
            with self.subTest(scenario=scenario):
                self.output = self.root / scenario
                result, _ = self.invoke(scenario, max_bytes=4000)
                receipt, rows = self.private(1, result)
                self.assertEqual((receipt["status"], receipt["reason"]), ("partial", reason))
                self.assertEqual(receipt["last_safe_cursor"], "opaque#1 ?\t")
                self.assertEqual(len(rows), 2)
                if scenario == "mixed_limit":
                    self.assertEqual(receipt["received_bytes"], 4000)
                    self.assertGreater(receipt["stderr_bytes"], 0)

    def test_bad_first_pages_and_exits_report_safe_boundary(self):
        for scenario, reason in (
            ("overreturn", "overreturned_page"), ("wrong_turn", "wrong_turn_scope"),
            ("bad_cursor", "invalid_response_cursor"), ("missing_cursor", "missing_response_cursor"), ("empty_cursor", "cursor_no_progress"),
            ("bad_json", "malformed_response"), ("wrong_id", "unexpected_response_envelope"),
            ("rpc", "rpc_error"), ("server_request", "unexpected_server_request"),
            ("exit", "peer_exited"), ("truncated", "truncated_response"), ("timeout", "wall_limit"),
            ("notification_limit", "byte_limit"), ("stderr_limit", "byte_limit"),
        ):
            with self.subTest(scenario=scenario):
                self.output = self.root / scenario
                result, _ = self.invoke(scenario, cursor="input-cursor", max_seconds=0.75, max_bytes=4000)
                receipt, rows = self.private(1, result)
                self.assertEqual(receipt["reason"], reason)
                self.assertEqual(receipt["last_safe_cursor"], "input-cursor")
                self.assertEqual(rows, [])
                self.assertEqual(receipt["attempted_page_count"], 1)
                self.assertLess(receipt["elapsed_seconds"], 3.3)
                if reason == "byte_limit":
                    self.assertEqual(receipt["received_bytes"], 4000)
                if scenario == "server_request":
                    self.assertEqual(receipt["server_requests"], 1)

    def test_complete_response_on_exact_combined_byte_ceiling(self):
        result, _ = self.invoke("exact_mixed")
        reference, expected = self.private(0, result)
        self.assertGreater(reference["stderr_bytes"], 0)
        self.assertGreater(reference["notifications"], 0)
        self.output = self.root / "exact-boundary"
        result, _ = self.invoke("exact_mixed", max_bytes=reference["received_bytes"])
        receipt, actual = self.private(0, result)
        self.assertEqual(receipt["status"], "complete")
        self.assertEqual(receipt["received_bytes"], reference["received_bytes"])
        self.assertEqual(receipt["stderr_bytes"], reference["stderr_bytes"])
        self.assertEqual(receipt["stdout_bytes"], reference["stdout_bytes"])
        self.assertEqual(actual, expected)
        self.output = self.root / "one-byte-short"
        result, _ = self.invoke("exact_mixed", max_bytes=reference["received_bytes"] - 1)
        receipt, actual = self.private(1, result)
        self.assertEqual((receipt["status"], receipt["reason"]), ("partial", "byte_limit"))
        self.assertEqual(receipt["received_bytes"], reference["received_bytes"] - 1)
        self.assertEqual(receipt["last_safe_cursor"], "opaque#1 ?\t")
        self.assertEqual(actual, expected[:2])

    def test_owned_group_reaps_peer_that_ignores_termination(self):
        result, _ = self.invoke("ignore_term", max_seconds=0.75)
        receipt, rows = self.private(1, result)
        self.assertEqual(receipt["reason"], "wall_limit")
        self.assertEqual(receipt["cleanup"]["signals"], ["SIGTERM", "SIGKILL"])
        self.assertLess(receipt["elapsed_seconds"], 3.3)
        self.assertEqual(rows, [])

    def large(self, scenario, **overrides):
        profile = {"read_mode": "large_single_page", "page_size": 1, "max_pages": 1,
                   "max_records": 1, "max_bytes": 4 * 1024 * 1024, **overrides}
        return self.invoke(scenario, **profile)

    def test_standard_remains_capped_for_large_items(self):
        for selection in ({}, {"read_mode": "standard"}):
            self.output = self.root / ("standard-explicit" if selection else "standard-implicit")
            result, _ = self.invoke("large_user", cursor="input-cursor", **selection)
            receipt, rows = self.private(1, result)
            self.assertEqual(receipt["plan"]["read_mode"], "standard")
            self.assertEqual(receipt["received_bytes"], 131072)
            self.assertEqual(receipt["reason"], "byte_limit")
            self.assertEqual(receipt["last_safe_cursor"], "input-cursor")
            self.assertEqual(rows, [])

    def test_large_unicode_exact_cap_and_one_byte_short(self):
        result, _ = self.large("large_user", cursor="input-cursor")
        reference, rows = self.private(0, result)
        self.assertGreater(reference["received_bytes"], 131072)
        self.assertGreater(reference["stderr_bytes"], 0)
        self.assertGreater(reference["notifications"], 0)
        self.assertEqual(reference["plan"]["read_mode"], "large_single_page")
        self.assertEqual(reference["accepted_records"], 1)
        self.assertEqual(reference["attempted_page_count"], 1)
        self.assertEqual(reference["last_safe_cursor"], "opaque#1 ?\t")
        self.assertEqual((rows[0]["item_id"], rows[0]["turn_id"]), ("large-user", "fake-turn"))
        self.assertEqual(rows[0]["text_parts"], ["Exact selected π 🌱\n  " * 12000])
        self.assertNotIn("Exact selected", result.stdout)
        self.assertEqual((rows[0]["started_at_ms"], rows[0]["completed_at_ms"]), (10, 42))
        transcript = [json.loads(line) for line in self.transcript.read_text().splitlines()]
        self.assertEqual([entry["method"] for entry in transcript[1:]],
                         ["initialize", "initialized", "thread/items/list"])
        self.assertEqual(transcript[-1]["params"], {"cursor": "input-cursor", "threadId": "fake-chat",
                         "turnId": "fake-turn", "limit": 1, "sortDirection": "asc"})
        for label, cap, code in (("exact", reference["received_bytes"], 0),
                                 ("short", reference["received_bytes"] - 1, 1)):
            with self.subTest(label=label):
                self.output = self.root / label
                result, _ = self.large("large_user", max_bytes=cap, cursor="input-cursor")
                receipt, actual = self.private(code, result)
                self.assertEqual(receipt["received_bytes"], cap)
                self.assertEqual(actual, rows if code == 0 else [])
                self.assertEqual(receipt["last_safe_cursor"], "input-cursor" if code else "opaque#1 ?\t")

    def test_large_nonuser_exact_hash_and_privacy(self):
        result, _ = self.large("large_nonuser")
        receipt, rows = self.private(0, result)
        self.assertGreater(receipt["received_bytes"], 131072)
        item = {"id": "large-other", "type": "reasoning", "text": "PRIVATE_NONUSER_PAYLOAD" * 18000,
                "arguments": {"instruction": "PRIVATE_NONUSER_PAYLOAD"}}
        raw = (json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
        self.assertEqual(rows[0]["serialized_item_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertNotIn("text_parts", rows[0])
        self.assertIsNone(rows[0]["role"])

    def test_large_profile_stops_at_four_mib_and_preserves_input_cursor(self):
        result, _ = self.large("large_overcap", cursor="input-cursor")
        receipt, rows = self.private(1, result)
        self.assertEqual(receipt["received_bytes"], 4194304)
        self.assertEqual(receipt["reason"], "byte_limit")
        self.assertEqual(receipt["last_safe_cursor"], "input-cursor")
        self.assertEqual(rows, [])

    def test_large_profile_retains_page_validation_and_timeout(self):
        for scenario, reason in (("overreturn", "overreturned_page"), ("wrong_turn", "wrong_turn_scope"),
                                 ("truncated", "truncated_response"), ("server_request", "unexpected_server_request"),
                                 ("timeout", "wall_limit")):
            with self.subTest(scenario=scenario):
                self.output = self.root / scenario
                result, _ = self.large(scenario, cursor="input-cursor", max_seconds=0.75)
                receipt, rows = self.private(1, result)
                self.assertEqual(receipt["reason"], reason)
                self.assertEqual(receipt["last_safe_cursor"], "input-cursor")
                self.assertEqual(receipt["attempted_page_count"], 1)
                self.assertEqual(rows, [])

    def test_invalid_large_profiles_refuse_before_process_and_output(self):
        invalid = [
            {"read_mode": None}, {"read_mode": False}, {"read_mode": []}, {"read_mode": "large_single_pages"},
            {"read_mode": "standard"}, {"max_bytes": True}, {"max_bytes": 131072}, {"max_bytes": 0},
            {"max_bytes": -1}, {"max_bytes": 4194305}, {"max_bytes": 4194304.0}, {"max_bytes": "200000"},
            {"page_size": 2}, {"max_pages": 2}, {"max_records": True}, {"max_seconds": 16},
            {"operation": "turns", "turn_id": None}, {"turn_id": None}, {"turn_id": "bad turn"},
            *({"omit": (key,)} for key in ("page_size", "max_pages", "max_records", "max_bytes", "turn_id")),
        ]
        for override in invalid:
            with self.subTest(override=override):
                result, summary = self.large("large_user", **override)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(summary["status"], "refused")
                self.assertFalse(self.output.exists())
                self.assertFalse(self.transcript.exists())

    def batch(self, scenario, **overrides):
        profile = {"read_mode": "large_batch_page", "page_size": 2, "max_pages": 1,
                   "max_records": 2, "max_bytes": 4194304, "cursor": "input-cursor", **overrides}
        return self.invoke(scenario, **profile)

    def test_large_batch_exact_limit_and_unadvanced_short_limit(self):
        result, _ = self.batch("large_batch")
        receipt, rows = self.private(0, result)
        cap = receipt["received_bytes"]
        self.assertGreater(cap, 131072)
        self.assertGreater(receipt["stderr_bytes"], 0)
        self.assertEqual(receipt["accepted_records"], 2)
        self.assertEqual(receipt["plan"]["read_mode"], "large_batch_page")
        self.assertEqual(receipt["requests"], [{"id": 2, "method": "thread/items/list", "params": {
            "cursor": "input-cursor", "threadId": "fake-chat", "turnId": "fake-turn", "limit": 2,
            "sortDirection": "asc"}}])
        self.assertEqual(rows[0]["text_parts"], ["Exact batch π 🌱\n  " * 9000])
        self.assertNotIn("text_parts", rows[1])
        self.assertNotIn("Exact batch", result.stdout)
        for name, ceiling, code in (("exact", cap, 0), ("short", cap - 1, 1)):
            self.output = self.root / name
            result, _ = self.batch("large_batch", max_bytes=ceiling)
            exact, actual = self.private(code, result)
            self.assertEqual(exact["received_bytes"], ceiling)
            self.assertEqual(exact["last_safe_cursor"], "input-cursor" if code else "batch-next")
            self.assertEqual(actual, [] if code else rows)

    def test_large_batch_preserves_default_caps_and_rejects_unsafe_plans(self):
        for override in ({"read_mode": None}, {"read_mode": False}, {"read_mode": []}, {"read_mode": "standard"},
                         {"read_mode": "large_single_page"}, {"max_bytes": True}, {"max_bytes": 131072},
                         {"max_bytes": 4194305}, {"max_bytes": 4194304.0}, {"operation": "turns", "turn_id": None},
                         {"page_size": False}, {"page_size": 21}, {"max_records": 1}, {"max_pages": 2},
                         {"turn_id": None}, {"turn_id": "bad turn"},
                         *({"omit": (field,)} for field in ("turn_id", "page_size", "max_pages", "max_records",
                                                          "max_bytes", "read_mode"))):
            with self.subTest(override=override):
                result, summary = self.batch("large_batch", **override)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(summary["status"], "refused")
                self.assertFalse(self.output.exists())
                self.assertFalse(self.transcript.exists())
        result, _ = self.invoke("large_batch", max_pages=1, cursor="input-cursor")
        receipt, rows = self.private(1, result)
        self.assertEqual(receipt["reason"], "byte_limit")
        self.assertEqual(receipt["received_bytes"], 131072)
        self.assertEqual(receipt["last_safe_cursor"], "input-cursor")
        self.assertEqual(rows, [])

    def test_large_batch_rejects_overreturn_repeat_scope_and_malformed_pages(self):
        for scenario, reason in (("overreturn", "overreturned_page"), ("large_batch_repeat", "cursor_no_progress"),
                                 ("wrong_turn", "wrong_turn_scope"), ("missing_cursor", "missing_response_cursor")):
            with self.subTest(scenario=scenario):
                self.output = self.root / scenario
                result, _ = self.batch(scenario)
                receipt, rows = self.private(1, result)
                self.assertEqual(receipt["reason"], reason)
                self.assertEqual(receipt["last_safe_cursor"], "input-cursor")
                self.assertEqual(rows, [])

    def selected_assistant_plan(self, scenario="assistant_final"):
        item = assistant_rows(scenario)[1]["item"]
        if scenario == "assistant_missing":
            item = assistant_rows("assistant_final")[1]["item"]
        canonical = json.dumps(item, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n"
        return {"item_id": item["id"], "expected_sha256": hashlib.sha256(canonical.encode("ascii")).hexdigest()}

    def test_default_omits_assistant_text_and_exact_selection_is_private(self):
        result, _ = self.invoke("assistant_final", max_pages=1, page_size=5, max_records=5)
        receipt, ordinary = self.private(0, result)
        self.assertNotIn("assistant_text_selection", receipt["plan"])
        self.assertNotIn("assistant_text", ordinary[1])
        self.assertNotIn("assistant_phase", ordinary[1])
        selection = self.selected_assistant_plan()
        self.assertEqual(ordinary[1]["serialized_item_sha256"], selection["expected_sha256"])

        self.output = self.root / "selected"
        result, _ = self.invoke("assistant_final", max_pages=1, page_size=5, max_records=5,
                                cursor="selected-input", assistant_text_selection=selection)
        receipt, selected = self.private(0, result)
        self.assertNotIn("Exact selected reply", result.stdout + result.stderr)
        self.assertNotIn("Exact selected reply", (self.output / "receipt.json").read_text())
        self.assertEqual(receipt["last_safe_cursor"], "assistant-next")
        self.assertEqual(receipt["plan"]["assistant_text_selection"], selection)
        self.assertEqual(receipt["requests"][0]["params"], {"threadId": "fake-chat", "turnId": "fake-turn",
                         "cursor": "selected-input", "sortDirection": "asc", "limit": 5})
        expected = {"assistant_text": "Exact selected reply π 🌱\n  ", "assistant_phase": "final_answer"}
        self.assertEqual(selected[1], {**ordinary[1], **expected})
        self.assertEqual(selected[:1] + selected[2:], ordinary[:1] + ordinary[2:])

    def test_explicit_assistant_selection_retains_observed_phase_and_empty_text(self):
        for scenario, phase in (("assistant_commentary", "commentary"), ("assistant_partial", "partial_answer"),
                                ("assistant_phase_omitted", None), ("assistant_phase_null", None)):
            with self.subTest(scenario=scenario):
                self.output = self.root / scenario
                result, _ = self.invoke(scenario, max_pages=1, page_size=5, max_records=5,
                                        assistant_text_selection=self.selected_assistant_plan(scenario))
                _, rows = self.private(0, result)
                self.assertEqual(rows[1]["assistant_phase"], phase)
                self.assertEqual(rows[1]["assistant_text"], assistant_rows(scenario)[1]["item"]["text"])

    def test_invalid_assistant_selection_refuses_before_process_and_output(self):
        selection = self.selected_assistant_plan()
        plans = [{"assistant_text_selection": value} for value in (
            None, [], "*", {}, {**selection, "extra": True}, {"item_id": "known"},
            {**selection, "item_id": "*"}, {**selection, "item_id": "bad id"},
            {**selection, "expected_sha256": selection["expected_sha256"].upper()},
            {**selection, "expected_sha256": "a" * 63}, {**selection, "expected_sha256": 42},
        )]
        plans += [{"max_pages": 2}, {"max_pages": True}, {"operation": "turns", "turn_id": None},
                  {"turn_id": None}, {"omit": ("max_pages",)}, {"omit": ("turn_id",)}]
        for override in plans:
            with self.subTest(override=override):
                plan = {"max_pages": 1, "assistant_text_selection": selection, **override}
                result, summary = self.invoke("assistant_final", **plan)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(summary["status"], "refused")
                self.assertFalse(self.output.exists())
                self.assertFalse(self.transcript.exists())

    def test_assistant_selection_fails_atomically_when_any_page_requirement_fails(self):
        cases = {"assistant_missing": "selected_assistant_item_missing", "assistant_duplicate": "record_no_progress",
                 "assistant_wrong_type": "selected_assistant_item_wrong_type", "assistant_wrong_turn": "wrong_turn_scope",
                 "assistant_bad_phase": "invalid_selected_assistant_content",
                 "assistant_bad_text": "invalid_selected_assistant_content",
                 "assistant_bad_neighbor": "invalid_record_timestamp", "assistant_wrong_hash": "selected_assistant_item_hash_mismatch"}
        for scenario, reason in cases.items():
            with self.subTest(scenario=scenario):
                self.output = self.root / scenario
                selection = self.selected_assistant_plan(scenario)
                if scenario == "assistant_wrong_hash":
                    selection["expected_sha256"] = "0" * 64
                result, _ = self.invoke(scenario, page_size=5, max_pages=1, max_records=5,
                                        cursor="selected-input", assistant_text_selection=selection)
                receipt, rows = self.private(1, result)
                self.assertEqual(receipt["reason"], reason)
                self.assertEqual(receipt["last_safe_cursor"], "selected-input")
                self.assertEqual(receipt["accepted_page_count"], 0)
                self.assertEqual(rows, [])

    def test_valid_empty_page_finishes_only_selected_scope(self):
        result, _ = self.invoke("empty")
        receipt, rows = self.private(0, result)
        self.assertEqual(rows, [])
        self.assertEqual(receipt["boundary"], "selected_scope_end")
        self.assertEqual(receipt["accepted_page_count"], 1)

    def test_invalid_plan_and_existing_or_symlink_output_refuse_prelaunch(self):
        for override in ({"max_seconds": True}, {"max_bytes": 0}, {"max_pages": 3}, {"page_size": False},
                         {"operation": "thread/start"}, {"thread_id": ["another-chat"]}, {"config": "unsupported"}):
            with self.subTest(override=override):
                result, summary = self.invoke(**override)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(summary["status"], "refused")
                self.assertFalse(self.output.exists())
        self.output.mkdir()
        sentinel = self.output / "sentinel"
        sentinel.write_bytes(b"keep")
        result, _ = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(sentinel.read_bytes(), b"keep")
        link = self.root / "link"
        link.symlink_to(self.output, target_is_directory=True)
        result, _ = self.invoke(output=link / "new")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.output / "new").exists())
        self.assertFalse(self.transcript.exists())

    def test_plan_symlink_refuses_prelaunch(self):
        real_plan = self.root / "real-plan.json"
        self.plan.symlink_to(real_plan)
        result, summary = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(summary["reason"], "symlink_path")
        self.assertFalse(self.transcript.exists())


if __name__ == "__main__":
    unittest.main()
