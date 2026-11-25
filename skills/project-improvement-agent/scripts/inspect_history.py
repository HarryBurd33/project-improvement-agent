#!/usr/bin/env python3
"""Inspect committed, pinned history evidence without resuming its producer."""
import argparse
import hashlib
import math
import os
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True
import walk_history as walker

reader = walker.reader
require = walker.require
VERSION = "1.14.0"
READER_SHA256 = "93e171abe75a7e4e4413881a27af1d2899addc5eaa6353785995ed04e9dfad25"
PRODUCERS = {
    "1.9.0": ("475e661a2bb8cf7381f8fdca106f278ab94731963ae66914af506c836633921e",
              "aa20991c69b61c4d49ccdb827bd09d10ef7142a6"),
    "1.10.0": ("32ca30ef7804145495daf04463bf807f0ed2dc481c7c75b056ae969abbc806b5",
               "8dc22d9b0bf7c2011dd5f01133bef90188d4ce23"),
    "1.11.0": ("956e70e10fe8ca29b54b506cd85c83a8033437fa175121a4b2642a657553c46e",
               "53ecb693eb51b8d14d02abff5cb5503499763562"),
}

# Exact observed walker version, walker bytes and reader bytes select one profile.
EARLY_PRODUCERS = {
    ("1.6.0", "d79594ab1e1687784981631881828543a4b7a8f315b06573221e0292d1cb2f95",
     "6fdde60b719e2725a3c9c10a028ab6aad8b41df3b1bc31c30e3c39d2b1dfc743"):
        ("1.6.0", "v1.6.0", "45e589c72bbd2f141394ec9bceed61616f0e486c", True),
    ("1.6.0", "d79594ab1e1687784981631881828543a4b7a8f315b06573221e0292d1cb2f95",
     "5d7deaea2f26c240f89e6a513a4a6bf73ca549c029ad6b6fa7b02613a2524075"):
        ("1.7.0", "v1.7.0", "bd27cdcda687a4e50bc806b66ef13e87056ca8e6", True),
    ("1.7.1", "53facc5c07e0ee404f981d2812f402025140c24b851deb17dc75359066dbc98e",
     "5d7deaea2f26c240f89e6a513a4a6bf73ca549c029ad6b6fa7b02613a2524075"):
        ("1.7.0", "v1.8.0", "380078ae3a2609422193407f2676e63dea4aafdd", False),
}


# Explicit pre-release bytes; the released tag is only a reconstruction reference.
PREVIEW_SOURCE = ("1.6.0", "e1c0fd50891f288a92d43c882b8a4910afc863892d6f5da6d3c5eb8504ee2c39",
                  "6fdde60b719e2725a3c9c10a028ab6aad8b41df3b1bc31c30e3c39d2b1dfc743")


def producer_profile(state):
    version, source = state.get("walker_version"), state["source"]
    require(isinstance(version, str) and (version in PRODUCERS or any(key[0] == version for key in EARLY_PRODUCERS)),
            "unsupported_producer")
    require(isinstance(source, dict) and source.keys() == {"walker_sha256", "reader_sha256"}
            and all(isinstance(value, str) for value in source.values()), "unsupported_producer_source")
    if version in PRODUCERS:
        sha, commit = PRODUCERS[version]
        require(source == {"walker_sha256": sha, "reader_sha256": READER_SHA256}, "unsupported_producer_source")
        producer = {"walker_version": version, "reader_version": reader.VERSION,
                    "source": source, "released_commit": commit}
        profile = {"reader_version": reader.VERSION, "old_view": False, "reset_stage": False,
                   "prefix_only": version == "1.9.0", "unjournaled_timing": version != "1.11.0"}
    else:
        key = (version, source["walker_sha256"], source["reader_sha256"])
        if key == PREVIEW_SOURCE:
            producer = {"walker_version": version, "reader_version": "1.6.0", "source": source,
                        "compatibility": "explicit_prerelease", "compatible_release_tags": [],
                        "original_package_identity": "unverified",
                        "historical_plan_limits": {"max_bytes": 134217728}}
            profile = {"reader_version": "1.6.0", "old_view": True, "reset_stage": True,
                       "prefix_only": True, "unjournaled_timing": True, "max_plan_bytes": 134217728}
            return producer, profile
        require(key in EARLY_PRODUCERS, "unsupported_producer_source")
        reader_version, tag, commit, reset = EARLY_PRODUCERS[key]
        producer = {"walker_version": version, "reader_version": reader_version, "source": source,
                    "released_commit": commit, "compatible_release_tags": [tag],
                    "original_package_identity": "unverified"}
        profile = {"reader_version": reader_version, "old_view": True, "reset_stage": reset,
                   "prefix_only": True, "unjournaled_timing": True}
    return producer, profile


