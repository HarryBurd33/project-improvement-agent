import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/project-improvement-agent/scripts"
sys.path.insert(0, str(SCRIPTS))
try:
    import audit_session as session
finally:
    sys.path.pop(0)

PRIVATE_TEXT = "/private/test/secret-command-or-output"


def json_data(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(item_id, event="completed", *, code=0, output=PRIVATE_TEXT):
    return {
        "type": f"item.{event}",
        "item": {
            "type": "command_execution",
            "id": item_id,
            "command": "cat " + PRIVATE_TEXT,
            "aggregated_output": output if event == "completed" else "",
            "status": "completed" if event == "completed" else "in_progress",
            "exit_code": code if event == "completed" else None,
        },
    }


def item(item_id, item_type, event="completed"):
    return {"type": f"item.{event}", "item": {"id": item_id, "type": item_type}}


class SessionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.spec = self.root / "private-spec.json"
        self.intake = self.root / "private-intake.json"
        self.trace = self.root / "private-trace.jsonl"
        self.classification = self.root / "private-classification.json"
        self.execution = self.root / "private-execution.json"
        self.body = self.root / "private-body.md"
        self.bundle = self.root / "private-bundle"
        self.spec_value = {
            "schema_version": 1,
            "run_id": "snow-雪",
            "scope": {"chat": None, "project": "workspace", "basis": "request"},
            "criteria": [{"id": "A", "expected": "local evidence", "method": "file read"}],
        }
        self.spec.write_bytes(b" \r\n" + json_data(self.spec_value) + b"\r\n")
        self.body_data = b"# Original\r\nAll-tool total was 8. \xe9\x9b\xaa\r\nNo final newline"
        self.body.write_bytes(self.body_data)

    def cli(self, *args, code=0, mock_write=None):
        argv = list(map(str, args))
        if mock_write is None:
            proc = subprocess.run(
                [sys.executable, "-B", str(SCRIPTS / "audit_session.py"), *argv],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.stderr, "")
            actual, stdout = proc.returncode, proc.stdout
        else:
            stream = io.StringIO()
            with patch.object(session, "write_private", side_effect=mock_write):
                with contextlib.redirect_stdout(stream):
                    actual = session.main(argv)
            stdout = stream.getvalue()
        self.assertEqual(actual, code, stdout)
        self.assertNotIn(PRIVATE_TEXT, stdout)
        self.assertNotIn(str(self.root), stdout)
        return json.loads(stdout)

    def new_intake(self):
        result = self.cli("intake", "--spec", self.spec, "--output", self.intake)
        self.assertEqual(result, {
            "type": "pia.intake", "schema_version": 1, "run_id": self.spec_value["run_id"],
            "intake_sha256": digest(self.spec),
        })
        return json.dumps(result) + "\n"

    def write_trace(self, events=(), *, complete=True):
        rows = [{"type": "thread.started"}, {"type": "turn.started"}, *events]
        if complete:
            rows.append({"type": "turn.completed"})
        self.trace.write_bytes(b"".join(json_data(row) + b"\n" for row in rows))

    def write_classification(self, commands, **overrides):
        value = {
            "schema_version": 1, "trace_sha256": digest(self.trace),
            "intake_sha256": digest(self.intake), "commands": commands,
        }
        self.classification.write_bytes(json_data(dict(value, **overrides)))

    def write_execution(self, elapsed, **overrides):
        value = {"elapsed_seconds": elapsed, "trace_sha256": digest(self.trace)}
        self.execution.write_bytes(json_data(dict(value, **overrides)))

    def check(self, code=0):
        return self.cli(
            "check-order", "--trace", self.trace, "--intake", self.intake,
            "--classification", self.classification, code=code,
        )

    def ordering_options(self):
        return ("--intake", self.intake, "--classification", self.classification)

    def finish(self, *options, code=0, mock_write=None):
        return self.cli(
            "finalize", "--trace", self.trace, "--body", self.body,
            "--output", self.bundle, *options, code=code, mock_write=mock_write,
        )

    def ordered_trace(self, marker):
        return [
            command("g", "started"), command("g"),
            item("r", "reasoning"), item("a", "agent_message"),
            command("i", "started"), command("i", output=marker),
            command("e", "started"), command("e", "updated"), command("e", code=9),
        ]

    def test_intake_exact_bytes_private_mode_and_exclusive_destination(self):
        initial = self.spec.read_bytes()
        self.new_intake()
        self.assertEqual(self.intake.read_bytes(), initial)
        self.assertEqual(stat.S_IMODE(self.intake.stat().st_mode), 0o600)
        for path in (self.spec, self.intake, self.root / "existing-link", self.root / "alias"):
            if path.name == "existing-link":
                path.symlink_to(self.root / "nonexistent")
            elif path.name == "alias":
                os.link(self.spec, path)
            with self.subTest(path=path.name):
                self.cli("intake", "--spec", self.spec, "--output", path, code=2)
        self.assertEqual(self.intake.read_bytes(), initial)
        self.assertEqual(self.spec.read_bytes(), initial)
        self.assertFalse((self.root / "nonexistent").exists())

    def test_intake_rejects_invalid_spec_before_creating_output(self):
        invalid = [
            b'{"schema_version":1,"schema_version":1}',
            b'{"unused":1e309}', b"\xff", b"[]",
            json_data(dict(self.spec_value, schema_version=True)),
            json_data(dict(self.spec_value, run_id="  ")),
            json_data(dict(self.spec_value, scope={"chat": [], "project": None, "basis": "x"})),
            json_data(dict(self.spec_value, criteria=[])),
            json_data(dict(self.spec_value, criteria=self.spec_value["criteria"] * 2)),
            json_data(dict(self.spec_value, criteria=[{"id": "x", "expected": "x", "method": ""}])),
        ]
        for bad in invalid:
            with self.subTest(bad=bad):
                self.spec.write_bytes(bad)
                self.cli("intake", "--spec", self.spec, "--output", self.intake, code=2)
                self.assertFalse(self.intake.exists())

    def test_order_allows_governing_first_updates_and_passive_items(self):
        self.write_trace(self.ordered_trace(self.new_intake()))
        self.write_classification({"g": "governing", "i": "intake", "e": "evidence"})
        order = self.check()
        self.assertEqual(order["status"], "passed")
        self.assertEqual(order["facts"]["declared_commands"], 3)
        self.assertEqual(order["facts"]["evidence_commands"], 1)
        self.assertLess(order["facts"]["intake_completed_event"], order["facts"]["first_evidence_started_event"])
        for name in ("trace", "intake", "classification"):
            self.assertEqual(order[f"{name}_sha256"], digest(getattr(self, name)))
        self.assertIn("independent review", order["scope"])

    def test_earlier_and_overlapping_evidence_starts_fail(self):
        marker = self.new_intake()
        es, ec = command("e", "started"), command("e")
        ins, inc = command("i", "started"), command("i", output=marker)
        for events in ([es, ec, ins, inc], [ins, es, inc, ec]):
            self.write_trace(events)
            self.write_classification({"i": "intake", "e": "evidence"})
            self.assertEqual(self.check(code=1)["status"], "failed")

    def test_lifecycle_missing_duplicate_reused_or_outside_turn(self):
        marker = self.new_intake()
        ins, inc = command("i", "started"), command("i", output=marker)
        es, ec = command("e", "started"), command("e")
        cases = [
            ([ins, inc, ec], 3),
            ([ins, inc, command("e", "updated"), es, ec], 3),
            ([ins, inc, es], 3),
            ([ins, ins, inc, es, ec], 2),
            ([ins, inc, es, ec, ec], 2),
            ([ins, inc, es, ec, es], 2),
            ([ins, inc, item("e", "reasoning", "started"), es, ec], 2),
            ([ins, inc, {"type": "turn.completed"}, es, ec], 3),
        ]
        for events, code in cases:
            with self.subTest(events=events):
                self.write_trace(events)
                self.write_classification({"i": "intake", "e": "evidence"})
                self.check(code=code)

    def test_order_requires_complete_exact_bound_classification(self):
        marker = self.new_intake()
        self.write_trace(self.ordered_trace(marker))
        labels = {"g": "governing", "i": "intake", "e": "evidence"}
        cases = [
            ({"i": "intake", "e": "evidence"}, {}, 3),
            (dict(labels, e="other"), {}, 3),
            (dict(labels, ghost="evidence"), {}, 1),
            (dict(labels, g="intake"), {}, 2),
            (dict(labels, e=[]), {}, 2),
            (labels, {"trace_sha256": "a" * 64}, 1),
            (labels, {"intake_sha256": "a" * 64}, 1),
            (labels, {"intake_sha256": "invalid"}, 2),
        ]
        for commands, overrides, code in cases:
            with self.subTest(commands=commands, overrides=overrides):
                self.write_classification(commands, **overrides)
                self.check(code=code)
        self.classification.write_bytes(b'{"commands":{"e":"other","e":"evidence"}}')
        self.check(code=2)

    def test_unknown_actionable_items_make_order_partial(self):
        events = self.ordered_trace(self.new_intake())
        for shape in ("mcp_tool_call", "web_search", "file_change", "future_item"):
            with self.subTest(shape=shape):
                self.write_trace([*events, item("unknown", shape)])
                self.write_classification({"g": "governing", "i": "intake", "e": "evidence"})
                self.assertEqual(self.check(code=3)["status"], "partial")

    def test_intake_marker_has_exact_shape_and_is_unique(self):
        marker = self.new_intake()
        base = json.loads(marker)
        cases = [
            (marker, 1),
            (" " + marker, 0),
            (marker + marker, 0),
            (marker + "extra", 0),
            (json.dumps(dict(base, schema_version=True)), 0),
            (json.dumps(dict(base, run_id="wrong")), 0),
            (json.dumps(dict(base, unexpected="value")), 0),
            (marker.replace('{"type":', '{"type":"pia.intake","type":'), 0),
        ]
        for output, exit_code in cases:
            with self.subTest(output=output, exit_code=exit_code):
                self.write_trace([
                    command("i", "started"), command("i", code=exit_code, output=output),
                    command("e", "started"), command("e"),
                ])
                self.write_classification({"i": "intake", "e": "evidence"})
                self.check(code=1)
        self.write_trace([
            command("i", "started"), command("i", output=marker),
            command("e", "started"), command("e", output=marker),
        ])
        self.write_classification({"i": "intake", "e": "evidence"})
        self.check(code=1)

    def test_finalize_binds_actual_files_without_rewriting_narrative(self):
        self.write_trace(self.ordered_trace(self.new_intake()))
        self.write_classification({"g": "governing", "i": "intake", "e": "evidence"})
        self.write_execution(0)
        input_hashes = {key: digest(getattr(self, key)) for key in (
            "trace", "body", "execution", "intake", "classification",
        )}
        result = self.finish("--execution", self.execution, *self.ordering_options())
        manifest = json.loads((self.bundle / "manifest.json").read_bytes())
        self.assertEqual(result, manifest)
        self.assertEqual(manifest["tool_version"], "1.3.0")
        self.assertEqual(manifest["ordering"], "verified")
        self.assertEqual(manifest["input_hashes"], input_hashes)
        for name, expected in manifest["output_hashes"].items():
            self.assertEqual(digest(self.bundle / name), expected)
        self.assertEqual(
            {p.name for p in self.bundle.iterdir()},
            {"manifest.json", "audit.md", "claims.json", "receipt.json"},
        )
        self.assertEqual(stat.S_IMODE(self.bundle.stat().st_mode), 0o700)
        for path in self.bundle.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        report = (self.bundle / "audit.md").read_bytes()
        self.assertTrue(report.startswith(b"## Unverified narrative\n\n" + self.body_data + b"\n\n"))
        self.assertIn(b"Elapsed seconds: **0**", report)
        self.assertIn(b"Recorded failed shell calls: **1**", report)
        self.assertIn(b"All-tool total: **unknown**", report)
        self.assertNotIn(digest(self.bundle / "audit.md").encode(), report)
        claims = json.loads((self.bundle / "claims.json").read_bytes())
        self.assertEqual(claims["report_sha256"], digest(self.bundle / "audit.md"))
        self.assertEqual(claims["trace_sha256"], input_hashes["trace"])
        self.assertEqual(claims["claims"]["recorded_shell_calls"], 3)
        self.assertEqual(claims["claims"]["elapsed_seconds"], 0)
        verified = json.loads((self.bundle / "receipt.json").read_bytes())
        self.assertEqual(verified["claim_checks"]["recorded_failed_shell_calls"], "matched")
        self.assertEqual(verified["claim_checks"]["catalog_inspections"], "not_asserted")
        self.assertEqual(verified["order_check"]["status"], "passed")
        self.assertEqual(input_hashes, {key: digest(getattr(self, key)) for key in input_hashes})

    def test_finalize_without_order_preserves_legacy_trace_support_and_unknown_duration(self):
        self.write_trace([command("e", code=-9)])
        result = self.finish()
        self.assertEqual(result["ordering"], "not_checked")
        verified = json.loads((self.bundle / "receipt.json").read_bytes())
        self.assertIsNone(verified["order_check"])
        self.assertIsNone(verified["facts"]["elapsed_seconds"]["value"])
        self.assertEqual(verified["facts"]["recorded_failed_shell_calls"]["value"], 1)

    def test_finalize_invalid_or_partial_inputs_do_not_claim_destination(self):
        self.write_trace([command("e")], complete=False)
        self.finish(code=3)
        self.assertFalse(self.bundle.exists())
        self.trace.write_bytes(b'{"type":bad}')
        self.finish(code=2)
        self.assertFalse(self.bundle.exists())
        self.write_trace([command("e")])
        self.write_execution(0, trace_sha256="f" * 64)
        self.finish("--execution", self.execution, code=1)
        self.assertFalse(self.bundle.exists())
        self.write_execution(False)
        self.finish("--execution", self.execution, code=2)
        self.assertFalse(self.bundle.exists())
        self.finish("--intake", self.intake, code=2)
        self.finish("--classification", self.classification, code=2)
        self.assertFalse(self.bundle.exists())
        self.body.write_bytes(b"\xff")
        self.finish(code=2)
        self.assertFalse(self.bundle.exists())

    def test_finalize_refuses_unsuccessful_supplied_ordering(self):
        marker = self.new_intake()
        self.write_trace([
            command("i", "started"), command("e", "started"),
            command("i", output=marker), command("e"),
        ])
        self.write_classification({"i": "intake", "e": "evidence"})
        self.finish(*self.ordering_options(), code=1)
        self.assertFalse(self.bundle.exists())
        self.write_classification({"i": "intake", "e": "other"})
        self.finish(*self.ordering_options(), code=3)
        self.assertFalse(self.bundle.exists())

    def test_finalize_no_clobber_and_no_symlinked_output_ancestor(self):
        self.write_trace()
        self.bundle.mkdir()
        self.finish(code=2)
        self.assertEqual(list(self.bundle.iterdir()), [])
        self.bundle.rmdir()
        other = self.root / "other"
        other.mkdir()
        self.bundle.symlink_to(other, target_is_directory=True)
        self.finish(code=2)
        self.bundle = self.bundle / "child"
        self.finish(code=2)
        self.assertEqual(list(other.iterdir()), [])

    def test_post_preflight_input_mutation_cannot_commit(self):
        self.write_trace(self.ordered_trace(self.new_intake()))
        self.write_classification({"g": "governing", "i": "intake", "e": "evidence"})
        self.write_execution(0)
        actual_write = session.write_private
        options = ("--execution", self.execution, *self.ordering_options())

        for name in ("trace", "body", "execution", "intake", "classification"):
            with self.subTest(input=name):
                self.bundle = self.root / f"bundle-{name}"
                changed = getattr(self, name)
                original = changed.read_bytes()

                def mutate_after_receipt(path, *blocks):
                    actual_write(path, *blocks)
                    if path.name == "receipt.json":
                        changed.write_bytes(original + b"\n")

                self.finish(*options, code=1, mock_write=mutate_after_receipt)
                self.assertTrue((self.bundle / "receipt.json").exists())
                self.assertFalse((self.bundle / "manifest.json").exists())
                changed.write_bytes(original)
                self.finish(*options, code=2)
                self.assertFalse((self.bundle / "manifest.json").exists())

    def test_write_and_readback_failures_cannot_commit(self):
        self.write_trace()
        actual_write = session.write_private

        def failed_write(path, *blocks):
            if path.name == "claims.json":
                raise OSError(PRIVATE_TEXT)
            actual_write(path, *blocks)

        self.finish(code=2, mock_write=failed_write)
        self.assertTrue((self.bundle / "audit.md").is_file())
        self.assertFalse((self.bundle / "manifest.json").exists())
        self.bundle = self.root / "other-bundle"

        def corrupt_readback(path, *blocks):
            actual_write(path, b"corrupt" if path.name == "receipt.json" else blocks[0], *blocks[1:])

        self.finish(code=1, mock_write=corrupt_readback)
        self.assertFalse((self.bundle / "manifest.json").exists())

    def test_manifest_publication_failure_preserves_closed_uncommitted_outputs(self):
        self.write_trace()
        with patch.object(session.os, "link", side_effect=OSError(PRIVATE_TEXT)):
            self.finish(code=2, mock_write=session.write_private)
        self.assertEqual({path.name for path in self.bundle.iterdir()}, {
            "audit.md", "claims.json", "receipt.json",
        })


if __name__ == "__main__":
    unittest.main()
