#!/usr/bin/env python3
"""Walk one closed Codex history prefix using bounded, private reader receipts."""
import argparse
import fcntl
import hashlib
import math
import os
from pathlib import Path
import signal
import stat
import sys
import time
import uuid

sys.dont_write_bytecode = True
import read_history as reader


VERSION = "1.11.0"
MAXIMA = {"max_probes": 1024, "max_bytes": 536870912, "max_seconds": 900, "max_records": 20000}
REQUIRED = {"schema_version", "thread_id", "through_turn_id", *MAXIMA}
LARGE_BATCH_STRATEGY = "bounded_large_pages"
STRATEGIES = ("standard_only", "standard_then_single_then_large", LARGE_BATCH_STRATEGY)
ITEM_PAGE_SIZE = reader.DEFAULTS["page_size"]
TERMINAL = {"completed", "interrupted", "failed"}
MICROS = 1000000
CLEANUP_RESERVE = math.ceil(reader.CLEANUP_SECONDS * MICROS)
PERSISTENCE_RESERVE = 250000
DISPATCH_RESERVE = CLEANUP_RESERVE + 2 * PERSISTENCE_RESERVE
INVOCATION_MARKER = ".invocation"
BASE_FILES = {"plan.json", "state.json", ".lock"}
VERIFY_LIMITS = {"seconds": 15, "bytes": 536870912, "records": 20000, "probe_receipts": 1024}
require = reader.require
Failure = reader.ReadFailure


def blob(path, limit, private=False, budget=None):
    if budget is not None:
        return budget.read(path, limit, private)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        mode = os.fstat(stream.fileno()).st_mode
        require(stat.S_ISREG(mode) and (not private or stat.S_IMODE(mode) == 0o600), "invalid_private_file")
        data = stream.read(limit + 1)
    require(len(data) <= limit, "state_file_too_large")
    return data


def parse_plan(raw):
    value = reader.parse(raw, "invalid_walk_plan_json")
    require(isinstance(value, dict) and REQUIRED <= value.keys()
            and value.keys() <= REQUIRED | {"page_strategy", "after_turn_id"}, "invalid_walk_plan_fields")
    plan = {"page_strategy": "standard_only", **value}
    require(type(plan["schema_version"]) is int and plan["schema_version"] == 1, "invalid_walk_plan_version")
    require(reader.identifier(plan["thread_id"]) and reader.identifier(plan["through_turn_id"]), "invalid_walk_scope")
    require("after_turn_id" not in plan or reader.identifier(plan["after_turn_id"]), "invalid_walk_after_turn")
    require(plan["page_strategy"] in STRATEGIES, "invalid_walk_strategy")
    for name, maximum in MAXIMA.items():
        number = plan[name]
        require(type(number) is int and 1 <= number <= maximum, "invalid_walk_" + name)
    return plan


def private_directory(path):
    require(stat.S_IMODE(path.lstat().st_mode) == 0o700 and path.is_dir() and not path.is_symlink(),
            "invalid_private_directory")