class ProfileProgress(walker.Progress):
    def __init__(self, plan, profile):
        super().__init__(plan)
        self.profile = profile

    def items(self, records, next_cursor):
        super().items(records, next_cursor)
        if self.profile["reset_stage"]:
            self.stage = 0

    def apply(self, plan, receipt, records, calls, exit_code):
        require(receipt["reader_version"] == self.profile["reader_version"], "receipt_reader_version_mismatch")
        # The raw historical header was checked after its exact receipt hash.
        # Adapt a copy for the current pure checker without modifying globals/files.
        checked = receipt
        if self.profile["reader_version"] != reader.VERSION:
            checked = {**receipt, "reader_version": reader.VERSION}
        super().apply(plan, checked, records, calls, exit_code)

    def view(self):
        view = super().view()
        if self.profile["old_view"]:
            del view["observation_sha256"]
        return view


def quiescent_marker(directory, budget):
    marker = directory / walker.INVOCATION_MARKER
    if not os.path.lexists(marker):
        return False
    value = reader.parse(walker.blob(marker, 4096, private=True, budget=budget), "invalid_invocation_marker")
    require(isinstance(value, dict) and {"pid", "started_at"} <= value.keys()
            and value.keys() <= {"pid", "started_at", "invocation_id", "nonce_sha256",
                                "terminal_state_sha256", "terminal_commitment"}
            and type(value["pid"]) is int and 0 < value["pid"] <= 2147483647
            and isinstance(value["started_at"], str), "invalid_invocation_marker")
    try:
        os.kill(value["pid"], 0)
    except ProcessLookupError:
        return True
    raise walker.Failure("inspection_origin_active")


def pending_slot(directory, state, progress, marker_present, budget):
    pending = state["pending"]
    if pending is None:
        return None
    require(marker_present, "pending_marker_missing")
    require(isinstance(pending, dict) and pending.keys() ==
            {"slot", "phase", "plan", "reserved_at", "reservation"}, "invalid_pending_reservation")
    selected, _ = progress.next_plan()
    slot = "probe-%04d" % (progress.used["probes"] + 1)
    require(selected is not None and pending["slot"] == slot and pending["phase"] == progress.phase
            and isinstance(pending["reserved_at"], str) and reader.validate_plan(pending["plan"]) == selected
            and reader.encoded(pending["plan"]) == reader.encoded(selected), "invalid_pending_reservation")
    expected = {"probes": 1, "received_bytes": selected["max_bytes"], "records": selected["max_records"],
                "elapsed_us": math.ceil(selected["max_seconds"] * walker.MICROS) + walker.DISPATCH_RESERVE}
    reservation = pending["reservation"]
    require(isinstance(reservation, dict) and reservation == expected
            and all(type(value) is int for value in reservation.values()), "invalid_pending_reservation")
    path = directory / slot
    if os.path.lexists(path):
        walker.private_directory(path)
        names = walker.directory_names(path, 2, budget)
        require(names <= {"receipt.json", "records.json"}, "unexpected_pending_files")
        for name in names:
            mode = (path / name).lstat().st_mode
            require(stat.S_ISREG(mode) and stat.S_IMODE(mode) == 0o600, "invalid_pending_file")
    return {"slot": slot, "outcome": "unknown", "excluded": True, "directory_present": path.exists()}


