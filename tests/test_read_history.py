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

    def invoke(self, scenario="success", output=None, **overrides):
        plan = {"schema_version": 1, "thread_id": "fake-chat", "operation": "items", "turn_id": "fake-turn",
                "page_size": 2, "max_pages": 2, "max_records": 4, **overrides}
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
