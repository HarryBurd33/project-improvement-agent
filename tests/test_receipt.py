import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/project-improvement-agent/scripts/audit_receipt.py"
)
PRIVATE_TEXT = "/private/example/private-workspace/token-that-must-not-appear"


def command(item_id, code=0, event="item.completed"):
    return {
        "type": event,
        "item": {
            "type": "command_execution",
            "id": item_id,
            "command": "cat " + PRIVATE_TEXT,
            "aggregated_output": PRIVATE_TEXT,
            "status": "failed" if code else "completed",
            "exit_code": code,
        },
    }


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="private-receipt-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.trace = self.root / "private-trace.jsonl"
        self.report = self.root / "private-report.md"
        self.execution = self.root / "private-execution.json"
        self.claims = self.root / "private-claims.json"
        self.report.write_text("# Draft\n" + PRIVATE_TEXT, encoding="utf-8")

    def write_trace(self, events=(), *, end=True):
        rows = [
            {"type": "thread.started", "thread_id": "private-thread"},
            {"type": "turn.started"},
            *events,
        ]
        if end:
            rows.append({"type": "turn.completed", "usage": {}})
        self.trace.write_bytes(b"".join(json.dumps(row).encode() + b"\n" for row in rows))

    def write_claims(self, values, **updates):
        receipt = {
            "schema_version": 1,
            "trace_sha256": sha256(self.trace),
            "report_sha256": sha256(self.report),
            "claims": values,
        }
        receipt.update(updates)
        self.claims.write_text(json.dumps(receipt), encoding="utf-8")
        return ("--claims", self.claims, "--report", self.report)

    def write_execution(self, value, **updates):
        receipt = {"trace_sha256": sha256(self.trace), "elapsed_seconds": value}
        receipt.update(updates)
        self.execution.write_text(json.dumps(receipt), encoding="utf-8")
        return ("--execution", self.execution)

    def cli(self, *options, code=0, fmt="json"):
        proc = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--trace", str(self.trace),
             "--format", fmt, *map(str, options)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, code, (proc.stdout, proc.stderr))
        self.assertEqual(proc.stderr, "")
        self.assertNotIn(PRIVATE_TEXT, proc.stdout)
        self.assertNotIn(str(self.root), proc.stdout)
        return json.loads(proc.stdout) if fmt == "json" else proc.stdout

    def test_thirteen_completed_commands_does_not_support_fourteen(self):
        events = [command(f"cmd-{i}", event="item.started") for i in range(13)]
        events += [command(f"cmd-{i}") for i in range(13)]
        self.write_trace(events)
        result = self.cli(*self.write_claims({"recorded_shell_calls": 14}), code=1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["facts"]["recorded_shell_calls"]["value"], 13)
        self.assertEqual(result["claim_checks"]["recorded_shell_calls"], "mismatch")
        result = self.cli(*self.write_claims({"recorded_shell_calls": 13}))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["claim_checks"]["recorded_shell_calls"], "matched")

    def test_absent_or_unrecognized_events_do_not_prove_other_counts_or_time(self):
        self.write_trace([
            command("c"),
            {"type": "clock.read", "elapsed_seconds": 0},
            {"type": "catalog.inspection", "count": 0},
            {"type": "unrecognized.event", "utc": "2026-01-01T00:00:00Z"},
        ])
        unknown = {
            "clock_reads": 0, "catalog_inspections": 0,
            "collection_end_utc": "2026-01-01T00:00:00Z", "elapsed_seconds": 0,
        }
        result = self.cli(*self.write_claims(unknown), code=1)
        for key in unknown:
            with self.subTest(key=key):
                self.assertIsNone(result["facts"][key]["value"])
                self.assertEqual(result["claim_checks"][key], "unsupported")
        result = self.cli(*self.write_claims(dict.fromkeys(unknown)))
        self.assertEqual(set(result["claim_checks"].values()), {"not_asserted"})

    def test_zero_elapsed_and_zero_failed_are_supported(self):
        self.write_trace([command("c")])
        result = self.cli(
            *self.write_execution(0.0),
            *self.write_claims({"recorded_failed_shell_calls": 0, "elapsed_seconds": 0}),
        )
        self.assertEqual(result["facts"]["recorded_failed_shell_calls"]["value"], 0)
        self.assertEqual(result["facts"]["elapsed_seconds"]["value"], 0.0)
        self.assertEqual(set(result["claim_checks"].values()), {"matched"})

    def test_nonzero_codes_count_and_facts_only_ignores_unavailable_elapsed(self):
        self.write_trace([command("c"), command("e", 7), command("signal", -9)])
        result = self.cli()
        self.assertEqual(result["facts"]["recorded_failed_shell_calls"]["value"], 2)
        self.assertIsNone(result["facts"]["elapsed_seconds"]["value"])
        self.assertEqual(result["claim_checks"], {})
        self.assertNotIn("report_sha256", result)

    def test_clean_empty_turn_records_zero_but_empty_file_is_partial(self):
        self.write_trace()
        result = self.cli()
        self.assertEqual(result["facts"]["recorded_shell_calls"]["value"], 0)
        self.assertEqual(result["facts"]["recorded_failed_shell_calls"]["value"], 0)
        self.trace.write_bytes(b"")
        result = self.cli(code=3)
        self.assertIsNone(result["facts"]["recorded_shell_calls"]["value"])

    def test_missing_exit_code_keeps_command_count_but_not_failure_total(self):
        event = command("c")
        del event["item"]["exit_code"]
        self.write_trace([event])
        result = self.cli(code=3)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["facts"]["recorded_shell_calls"]["value"], 1)
        self.assertIsNone(result["facts"]["recorded_failed_shell_calls"]["value"])
        result = self.cli(*self.write_claims({"recorded_failed_shell_calls": 0}), code=1)
        self.assertEqual(result["claim_checks"]["recorded_failed_shell_calls"], "unsupported")

    def test_only_normal_single_turn_can_pass(self):
        cases = [
            ("truncated", [command("c")], False),
            ("error", [{"type": "error", "message": PRIVATE_TEXT}], True),
            ("failed", [{"type": "turn.failed", "error": {"message": PRIVATE_TEXT}}], False),
            ("multiple turns", [{"type": "turn.completed"}, {"type": "turn.started"}], True),
            ("unfinished command", [command("c", event="item.started")], True),
            ("post-terminal data", [{"type": "turn.completed"}, {"type": "unknown"}], False),
        ]
        for label, events, end in cases:
            with self.subTest(case=label):
                self.write_trace(events, end=end)
                result = self.cli(code=3)
                self.assertEqual(result["status"], "partial")
                self.assertIs(result["trace_complete"], False)

    def test_malformed_lines_invalid_shapes_and_duplicate_ids(self):
        for malformed in (
            b"{bad",
            b"[]",
            b"\xff",
            b'{"type":"turn.started","type":"turn.completed"}',
            b'{"type":"item.completed","item":[]}',
        ):
            with self.subTest(malformed=malformed):
                self.write_trace()
                with self.trace.open("ab") as stream:
                    stream.write(malformed)
                self.assertEqual(self.cli(code=2)["status"], "failed")
        self.write_trace([command(PRIVATE_TEXT), command(PRIVATE_TEXT)])
        result = self.cli(code=2)
        self.assertIn("duplicate completed item ID", result["errors"][0])
        self.write_trace([command("c", True)])
        self.assertIn("exit code must be an integer", self.cli(code=2)["errors"][0])

    def test_stale_trace_report_and_execution_bindings(self):
        self.write_trace([command("c")])
        options = self.write_claims({"recorded_shell_calls": 1})
        self.trace.write_bytes(self.trace.read_bytes() + b"\n")
        result = self.cli(*options, code=1)
        self.assertIn("trace_sha256 does not match", result["errors"][0])
        options = self.write_claims({"recorded_shell_calls": 1})
        self.report.write_bytes(self.report.read_bytes() + b"\n")
        result = self.cli(*options, code=1)
        self.assertIn("report_sha256 does not match", result["errors"][0])
        options = self.write_execution(0, trace_sha256="a" * 64)
        result = self.cli(*options, code=1)
        self.assertIsNone(result["facts"]["elapsed_seconds"]["value"])
        self.execution.write_text(json.dumps({"elapsed_seconds": 12}), encoding="utf-8")
        result = self.cli(*options, code=1)
        self.assertIn("missing trace_sha256", result["errors"][0])

    def test_invalid_numeric_values_and_sidecar_schemas(self):
        self.write_trace()
        for value in (-1, False, "0", float("inf"), float("nan")):
            with self.subTest(duration=value):
                self.cli(*self.write_execution(value), code=2)
        for token in ("1e309", "-1e-9999", "1e-9999"):
            with self.subTest(token=token):
                self.execution.write_text(
                    '{"trace_sha256":"' + sha256(self.trace) + '","elapsed_seconds":' + token + '}',
                    encoding="utf-8",
                )
                self.cli("--execution", self.execution, code=2)
        for schema in (True, 2, None):
            with self.subTest(schema=schema):
                self.cli(*self.write_claims({}, schema_version=schema), code=2)
        self.cli(*self.write_claims({"recorded_shell_calls": False}), code=2)
        self.cli(*self.write_claims({PRIVATE_TEXT: 1}), code=2)
        self.cli(*self.write_claims({"elapsed_seconds": -1}), code=2)
        self.claims.write_text(
            '{"schema_version":1,"schema_version":1,"claims":{}}', encoding="utf-8",
        )
        self.cli("--claims", self.claims, code=2)

    def test_nonempty_claims_require_report_even_when_value_is_null(self):
        self.write_trace()
        self.write_claims({"elapsed_seconds": None})
        result = self.cli("--claims", self.claims, code=2)
        self.assertIn("nonempty claims require --report", result["errors"][0])
        self.claims.write_text(json.dumps({
            "schema_version": 1, "trace_sha256": sha256(self.trace), "claims": {},
        }), encoding="utf-8")
        self.cli("--claims", self.claims)
        self.cli("--claims", self.claims, "--report", self.report, code=1)

    def test_inputs_are_immutable_and_markdown_is_deterministic_and_safe(self):
        self.write_trace([command("c", 4)])
        options = (
            *self.write_execution(0),
            *self.write_claims({"recorded_shell_calls": 1, "recorded_failed_shell_calls": 1}),
        )
        before = {p: sha256(p) for p in self.root.iterdir()}
        result = self.cli(*options, fmt="markdown")
        self.assertEqual(result, self.cli(*options, fmt="markdown"))
        self.assertIn("Recorded shell calls: **1**", result)
        self.assertIn("Clock reads: **unknown**", result)
        self.assertIn(sha256(self.trace), result)
        self.assertIn(sha256(self.report), result)
        self.assertEqual(before, {p: sha256(p) for p in self.root.iterdir()})


if __name__ == "__main__":
    unittest.main()