def replay_committed(directory, state, plan, budget, producer, profile):
    entries = state["journal"]
    require(isinstance(entries, list) and len(entries) <= 8 * walker.MAXIMA["max_probes"], "invalid_walk_journal")
    progress = ProfileProgress(plan, profile)
    progress.reset_scan()
    scope = {"thread_id": plan["thread_id"], "through_turn_id": plan["through_turn_id"]}
    if "after_turn_id" in plan:
        scope["after_turn_id"] = plan["after_turn_id"]
    projection = hashlib.sha256(reader.encoded(["committed-history-projection-v1", producer["source"], scope]))
    evidence = []
    item_ids = set()
    for entry in entries:
        budget.check()
        require(isinstance(entry, dict), "invalid_probe_entry")
        if entry.keys() == {"kind", "category", "duration_us"} and entry["kind"] == "time":
            progress.charge_time(entry["category"], entry["duration_us"])
            continue
        if entry == {"kind": "resume_inventory"}:
            progress.check_resume()
            continue
        if entry == {"kind": "finalization_time_uncertain"}:
            require(producer["walker_version"] == "1.11.0" and progress.phase == "done"
                    and progress.blocked is None, "invalid_finalization_stop")
            progress.blocked = "finalization_time_uncertain"
            continue
        require(entry.keys() == {"kind", "slot", "receipt_sha256", "records_sha256", "calls", "exit_code"}
                and entry["kind"] == "probe", "invalid_probe_entry")
        selected, _ = progress.next_plan()
        slot = "probe-%04d" % (progress.used["probes"] + 1)
        require(selected is not None and entry["slot"] == slot, "invalid_probe_order")
        path = directory / slot
        walker.private_directory(path)
        require(walker.directory_names(path, 2, budget) == {"receipt.json", "records.json"}, "unexpected_probe_files")
        receipt_raw = walker.blob(path / "receipt.json", 262144, private=True, budget=budget)
        records_raw = walker.blob(path / "records.json", 33554432, private=True, budget=budget)
        require(reader.digest(receipt_raw) == entry["receipt_sha256"]
                and reader.digest(records_raw) == entry["records_sha256"], "probe_evidence_hash_mismatch")
        receipt = reader.parse(receipt_raw, "invalid_saved_receipt")
        records = reader.parse(records_raw, "invalid_saved_records")
        require(isinstance(records, list) and receipt["records_sha256"] == entry["records_sha256"]
                and receipt["executable"] == state["executable"], "probe_evidence_binding_mismatch")
        budget.records += len(records)
        budget.probes += 1
        budget.check()
        progress.apply(selected, receipt, records, entry["calls"], entry["exit_code"])
        require(progress.blocked != "cleanup_uncertain", "unconfirmed_committed_probe")
        require(entry["exit_code"] != 0 or progress.blocked is None, "invalid_committed_observation")
        # Apply includes the released request/count/cursor and duplicate checks.
        for row in records:
            projection.update(reader.encoded(row))
            if row["type"] != "turn":
                item_ids.add((row["turn_id"], row["item_id"]))
        evidence.append({"slot": slot, "record_rows": len(records), "operation": selected["operation"],
                         "receipt": slot + "/receipt.json", "records": slot + "/records.json",
                         "receipt_sha256": entry["receipt_sha256"], "records_sha256": entry["records_sha256"]})
    # 1.9 and 1.10 recorded this timing-only classifier after the committed journal.
    # No other view field or producer discrepancy is waived.
    adapted = (profile["unjournaled_timing"] and progress.blocked is None
               and state["reason"] == "finalization_time_uncertain"
               and state["coverage"].get("blocked") == "finalization_time_uncertain")
    if adapted:
        progress.blocked = "finalization_time_uncertain"
    require(reader.encoded(state["coverage"]) == reader.encoded(progress.view()), "saved_coverage_mismatch")
    expected_status = ("complete_observed" if state["reason"] == "selected_scope_end"
                       and progress.phase == "done" and not progress.blocked else "partial")
    require(state["coverage_status"] == expected_status, "saved_status_mismatch")
    return progress, scope, evidence, len(item_ids), projection.hexdigest(), adapted