def publish(directory, name, raw, replace=False):
    target = directory / name
    if replace:
        temporary = directory / (".state-" + uuid.uuid4().hex)
    else:
        temporary = target
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, target)
        fd = os.open(directory, os.O_DIRECTORY | os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if replace and temporary.exists():
            temporary.unlink()
    return reader.digest(raw)


def source_binding(budget=None):
    if budget is not None:
        return {"walker_sha256": reader.digest(blob(Path(__file__), 1048576, budget=budget)),
                "reader_sha256": reader.digest(blob(Path(reader.__file__), 1048576, budget=budget))}
    return {"walker_sha256": reader.digest(Path(__file__).read_bytes()),
            "reader_sha256": reader.digest(Path(reader.__file__).read_bytes())}


def exact_count(value, maximum):
    require(type(value) is int and 0 <= value <= maximum, "invalid_probe_counter")
    return value


class Progress:
    def __init__(self, plan):
        self.plan = plan
        # Canonical JSON lines bind the logical scope, inventory and retained rows.
        # Probe sizes, attempts, runtime and resume boundaries do not describe content.
        scope = ["closed-walk-projection-v1", plan["thread_id"], plan["through_turn_id"]]
        if "after_turn_id" in plan:
            scope = ["closed-walk-range-v1", plan["thread_id"], plan["after_turn_id"], plan["through_turn_id"]]
        self.observation = hashlib.sha256(reader.encoded(scope))
        self.anchor = None
        self.phase = "inventory"
        self.cursor = None
        self.cursors = {None}
        self.scanning = []
        self.initial_scan_resumed = False
        self.inventory = None
        self.turn_index = 0
        self.identities = set()
        self.stage = 0
        self.batch_limit = ITEM_PAGE_SIZE
        self.ends = []
        self.blocked = None
        self.provider_version = None
        self.used = dict(probes=0, received_bytes=0, stdout_bytes=0, stderr_bytes=0, elapsed_us=0,
                         accepted_records=0, selected_items=0, user_items=0, nonuser_items=0,
                         turn_metadata_records=0, initialize_calls=0, initialized_notifications=0,
                         source_list_calls=0, ignored_notifications=0, failed_probes=0,
                         reader_elapsed_us=0, orchestration_elapsed_us=0, finalization_reserve_us=0)

    def check_resume(self):
        require(self.phase != "done" and not self.blocked, "invalid_resume_checkpoint")
        if self.inventory is None:
            require(self.phase == "inventory", "invalid_resume_checkpoint")
            self.initial_scan_resumed = True
        else:
            self.phase = "resume_inventory"
            self.reset_scan()

    def reset_scan(self):
        self.scanning = []
        self.scan_cursor = None
        self.scan_cursors = {None}
        self.scan_ids = set()

    def next_plan(self):
        p = self.plan
        if self.blocked or self.phase == "done":
            return None, self.blocked or "selected_scope_end"
        if self.used["probes"] >= p["max_probes"]:
            return None, "probe_limit"
        records = p["max_records"] - self.used["accepted_records"]
        if records <= 0:
            return None, "record_limit"
        bytes_left = p["max_bytes"] - self.used["received_bytes"]
        if bytes_left <= 0:
            return None, "byte_limit"
        time_left = p["max_seconds"] * MICROS - self.used["elapsed_us"]
        if time_left <= DISPATCH_RESERVE:
            return None, "wall_limit"
        items = self.phase == "items"
        stage = self.stage if items else 0
        standard = reader.DEFAULTS["max_bytes"]
        if items and p["page_strategy"] == LARGE_BATCH_STRATEGY:
            mode = "large_batch_page"
            limit = min(records, self.batch_limit)
        else:
            mode = "large_single_page" if stage == 2 else "standard"
            limit = 1 if stage else min(records, ITEM_PAGE_SIZE)
        maximum = min(bytes_left, standard if mode == "standard" else reader.LARGE_MAX_BYTES)
        if mode != "standard" and maximum <= standard:
            return None, "remaining_budget_cannot_fund_large_read"
        probe = {"schema_version": 1, "thread_id": p["thread_id"], "operation": "items" if items else "turns",
                 "turn_id": self.inventory[self.turn_index]["turn_id"] if items else None,
                 "cursor": self.cursor if items else self.scan_cursor, "direction": "asc",
                 "page_size": limit, "max_pages": 1, "max_records": limit, "max_bytes": maximum,
                 "max_seconds": min(15, (time_left - DISPATCH_RESERVE) / MICROS), "read_mode": mode}
        return reader.validate_plan(probe), None

    def scan(self, records, next_cursor):
        after = self.plan.get("after_turn_id")
        for row in records:
            turn = row["turn_id"]
            require(row["type"] == "turn" and reader.identifier(turn) and turn not in self.scan_ids,
                    "duplicate_or_invalid_turn")
            self.scan_ids.add(turn)
            if after is None or after in self.scan_ids:
                require(row["status"] in TERMINAL and type(row["completed_at_seconds"]) is int,
                        "nonterminal_selected_turn")
            self.scanning.append(row)
            if turn == self.plan["through_turn_id"]:
                anchor = None
                selected = self.scanning.copy()
                if after is not None:
                    require(after in self.scan_ids, "after_turn_missing_or_reversed")
                    index = next(index for index, value in enumerate(selected) if value["turn_id"] == after)
                    anchor = selected[index]
                    selected = selected[index + 1:]
                if self.phase == "inventory":
                    self.inventory = selected
                    self.anchor = anchor
                    if anchor is not None:
                        self.observation.update(reader.encoded(anchor))
                    for turn_record in self.inventory:
                        self.observation.update(reader.encoded(turn_record))
                    self.phase = ("resume_inventory" if self.initial_scan_resumed else
                                  "items" if self.inventory else "final_inventory")
                else:
                    require(selected == self.inventory and anchor == self.anchor, "selected_inventory_changed")
                    self.phase = ("done" if self.phase == "final_inventory" else
                                  "items" if self.turn_index < len(self.inventory) else "final_inventory")
                self.reset_scan()
                return
        require(next_cursor is not None, "cutoff_missing")
        require(next_cursor not in self.scan_cursors, "inventory_cursor_cycle")
        self.scan_cursor = next_cursor
        self.scan_cursors.add(next_cursor)

    def items(self, records, next_cursor):
        turn = self.inventory[self.turn_index]["turn_id"]
        keys = {row["item_id"] for row in records}
        require(len(keys) == len(records) and all(reader.identifier(key) for key in keys)
                and all(row["turn_id"] == turn and row["type"] in reader.ITEMS for row in records)
                and not keys & self.identities, "duplicate_or_wrong_item")
        require(next_cursor is None or next_cursor not in self.cursors, "item_cursor_cycle")
        for row in records:
            self.observation.update(reader.encoded(row))
        self.identities.update(keys)
        self.used["selected_items"] += len(records)
        users = sum(row["type"] == "userMessage" for row in records)
        self.used["user_items"] += users
        self.used["nonuser_items"] += len(records) - users
        # A successful fallback establishes a workable page size for this turn.
        # Start each new cursor with the standard byte cap, including after replay.
        self.stage = 1 if self.stage and next_cursor is not None else 0
        self.batch_limit = ITEM_PAGE_SIZE
        if next_cursor is not None:
            self.cursor = next_cursor
            self.cursors.add(next_cursor)
            return
        self.ends.append({"turn_id": turn, "item_count": len(self.identities), "next_cursor": None})
        self.turn_index += 1
        self.cursor = None
        self.cursors = {None}
        self.identities.clear()
        if self.turn_index == len(self.inventory):
            self.phase = "final_inventory"
            self.reset_scan()

    def charge_time(self, category, duration):
        require(category in ("orchestration_elapsed_us", "finalization_reserve_us")
                and type(duration) is int and duration > 0, "invalid_walk_time_charge")
        if category == "finalization_reserve_us":
            require(duration <= PERSISTENCE_RESERVE, "invalid_walk_finalization_reserve")
        self.used[category] += duration
        self.used["elapsed_us"] += duration
        if self.used["elapsed_us"] > self.plan["max_seconds"] * MICROS:
            self.blocked = "elapsed_accounting_exceeded"

    def apply(self, plan, receipt, records, calls, exit_code):
        require(receipt["plan"] == plan and receipt["plan_sha256"] == reader.digest(reader.encoded(plan))
                and receipt["reader_version"] == reader.VERSION and receipt["transport"] == "codex app-server --stdio",
                "probe_plan_mismatch")
        require(type(exit_code) is int and exit_code in (0, 1) and isinstance(records, list), "invalid_probe_result")
        size = exact_count(receipt["accepted_records"], plan["max_records"])
        require(size == len(records), "probe_record_count_mismatch")
        require(receipt["attempted_page_count"] in (0, 1)
                and receipt["attempted_page_count"] == len(receipt["requests"]), "probe_request_count_mismatch")
        requires_items = plan["operation"] == "items"
        params = {"threadId": plan["thread_id"], "limit": plan["page_size"], "sortDirection": "asc"}
        if plan["cursor"] is not None:
            params["cursor"] = plan["cursor"]
        if requires_items:
            params["turnId"] = plan["turn_id"]
        else:
            params["itemsView"] = "notLoaded"
        if receipt["requests"]:
            require(receipt["requests"] == [{"id": 2, "method": "thread/" + plan["operation"] + "/list", "params": params}],
                    "probe_request_scope_mismatch")
        require(isinstance(calls, list) and calls in [[], ["initialize"], ["initialize", "initialized"],
                ["initialize", "initialized", "thread/" + plan["operation"] + "/list"]]
                and len(calls[2:]) == receipt["attempted_page_count"], "probe_protocol_mismatch")
        channel = {name: exact_count(receipt[name], plan["max_bytes"]) for name in ("stdout_bytes", "stderr_bytes")}
        received = exact_count(receipt["received_bytes"], plan["max_bytes"])
        require(sum(channel.values()) == received, "probe_byte_count_mismatch")
        elapsed = receipt["elapsed_seconds"]
        require(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0, "invalid_probe_elapsed")
        actual_us = math.ceil(elapsed * MICROS)
        notifications = exact_count(receipt["notifications"], received)
        pages = receipt["accepted_pages"]
        next_cursor = receipt["last_safe_cursor"]
        require(isinstance(pages, list) and len(pages) <= 1 and len(pages) == receipt["accepted_page_count"],
                "invalid_accepted_pages")
        if pages:
            require(pages == [{"record_count": size, "request_id": 2, "next_cursor": next_cursor}]
                    and receipt["attempted_page_count"] == 1
                    and (next_cursor is None or (size and reader.valid_cursor(next_cursor) and next_cursor != plan["cursor"])),
                    "invalid_accepted_cursor")
        else:
            require(not size and next_cursor == plan["cursor"] and exit_code == 1, "unaccepted_cursor_advanced")
        if exit_code == 0:
            require(receipt["status"] == ("complete" if next_cursor is None else "partial"), "invalid_probe_status")
        for key, amount in {"probes": 1, "received_bytes": received, "elapsed_us": actual_us, "reader_elapsed_us": actual_us,
                            "accepted_records": size, "turn_metadata_records": 0 if requires_items else size,
                            "ignored_notifications": notifications, "failed_probes": exit_code,
                            "initialize_calls": calls.count("initialize"), "initialized_notifications": calls.count("initialized"),
                            "source_list_calls": len(calls[2:]), **channel}.items():
            self.used[key] += amount
        cleanup = receipt["cleanup"]
        require(type(cleanup["started"]) is bool, "invalid_probe_cleanup")
        if cleanup["started"] and not (cleanup["reaped"] is True and cleanup["group_gone"] is True):
            self.blocked = "cleanup_uncertain"
            return
        if self.used["elapsed_us"] > self.plan["max_seconds"] * MICROS:
            self.blocked = "elapsed_accounting_exceeded"
            return
        version = receipt["app_server_version"]
        if self.provider_version is None:
            self.provider_version = version
        elif version is not None and version != self.provider_version:
            self.blocked = "provider_version_changed"
            return
        if exit_code:
            byte_limited_item = requires_items and not pages and receipt["reason"] == "byte_limit"
            if byte_limited_item and plan["read_mode"] == "large_batch_page" and plan["page_size"] > 1:
                self.batch_limit = plan["page_size"] // 2
            elif byte_limited_item and self.plan["page_strategy"] == STRATEGIES[1] and self.stage < 2:
                self.stage += 1
                if self.stage == 1 and plan["page_size"] == 1:
                    self.stage = 2
            else:
                self.blocked = receipt["reason"]
            return
        try:
            if requires_items:
                self.items(records, next_cursor)
            else:
                self.scan(records, next_cursor)
        except Failure as error:
            self.blocked = str(error)

    def view(self):
        scope = {}
        if "after_turn_id" in self.plan:
            scope = {"range": {"after_turn_id": self.plan["after_turn_id"],
                               "through_turn_id": self.plan["through_turn_id"],
                               "start_exclusive": True, "end_inclusive": True},
                     "observed_anchor": self.anchor, "earlier_item_coverage": "excluded"}
        return {**scope, "phase": self.phase,
                "observation_sha256": self.observation.hexdigest() if self.phase == "done" and not self.blocked else None,
                "observed_inventory": self.inventory, "closed_item_scopes": self.ends,
                "scope_excludes_after_cutoff": True, "blocked": self.blocked, "item_cursor": self.cursor,
                "inventory_cursor": self.scan_cursor, "item_stage": self.stage, "item_batch_limit": self.batch_limit,
                "next_turn_index": self.turn_index, "initial_scan_resumed": self.initial_scan_resumed, "usage": self.used, "provider_version": self.provider_version,
                "snapshot_consistency": "unverified", "mutation_check": "turn_inventory_only"}


class CountingPeer(reader.Peer):
    calls = None

    def call(self, request):
        self.calls.append(request["method"])
        return super().call(request)


def read_probe(command, plan):
    calls = []
    original = reader.Peer
    CountingPeer.calls = calls
    reader.Peer = CountingPeer
    previous = signal.signal(signal.SIGTERM, reader.interrupted)
    try:
        receipt, records, code = reader.collect(command, plan, reader.digest(reader.encoded(plan)))
        return receipt, records, calls, code
    finally:
        reader.Peer = original
        CountingPeer.calls = None
        signal.signal(signal.SIGTERM, previous)


def persist_state(directory, state, progress, reason):
    state["coverage"] = progress.view()
    complete = reason == "selected_scope_end" and progress.phase == "done" and not progress.blocked
    state["coverage_status"] = "complete_observed" if complete else "partial"
    state["reason"] = reason
    return publish(directory, "state.json", reader.encoded(state), replace=True)


def replay(directory, state, plan, raw, budget=None):
    require(state["schema_version"] == 1 and state["walker_version"] == VERSION and state["plan"] == plan
            and state["plan_sha256"] == reader.digest(raw) and state["source"] == source_binding(budget), "walk_binding_mismatch")
    require(state["pending"] is None, "uncertain_pending_probe")
    entries = state["journal"]
    require(isinstance(entries, list) and len(entries) <= 8 * MAXIMA["max_probes"], "invalid_walk_journal")
    progress = Progress(plan)
    progress.reset_scan()
    names = BASE_FILES | {INVOCATION_MARKER}
    for entry in entries:
        if budget is not None:
            budget.check()
        if entry == {"kind": "finalization_time_uncertain"}:
            require(progress.phase == "done" and progress.blocked is None, "invalid_finalization_stop")
            progress.blocked = "finalization_time_uncertain"
            continue
        if isinstance(entry, dict) and entry.keys() == {"kind", "category", "duration_us"} and entry["kind"] == "time":
            progress.charge_time(entry["category"], entry["duration_us"])
            continue
        if entry == {"kind": "resume_inventory"}:
            progress.check_resume()
            continue
        require(entry.keys() == {"kind", "slot", "receipt_sha256", "records_sha256", "calls", "exit_code"}
                and entry["kind"] == "probe", "invalid_probe_entry")
        probe, _ = progress.next_plan()
        require(probe is not None, "unexpected_probe_after_stop")
        slot = "probe-%04d" % (progress.used["probes"] + 1)
        require(entry["slot"] == slot, "invalid_probe_order")
        names.add(slot)
        root = directory / slot
        private_directory(root)
        require(directory_names(root, 2, budget) == {"records.json", "receipt.json"}, "unexpected_probe_files")
        receipt_raw = blob(root / "receipt.json", 256 * 1024, private=True, budget=budget)
        records_raw = blob(root / "records.json", 32 * 1024 * 1024, private=True, budget=budget)
        require(reader.digest(receipt_raw) == entry["receipt_sha256"]
                and reader.digest(records_raw) == entry["records_sha256"], "probe_evidence_hash_mismatch")
        receipt = reader.parse(receipt_raw, "invalid_saved_receipt")
        records = reader.parse(records_raw, "invalid_saved_records")
        if budget is not None:
            require(isinstance(records, list), "invalid_saved_records")
            budget.records += len(records)
            budget.probes += 1
            budget.check()
        require(receipt["records_sha256"] == entry["records_sha256"]
                and receipt["executable"] == state["executable"], "probe_evidence_binding_mismatch")
        progress.apply(probe, receipt, records, entry["calls"], entry["exit_code"])
    require(directory_names(directory, MAXIMA["max_probes"] + len(BASE_FILES) + 1, budget) == names, "unexpected_walk_files")
    require(state["coverage"] == progress.view(), "saved_coverage_mismatch")
    require((state["coverage_status"] == "complete_observed") == (progress.phase == "done" and not progress.blocked),
            "saved_completion_mismatch")
    return progress


def lock_directory(directory, create):
    flags = os.O_RDWR | os.O_NOFOLLOW
    fd = os.open(directory / ".lock", flags | (os.O_CREAT | os.O_EXCL if create else 0), 0o600)
    try:
        if create:
            os.fchmod(fd, 0o600)
        require(stat.S_IMODE(os.fstat(fd).st_mode) == 0o600 and stat.S_ISREG(os.fstat(fd).st_mode),
                "invalid_walk_lock")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Failure("walk_writer_active") from None
        return fd
    except BaseException:
        os.close(fd)
        raise


class ActiveClock:
    def __init__(self, start, progress, journal):
        self.start = start
        self.progress = progress
        self.journal = journal
        self.prior = progress.used["elapsed_us"]
        self.limit = progress.plan["max_seconds"] * MICROS

    def elapsed(self):
        return self.prior + (time.monotonic_ns() - self.start + 999) // 1000

    def charge(self, category, amount):
        if amount > 0:
            self.progress.charge_time(category, amount)
            self.journal.append({"kind": "time", "category": category, "duration_us": amount})

    def observe(self):
        self.charge("orchestration_elapsed_us", self.elapsed() - self.progress.used["elapsed_us"])

    def permits_dispatch(self, probe):
        reserved = math.ceil(probe["max_seconds"] * MICROS) + CLEANUP_RESERVE + PERSISTENCE_RESERVE
        return self.elapsed() + reserved <= self.limit

    def finish(self):
        self.observe()
        remaining = self.limit - self.progress.used["elapsed_us"]
        self.charge("finalization_reserve_us", min(PERSISTENCE_RESERVE, remaining))


def walk(args):
    active_start = time.monotonic_ns()
    create = args.resume is None
    if create:
        raw = blob(reader.canonical(args.plan), reader.PLAN_MAX)
        plan = parse_plan(raw)
        command = reader.executable()
        directory, directory_fd = reader.open_output(args.output)
        os.close(directory_fd)
    else:
        directory = reader.canonical(args.resume)
        private_directory(directory)
    lock = lock_directory(directory, create)
    marker = directory / INVOCATION_MARKER
    validated_state = False
    own_marker = False
    try:
        if not create:
            raw = blob(directory / "plan.json", reader.PLAN_MAX, private=True)
            plan = parse_plan(raw)
            state = reader.parse(blob(directory / "state.json", 16 * 1024 * 1024, private=True), "invalid_walk_state")
            require(state["pending"] is None, "uncertain_pending_probe")
        require(not os.path.lexists(marker), "uncertain_previous_invocation")
        nonce = os.urandom(32).hex()
        invocation = {"started_at": reader.utc(), "pid": os.getpid(), "invocation_id": uuid.uuid4().hex,
                      "nonce_sha256": reader.digest(nonce.encode("ascii"))}
        publish(directory, INVOCATION_MARKER, reader.encoded(invocation))
        own_marker = True
        if create:
            publish(directory, "plan.json", raw)
            progress = Progress(plan)
            progress.reset_scan()
            state = {"schema_version": 1, "walker_version": VERSION, "plan": plan, "plan_sha256": reader.digest(raw),
                     "source": source_binding(), "executable": command, "journal": [], "pending": None,
                     "started_at": reader.utc()}
        else:
            progress = replay(directory, state, plan, raw)
            command = reader.executable()
            require(command == state["executable"], "walk_executable_changed")
        validated_state = True
        clock = ActiveClock(active_start, progress, state["journal"])
        clock.observe()
        if not create and progress.used["probes"] and progress.next_plan()[0] is not None:
            progress.check_resume()
            state["journal"].append({"kind": "resume_inventory"})
        persist_state(directory, state, progress, "ready")
        for _ in range(args.max_probes_this_run):
            clock.observe()
            selected, reason = progress.next_plan()
            if selected is None:
                break
            slot = "probe-%04d" % (progress.used["probes"] + 1)
            state["pending"] = {"slot": slot, "phase": progress.phase, "plan": selected,
                                "reserved_at": reader.utc(), "reservation": {"probes": 1,
                                 "received_bytes": selected["max_bytes"], "records": selected["max_records"],
                                 "elapsed_us": math.ceil(selected["max_seconds"] * MICROS) + DISPATCH_RESERVE}}
            persist_state(directory, state, progress, "probe_pending")
            probe_dir = directory / slot
            probe_dir.mkdir(mode=0o700)
            probe_dir.chmod(0o700)
            if not clock.permits_dispatch(selected):
                probe_dir.rmdir()
                state["pending"] = None
                reason = "insufficient_time_after_predispatch"
                break
            receipt, records, calls, code = read_probe(command, selected)
            records_sha = publish(probe_dir, "records.json", reader.encoded(records))
            receipt["records_sha256"] = records_sha
            receipt_sha = publish(probe_dir, "receipt.json", reader.encoded(receipt))
            progress.apply(selected, receipt, records, calls, code)
            state["journal"].append({"kind": "probe", "slot": slot, "receipt_sha256": receipt_sha,
                                     "records_sha256": records_sha, "calls": calls, "exit_code": code})
            state["pending"] = None
            clock.observe()
            persist_state(directory, state, progress, progress.blocked or "probe_committed")
        else:
            reason = "invocation_probe_limit"
        persist_state(directory, state, progress, "finalizing")
        clock.finish()
        if progress.blocked:
            reason = progress.blocked
        elif progress.phase == "done":
            reason = "selected_scope_end"
        state_sha = persist_state(directory, state, progress, reason)
        elapsed = clock.elapsed()
        if elapsed > progress.used["elapsed_us"]:
            clock.observe()
            if progress.blocked is None and progress.phase == "done":
                state["journal"].append({"kind": "finalization_time_uncertain"})
            progress.blocked = progress.blocked or "finalization_time_uncertain"
            reason = progress.blocked
            state_sha = persist_state(directory, state, progress, reason)
            # Keep the marker so another invocation cannot refund unobserved
            # persistence time or take durable completion from this boundary.
            finalization_uncertain = True
        else:
            marker.unlink()
            finalization_uncertain = False
        witness = {}
        if (finalization_uncertain and progress.phase == "done"
                and progress.blocked == "finalization_time_uncertain"):
            invocation.update(terminal_state_sha256=state_sha,
                              terminal_commitment=reader.digest(reader.encoded([invocation["invocation_id"], nonce, state_sha])))
            marker_sha = publish(directory, INVOCATION_MARKER, reader.encoded(invocation), replace=True)
            # Release only after the last real durable write and within the original deadline.
            if clock.elapsed() <= clock.limit:
                witness = {"finalization_witness": {"schema_version": 1, "nonce": nonce,
                           "state_sha256": state_sha, "marker_sha256": marker_sha}}
        return ({**witness, "coverage_status": "partial" if finalization_uncertain else state["coverage_status"],
                "reason": reason, "state": str(directory / "state.json"), "state_sha256": state_sha,
                "usage": progress.used, "measured_elapsed_us_before_summary": clock.elapsed(),
                "snapshot_consistency": "unverified", "mutation_check": "turn_inventory_only",
                **({"range": progress.view()["range"], "earlier_item_coverage": "excluded"}
                   if "after_turn_id" in plan else {})},
                int(bool(progress.blocked or finalization_uncertain)))
    finally:
        if own_marker and not validated_state:
            marker.unlink()
        os.close(lock)


class VerificationBudget:
    def __init__(self):
        self.start = time.monotonic()
        self.received = 0
        self.records = 0
        self.probes = 0

    def check(self):
        require(time.monotonic() - self.start <= VERIFY_LIMITS["seconds"], "verification_wall_limit")
        require(self.received <= VERIFY_LIMITS["bytes"], "verification_byte_limit")
        require(self.records <= VERIFY_LIMITS["records"], "verification_record_limit")
        require(self.probes <= VERIFY_LIMITS["probe_receipts"], "verification_probe_limit")

    def read(self, path, limit, private):
        self.check()
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode) and (not private or stat.S_IMODE(info.st_mode) == 0o600),
                    "invalid_private_file")
            require(info.st_size <= limit, "state_file_too_large")
            require(info.st_size <= VERIFY_LIMITS["bytes"] - self.received, "verification_byte_limit")
            parts = []
            remaining = info.st_size
            while remaining:
                self.check()
                chunk = stream.read(min(65536, remaining))
                require(chunk, "verification_file_changed")
                self.received += len(chunk)
                remaining -= len(chunk)
                parts.append(chunk)
            require(os.fstat(stream.fileno()).st_size == info.st_size, "verification_file_changed")
        self.check()
        return b"".join(parts)

    def view(self):
        return {"received_bytes": self.received, "records": self.records, "probe_receipts": self.probes,
                "elapsed_seconds": time.monotonic() - self.start, "limits": VERIFY_LIMITS}


