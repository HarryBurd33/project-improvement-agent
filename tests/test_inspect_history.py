"""Separate-process inspection of synthetic, source-bound committed histories."""
import fcntl
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

import test_walk_history as fixtures

INSPECTOR = fixtures.WALKER.with_name("inspect_history.py")


class InspectHistoryTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.WalkTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def inspect(self, expected=0, inject=None):
        launcher = [str(INSPECTOR)]
        if inject is not None:
            launcher = ["-c", "import sys,time\n"
                        + "sys.path.insert(0," + repr(str(INSPECTOR.parent)) + ")\n"
                        + "import inspect_history as inspector\n" + inject + "\n"
                        + "raise SystemExit(inspector.main(sys.argv[1:]))"]
        run = subprocess.run([sys.executable, "-B", *launcher, "--run", str(self.fixture.output)],
                             capture_output=True, text=True, env=self.fixture.env, timeout=20)
        self.assertEqual(run.returncode, expected, run.stdout + run.stderr)
        self.assertEqual(run.stderr, "")
        self.assertNotIn("Exact π", run.stdout)
        self.assertNotIn("PRIVATE_", run.stdout)
        result = json.loads(run.stdout)
        if expected:
            self.assertNotIn("committed_projection_sha256", result)
        return result

    def hashes(self):
        return {str(path.relative_to(self.fixture.output)): (hashlib.sha256(path.read_bytes()).hexdigest(),
                path.stat().st_mode) for path in self.fixture.output.rglob("*") if path.is_file()}

    def test_partial_and_terminal_are_committed_evidence_without_completion_claim(self):
        self.fixture.invoke(probes=2)
        before = self.hashes()
        calls = self.fixture.log.read_bytes()
        first = self.inspect()
        repeated = self.inspect()
        self.assertEqual(first["committed_projection_sha256"], repeated["committed_projection_sha256"])
        self.assertEqual(first["committed"]["items"], 2)
        self.assertEqual(first["committed"]["unique_item_identities"], 2)
        self.assertEqual(first["committed"]["user_items"], 1)
        self.assertEqual(first["current_incomplete_scope"]["next_cursor"], "one-next")
        self.assertEqual(first["unreached_item_scopes"], ["two"])
        self.assertEqual(first["original_completion"], "unverified")
        self.assertEqual(first["original_deadline_compliance"], "unverified")
        self.assertEqual(before, self.hashes())
        self.assertEqual(calls, self.fixture.log.read_bytes())
        self.fixture.invoke(resume=True)
        terminal = self.inspect()
        self.assertEqual(terminal["committed"]["items"], 3)
        self.assertEqual(len(terminal["committed"]["closed_item_scopes"]), 2)
        self.assertIsNone(terminal["current_incomplete_scope"])
        self.assertEqual(terminal["original_completion"], "unverified")
        self.assertFalse(terminal["collection_resumed"])

    def test_unestablished_inventory_is_explicitly_unknown(self):
        self.fixture.invoke(mode="long_inventory", probes=1)
        result = self.inspect()
        self.assertEqual(result["inventory_status"], "not_yet_established")
        self.assertIsNone(result["observed_inventory"])
        self.assertIsNone(result["unreached_item_scopes"])
        self.assertEqual(result["committed"]["items"], 0)

    def test_genuine_producer_rejected_page_is_not_credited(self):
        self.fixture.invoke(expected=1, mode="item_duplicate")
        before = self.hashes()
        result = self.inspect(expected=2)
        self.assertEqual(result["reason"], "invalid_committed_observation")
        self.assertEqual(before, self.hashes())

    def make_pending(self):
        fixture = self.fixture
        plan = {"schema_version": 1, "thread_id": "walk-test", "through_turn_id": "two", "max_probes": 24,
                "max_bytes": 4194304, "max_records": 100, "max_seconds": 30}
        fixture.plan.write_text(json.dumps(plan))
        wrapper = "import sys\nsys.path.insert(0," + repr(str(fixtures.WALKER.parent)) + ")\n" + """
import walk_history as walker
read_probe = walker.read_probe
calls = 0
def stop_after_reservation(*args):
    global calls
    calls += 1
    if calls == 3:
        raise SystemExit(75)
    return read_probe(*args)
walker.read_probe = stop_after_reservation
raise SystemExit(walker.main(sys.argv[1:]))
"""
        run = subprocess.run([sys.executable, "-B", "-c", wrapper, "--plan", str(fixture.plan),
                              "--output", str(fixture.output)], env=dict(fixture.env, PIA_WALK_MODE="normal"),
                             capture_output=True, text=True, timeout=12)
        self.assertEqual(run.returncode, 75, run.stdout + run.stderr)
        return fixture.state()["pending"]["slot"]

    def test_uncertain_pending_files_are_excluded_and_reservation_is_strict(self):
        slot = self.make_pending()
        path = self.fixture.output / slot
        path.rmdir()
        absent = self.inspect()
        self.assertEqual(absent["committed"]["items"], 2)
        self.assertEqual(absent["pending_operation"]["outcome"], "unknown")
        path.mkdir(mode=0o700)
        for filename in ("records.json", "receipt.json"):
            target = path / filename
            target.write_text("PRIVATE_UNCOMMITTED_NOT_JSON")
            target.chmod(0o600)
            before = self.hashes()
            result = self.inspect()
            self.assertEqual(result["committed_projection_sha256"], absent["committed_projection_sha256"])
            self.assertEqual(result["committed"]["items"], 2)
            self.assertEqual(before, self.hashes())
        state_path = self.fixture.output / "state.json"
        original = state_path.read_bytes()
        state = self.fixture.state()
        state["pending"]["reservation"]["probes"] = True
        state_path.write_text(json.dumps(state))
        self.assertEqual(self.inspect(expected=2)["reason"], "invalid_pending_reservation")
        state_path.write_bytes(original)

    def write_early_fixture(self, key):
        data = json.loads(Path(__file__).with_name("early_history_fixtures.json").read_bytes())[key]
        self.fixture.output = self.fixture.root / key.replace("/", "-")
        self.fixture.output.mkdir(mode=0o700)
        def write(name, raw):
            path = self.fixture.output / name
            path.write_bytes(raw)
            path.chmod(0o600)
        def encoded(value):
            return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")
        write(".lock", b"")
        write("plan.json", data["plan_json"].encode("utf-8"))
        write("state.json", encoded(data["state"]))
        for slot, probe in data["probes"].items():
            (self.fixture.output / slot).mkdir(mode=0o700)
            write(slot + "/receipt.json", encoded(probe["receipt"]))
            write(slot + "/records.json", encoded(probe["records"]))
        return data

    def test_exact_tagged_early_artifacts_preserve_versions_and_page_transitions(self):
        for tag in ("v1.6.0", "v1.7.0", "v1.8.0"):
            for phase in ("partial", "resumed"):
                with self.subTest(tag=tag, phase=phase):
                    data = self.write_early_fixture(tag + "/" + phase)
                    before = self.hashes()
                    result = self.inspect()
                    self.assertEqual(result["committed"]["items"], data["expected_items"])
                    self.assertEqual(len(result["committed"]["closed_item_scopes"]), data["expected_closed_scopes"])
                    self.assertEqual(result["producer"]["walker_version"], data["state"]["walker_version"])
                    self.assertEqual(result["producer"]["compatible_release_tags"], [tag])
                    self.assertEqual(result["producer"]["original_package_identity"], "unverified")
                    self.assertEqual(result["original_completion"], "unverified")
                    self.assertNotIn("observation_sha256", result)
                    self.assertEqual(before, self.hashes())
                    self.assertFalse(self.fixture.log.exists())
                    if phase == "resumed":
                        limits = [probe["receipt"]["plan"]["page_size"] for probe in data["probes"].values()
                                  if probe["receipt"]["plan"]["operation"] == "items"]
                        self.assertEqual(limits, [20, 1, 1, 1] if tag == "v1.8.0" else [20, 1, 1, 20])

    def test_early_profiles_reject_mixed_pair_wrong_receipt_and_extra_view_field(self):
        self.write_early_fixture("v1.7.0/partial")
        state_path = self.fixture.output / "state.json"
        original = state_path.read_bytes()
        state = self.fixture.state()
        state["source"]["reader_sha256"] = "0" * 64
        state_path.write_text(json.dumps(state))
        self.assertEqual(self.inspect(expected=2)["reason"], "unsupported_producer_source")
        state_path.write_bytes(original)
        state = self.fixture.state()
        state["coverage"]["observation_sha256"] = None
        state_path.write_text(json.dumps(state))
        self.assertEqual(self.inspect(expected=2)["reason"], "saved_coverage_mismatch")
        state_path.write_bytes(original)
        state = self.fixture.state()
        state["coverage"]["item_stage"] = 1
        state_path.write_text(json.dumps(state))
        self.assertEqual(self.inspect(expected=2)["reason"], "saved_coverage_mismatch")
        state_path.write_bytes(original)
        state = self.fixture.state()
        entry = next(entry for entry in state["journal"] if entry["kind"] == "probe")
        receipt_path = self.fixture.output / entry["slot"] / "receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt["reader_version"] = "1.9.0"
        receipt_path.write_text(json.dumps(receipt))
        entry["receipt_sha256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        state_path.write_text(json.dumps(state))
        self.assertEqual(self.inspect(expected=2)["reason"], "receipt_reader_version_mismatch")

    def test_corruption_unknown_sources_locks_and_limits_refuse_without_digest(self):
        self.fixture.invoke(probes=2)
        path = self.fixture.output / "probe-0002/records.json"
        original = path.read_bytes()
        path.write_bytes(original + b" ")
        self.assertEqual(self.inspect(expected=2)["reason"], "probe_evidence_hash_mismatch")
        path.write_bytes(original)
        state_path = self.fixture.output / "state.json"
        raw = state_path.read_bytes()
        state = self.fixture.state()
        state["source"]["walker_sha256"] = "0" * 64
        state_path.write_text(json.dumps(state))
        self.assertEqual(self.inspect(expected=2)["reason"], "unsupported_producer_source")
        state_path.write_bytes(raw)
        before = self.hashes()
        with (self.fixture.output / ".lock").open("rb") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.inspect(expected=2)["reason"], "walk_writer_active")
        small = self.inspect(expected=2, inject='inspector.walker.VERIFY_LIMITS = {**inspector.walker.VERIFY_LIMITS, "bytes": 1}')
        self.assertEqual(small["reason"], "verification_byte_limit")
        slow = self.inspect(expected=2, inject="""
inspector.walker.VERIFY_LIMITS = {**inspector.walker.VERIFY_LIMITS, "seconds": 0.1}
replay = inspector.replay_committed
def slow_replay(*args):
    time.sleep(0.15)
    return replay(*args)
inspector.replay_committed = slow_replay
""")
        self.assertEqual(slow["reason"], "verification_wall_limit")
        self.assertEqual(before, self.hashes())


if __name__ == "__main__":
    unittest.main()