def inspect_run(path):
    budget = walker.VerificationBudget()
    directory = reader.canonical(path)
    walker.private_directory(directory)
    lock = walker.lock_directory(directory, False)
    try:
        require(walker.source_binding(budget) == {"walker_sha256": PRODUCERS["1.11.0"][0],
                                                 "reader_sha256": READER_SHA256}, "unsupported_inspection_engine")
        marker_present = quiescent_marker(directory, budget)
        raw = walker.blob(directory / "plan.json", reader.PLAN_MAX, private=True, budget=budget)
        state = reader.parse(walker.blob(directory / "state.json", 16777216, private=True, budget=budget), "invalid_walk_state")
        require(isinstance(state, dict) and type(state.get("schema_version")) is int
                and state["schema_version"] == 1, "unsupported_walk_schema")
        producer, profile = producer_profile(state)
        plan = walker.parse_plan(raw)
        require(plan["max_bytes"] <= profile.get("max_plan_bytes", walker.MAXIMA["max_bytes"]),
                "unsupported_producer_plan_limit")
        require(not profile["prefix_only"] or "after_turn_id" not in plan, "unsupported_producer_range")
        require(reader.encoded(state["plan"]) == reader.encoded(plan)
                and state["plan_sha256"] == reader.digest(raw), "walk_plan_mismatch")
        require(isinstance(state["coverage"], dict) and isinstance(state["reason"], str)
                and isinstance(state["executable"], str) and state["executable"], "invalid_walk_state")
        progress, scope, evidence, unique_items, digest, adapted = replay_committed(directory, state, plan, budget, producer, profile)
        pending = pending_slot(directory, state, progress, marker_present, budget)
        expected = walker.BASE_FILES | {row["slot"] for row in evidence}
        if marker_present:
            expected.add(walker.INVOCATION_MARKER)
        if pending and pending["directory_present"]:
            expected.add(pending["slot"])
        require(walker.directory_names(directory, walker.MAXIMA["max_probes"] + 5, budget) == expected,
                "unexpected_walk_files")
        incomplete = None
        unreached = [] if progress.inventory is not None else None
        if progress.inventory is not None and progress.turn_index < len(progress.inventory):
            incomplete = {"turn_id": progress.inventory[progress.turn_index]["turn_id"],
                          "retained_items": len(progress.identities), "next_cursor": progress.cursor}
            unreached = [row["turn_id"] for row in progress.inventory[progress.turn_index + 1:]]
        used = progress.used
        result = {"inspector_version": VERSION, "inspection_status": "verified_committed_evidence",
                  "producer": producer, "stored": {"coverage_status": state["coverage_status"],
                  "reason": state["reason"], "phase": progress.phase, "usage": state["coverage"]["usage"]},
                  "scope": scope, "committed": {"probes": used["probes"], "record_rows": used["accepted_records"],
                  "turn_metadata_rows": used["turn_metadata_records"], "items": used["selected_items"],
                  "unique_item_identities": unique_items, "user_items": used["user_items"],
                  "nonuser_items": used["nonuser_items"], "closed_item_scopes": progress.ends},
                  "inventory_status": "recorded" if progress.inventory is not None else "not_yet_established",
                  "observed_inventory": progress.inventory, "current_incomplete_scope": incomplete,
                  "unreached_item_scopes": unreached, "pending_operation": pending,
                  "committed_projection_sha256": digest, "evidence": evidence,
                  "timing_label_adapter_applied": adapted, "original_completion": "unverified",
                  "original_deadline_compliance": "unverified", "collection_resumed": False,
                  "snapshot_consistency": "unverified", "mutation_check": "turn_inventory_only",
                  "verification": budget.view()}
        budget.check()
        return result
    finally:
        os.close(lock)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect_run(args.run)
        code = 0
    except walker.Failure as error:
        result, code = {"inspection_status": "refused", "reason": str(error)}, 2
    except (OSError, KeyError, TypeError, ValueError, OverflowError, RecursionError, KeyboardInterrupt):
        result, code = {"inspection_status": "refused", "reason": "invalid_or_uncertain_committed_evidence"}, 2
    sys.stdout.write(reader.encoded(result).decode("ascii"))
    return code


if __name__ == "__main__":
    sys.exit(main())