def directory_names(directory, maximum, budget=None):
    names = set()
    with os.scandir(directory) as entries:
        for entry in entries:
            if budget is not None:
                budget.check()
            names.add(entry.name)
            require(len(names) <= maximum, "unexpected_walk_files")
    return names


def verify_finalization(directory, capture):
    budget = VerificationBudget()
    directory = reader.canonical(directory)
    private_directory(directory)
    lock = lock_directory(directory, False)
    try:
        captured = reader.parse(blob(reader.canonical(capture), 65536, private=True, budget=budget), "invalid_finalization_capture")
        require(isinstance(captured, dict), "invalid_finalization_capture")
        witness = captured.get("finalization_witness")
        require(isinstance(witness, dict) and witness.keys() ==
                {"schema_version", "nonce", "state_sha256", "marker_sha256"}, "invalid_finalization_witness")
        require(type(witness["schema_version"]) is int and witness["schema_version"] == 1
                and all(isinstance(witness[key], str) and reader.SHA256.fullmatch(witness[key])
                        for key in ("nonce", "state_sha256", "marker_sha256")), "invalid_finalization_witness")
        marker_raw = blob(directory / INVOCATION_MARKER, 4096, private=True, budget=budget)
        require(reader.digest(marker_raw) == witness["marker_sha256"], "finalization_marker_mismatch")
        marker = reader.parse(marker_raw, "invalid_finalization_marker")
        require(isinstance(marker, dict) and marker.keys() == {"started_at", "pid", "invocation_id", "nonce_sha256",
                "terminal_state_sha256", "terminal_commitment"}, "invalid_finalization_marker")
        require(type(marker["pid"]) is int and 0 < marker["pid"] <= 2147483647 and reader.identifier(marker["invocation_id"]),
                "invalid_finalization_marker")
        try:
            os.kill(marker["pid"], 0)
        except ProcessLookupError:
            pass
        else:
            raise Failure("finalization_origin_active")
        require(marker["nonce_sha256"] == reader.digest(witness["nonce"].encode("ascii"))
                and marker["terminal_state_sha256"] == witness["state_sha256"]
                and marker["terminal_commitment"] == reader.digest(reader.encoded(
                    [marker["invocation_id"], witness["nonce"], witness["state_sha256"]])), "finalization_commitment_mismatch")
        raw = blob(directory / "plan.json", reader.PLAN_MAX, private=True, budget=budget)
        plan = parse_plan(raw)
        state_raw = blob(directory / "state.json", 16 * 1024 * 1024, private=True, budget=budget)
        require(reader.digest(state_raw) == witness["state_sha256"], "finalization_state_mismatch")
        state = reader.parse(state_raw, "invalid_walk_state")
        require(state["coverage_status"] == "partial" and state["reason"] == "finalization_time_uncertain"
                and state["pending"] is None, "ineligible_finalization_state")
        progress = replay(directory, state, plan, raw, budget)
        require(progress.phase == "done" and progress.blocked == "finalization_time_uncertain"
                and progress.used["elapsed_us"] < plan["max_seconds"] * MICROS, "ineligible_finalization_state")
        # This derived observation does not alter any frozen run file or allowance.
        progress.blocked = None
        digest = progress.view()["observation_sha256"]
        require(digest is not None, "ineligible_finalization_state")
        result = {"coverage_status": "complete_observed", "verification_status": "verified",
                  "observation_sha256": digest, "stored_coverage_status": "partial",
                  "stored_collection_usage": state["coverage"]["usage"],
                  "original_deadline_witness": "released_after_final_durable_write",
                  "exact_closing_elapsed_seconds": None, "verification": budget.view(),
                  "snapshot_consistency": "unverified", "mutation_check": "turn_inventory_only"}
        if "after_turn_id" in plan:
            result.update(range=progress.view()["range"], earlier_item_coverage="excluded")
        budget.check()
        return result
    finally:
        os.close(lock)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--verify-finalization", type=Path)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--max-probes-this-run", type=int)
    args = parser.parse_args(argv)
    try:
        if args.verify_finalization is not None:
            require(args.capture is not None and args.plan is None and args.output is None and args.resume is None
                    and args.max_probes_this_run is None, "invalid_verification_invocation")
            result = verify_finalization(args.verify_finalization, args.capture)
            sys.stdout.write(reader.encoded(result).decode("ascii"))
            return 0
        require(args.capture is None, "invalid_walk_invocation")
        if args.max_probes_this_run is None:
            args.max_probes_this_run = MAXIMA["max_probes"]
        require((args.resume is None and args.plan is not None and args.output is not None) or
                (args.resume is not None and args.plan is None and args.output is None), "invalid_walk_invocation")
        require(1 <= args.max_probes_this_run <= MAXIMA["max_probes"], "invalid_invocation_probe_limit")
        result, code = walk(args)
    except Failure as error:
        result, code = {"coverage_status": "error", "reason": str(error)}, 2
    except (OSError, KeyError, TypeError, ValueError, AssertionError, RecursionError, KeyboardInterrupt):
        result, code = {"coverage_status": "error", "reason": "invalid_or_uncertain_walk_state"}, 2
    if args.verify_finalization is not None:
        result["verification_status"] = "failed"
    result.update(snapshot_consistency="unverified", mutation_check="turn_inventory_only")
    sys.stdout.write(reader.encoded(result).decode("ascii"))
    return code


if __name__ == "__main__":
    sys.exit(main())
