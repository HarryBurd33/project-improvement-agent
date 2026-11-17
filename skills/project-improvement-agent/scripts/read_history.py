#!/usr/bin/env python3
"""Read a bounded selection from the Codex app-server into private evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import time


VERSION = "1.7.0"
DEFAULTS = dict(direction="asc", page_size=20, max_pages=2, max_records=20, max_seconds=15, max_bytes=131072)
REQUIRED = {"schema_version", "thread_id", "operation"}
OPTIONAL = {"turn_id", "cursor", "read_mode", "assistant_text_selection"}
LARGE_MAX_BYTES = 4 * 1024 * 1024
ID = re.compile(r"[A-Za-z0-9._:-]{1,200}")
METHOD = re.compile(r"[A-Za-z0-9_./-]{1,160}")
SHA256 = re.compile(r"[0-9a-f]{64}")
ASSISTANT_PHASES = (None, "commentary", "partial_answer", "final_answer")
ITEMS = {
    "userMessage", "hookPrompt", "agentMessage", "functionCallOutput", "plan", "reasoning",
    "commandExecution", "fileChange", "mcpToolCall", "dynamicToolCall", "collabAgentToolCall",
    "subAgentActivity", "webSearch", "imageView", "sleep", "imageGeneration", "enteredReviewMode",
    "exitedReviewMode", "contextCompaction",
}
USER_INPUTS = {"text", "image", "localImage", "audio", "localAudio", "skill", "mention"}
STATUSES = {"completed", "interrupted", "failed", "inProgress"}
CHUNK = 8192
PLAN_MAX = 32768
CLEANUP_SECONDS = 2.5


class ReadFailure(Exception):
    """A classified failure whose code carries no provider or user content."""


def require(value, code):
    if not value:
        raise ReadFailure(code)


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def reject_constant(_value):
    raise ValueError("Non-finite constant")


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def parse(raw, code):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ReadFailure(code) from None


def canonical(path):
    absolute = Path(os.path.abspath(path))
    require(absolute.resolve(strict=False) == absolute, "symlink_path")
    return absolute


def load_plan(path):
    path = canonical(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "invalid_plan_path")
            raw = stream.read(PLAN_MAX + 1)
    except OSError:
        raise ReadFailure("invalid_plan_path") from None
    require(len(raw) <= PLAN_MAX, "plan_too_large")
    return validate_plan(parse(raw, "invalid_plan_json")), digest(raw)


def validate_plan(supplied):
    require(isinstance(supplied, dict) and REQUIRED <= supplied.keys()
            and supplied.keys() <= REQUIRED | OPTIONAL | DEFAULTS.keys(), "invalid_plan_fields")
    plan = {**DEFAULTS, "turn_id": None, "cursor": None, "read_mode": "standard", **supplied}
    require(type(plan["schema_version"]) is int and plan["schema_version"] == 1, "invalid_plan_version")
    require(plan["operation"] in ("turns", "items") and plan["direction"] in ("asc", "desc"), "invalid_plan_operation")
    require(identifier(plan["thread_id"]), "invalid_plan_thread")
    require(plan["turn_id"] is None or (plan["operation"] == "items" and identifier(plan["turn_id"])), "invalid_plan_turn")
    require(plan["cursor"] is None or valid_cursor(plan["cursor"]), "invalid_plan_cursor")
    require(plan["read_mode"] in ("standard", "large_single_page", "large_batch_page"), "invalid_plan_read_mode")
    for key in ("page_size", "max_pages", "max_records"):
        value = plan[key]
        require(type(value) is int and 1 <= value <= DEFAULTS[key], "invalid_plan_" + key)
    byte_limit = plan["max_bytes"]
    if plan["read_mode"] != "standard":
        require(plan["operation"] == "items" and plan["turn_id"] is not None, "invalid_large_page_scope")
        require({"page_size", "max_pages", "max_records"} <= supplied.keys()
                and plan["max_pages"] == 1 and plan["page_size"] == plan["max_records"],
                "invalid_large_page_counts")
        if plan["read_mode"] == "large_single_page":
            require(plan["page_size"] == 1, "invalid_large_page_counts")
        require("max_bytes" in supplied and type(byte_limit) is int
                and DEFAULTS["max_bytes"] < byte_limit <= LARGE_MAX_BYTES, "invalid_plan_max_bytes")
    else:
        require(type(byte_limit) is int and 1 <= byte_limit <= DEFAULTS["max_bytes"], "invalid_plan_max_bytes")
    seconds = plan["max_seconds"]
    require(type(seconds) in (int, float) and 0 < seconds <= 15 and math.isfinite(seconds), "invalid_plan_max_seconds")
    if "assistant_text_selection" in supplied:
        selection = supplied["assistant_text_selection"]
        require(isinstance(selection, dict) and selection.keys() == {"item_id", "expected_sha256"}
                and identifier(selection["item_id"]), "invalid_assistant_text_selection")
        expected = selection["expected_sha256"]
        require(isinstance(expected, str) and SHA256.fullmatch(expected), "invalid_assistant_text_selection")
        require(plan["operation"] == "items" and plan["turn_id"] is not None and supplied.get("max_pages") == 1,
                "invalid_assistant_text_selection_scope")
    return plan


def identifier(value):
    return isinstance(value, str) and ID.fullmatch(value) is not None


def valid_cursor(value):
    return isinstance(value, str) and 0 < len(value) <= 16384


def executable():
    command = shutil.which("codex")
    require(command is not None, "codex_unavailable")
    path = Path(command).resolve(strict=True)
    require(path.is_file() and os.access(path, os.X_OK), "codex_unavailable")
    return str(path)


def open_output(path):
    path = canonical(path)
    require(not any((parent / ".git").exists() or (parent / "SKILL.md").is_file() for parent in path.parents),
            "output_inside_repository_or_skill")
    try:
        path.mkdir(mode=0o700)
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        os.fchmod(fd, 0o700)
    except OSError:
        raise ReadFailure("output_must_be_new_private_directory") from None
    return path, fd


def write_evidence(directory, name, value):
    raw = encoded(value)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    descriptor = os.open(name, flags, 0o600, dir_fd=directory)
    with os.fdopen(descriptor, "wb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(raw)
    return digest(raw)


def integer_or_none(value):
    require(value is None or (type(value) is int and -(2**63) <= value < 2**63), "invalid_record_timestamp")
    return value


def matching_scope(event, plan):
    if "threadId" in event:
        require(event["threadId"] == plan["thread_id"], "wrong_thread_scope")
    if plan["turn_id"] is not None and "turnId" in event:
        require(event["turnId"] == plan["turn_id"], "wrong_turn_scope")


def record(raw, plan):
    require(isinstance(raw, dict), "invalid_record")
    matching_scope(raw, plan)
    if plan["operation"] == "turns":
        require(identifier(raw.get("id")) and raw.get("status") in STATUSES
                and raw.get("items") == [] and raw.get("itemsView", "notLoaded") == "notLoaded", "invalid_turn_record")
        root = raw.get("rootTurnId")
        require(root is None or identifier(root), "invalid_turn_record")
        return {"type": "turn", "turn_id": raw["id"], "root_turn_id": root, "role": None, "status": raw["status"],
                "started_at_seconds": integer_or_none(raw.get("startedAt")),
                "completed_at_seconds": integer_or_none(raw.get("completedAt")),
                "duration_ms": integer_or_none(raw.get("durationMs"))}
    turn = raw.get("turnId")
    item = raw.get("item")
    require(identifier(turn) and isinstance(item, dict) and identifier(item.get("id")), "invalid_item_record")
    matching_scope(item, plan)
    kind = item.get("type")
    require(isinstance(kind, str) and kind in ITEMS, "invalid_item_type")
    result = {"type": kind, "turn_id": turn, "item_id": item["id"],
              "role": "user" if kind == "userMessage" else "assistant" if kind == "agentMessage" else None,
              "started_at_ms": integer_or_none(raw.get("startedAtMs")),
              "completed_at_ms": integer_or_none(raw.get("completedAtMs"))}
    if kind == "userMessage":
        content = item.get("content")
        require(isinstance(content, list), "invalid_user_content")
        result["text_parts"] = []
        result["omitted_nontext_parts"] = 0
        for part in content:
            require(isinstance(part, dict) and isinstance(part.get("type"), str)
                    and part["type"] in USER_INPUTS, "invalid_user_content")
            if part["type"] == "text":
                require(isinstance(part.get("text"), str), "invalid_user_text")
                result["text_parts"].append(part["text"])
            else:
                result["omitted_nontext_parts"] += 1
    else:
        result["serialized_item_sha256"] = digest(encoded(item))
    return result


class Peer:
    def __init__(self, process, plan, deadline):
        self.process = process
        self.plan = plan
        self.deadline = deadline
        self.selector = selectors.DefaultSelector()
        self.buffer = bytearray()
        self.pending = memoryview(b"")
        self.counts = {"stdout_bytes": 0, "stderr_bytes": 0, "notifications": 0, "server_requests": 0}
        self.stdout_open = True

    def __enter__(self):
        try:
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                os.set_blocking(stream.fileno(), False)
            self.selector.register(self.process.stdout, selectors.EVENT_READ, "stdout")
            self.selector.register(self.process.stderr, selectors.EVENT_READ, "stderr")
            return self
        except BaseException:
            self.selector.close()
            raise

    def __exit__(self, *_error):
        self.selector.close()

    def pump(self):
        byte_limit = self.plan["max_bytes"]
        require(self.counts["stdout_bytes"] + self.counts["stderr_bytes"] < byte_limit, "byte_limit")
        remaining = self.deadline - time.monotonic()
        require(remaining > 0, "wall_limit")
        ready = self.selector.select(remaining)
        require(ready, "wall_limit")
        require(time.monotonic() <= self.deadline, "wall_limit")
        for key, _ in ready:
            stream = key.fileobj
            channel = key.data
            try:
                if channel == "stdin":
                    sent = os.write(stream.fileno(), self.pending)
                    self.pending = self.pending[sent:]
                    if not self.pending:
                        self.selector.unregister(stream)
                    continue
                received = self.counts["stdout_bytes"] + self.counts["stderr_bytes"]
                allowance = byte_limit - received
                if allowance == 0:
                    # This batch can make both output channels ready. Parse the
                    # bytes already received before deciding if more are needed.
                    continue
                block = os.read(stream.fileno(), min(CHUNK, allowance))
            except BlockingIOError:
                continue
            except BrokenPipeError:
                raise ReadFailure("peer_write_closed") from None
            if not block:
                self.selector.unregister(stream)
                if channel == "stdout":
                    self.stdout_open = False
                continue
            self.counts[channel + "_bytes"] += len(block)
            if channel == "stdout":
                self.buffer.extend(block)

    def lines(self):
        while True:
            position = self.buffer.find(b"\n")
            if position < 0:
                break
            line = bytes(self.buffer[:position])
            del self.buffer[:position + 1]
            if line.strip():
                yield parse(line, "malformed_response")

    def call(self, request):
        self.pending = memoryview(encoded(request))
        self.selector.register(self.process.stdin, selectors.EVENT_WRITE, "stdin")
        expected = request.get("id")
        answer = None
        while True:
            require(time.monotonic() < self.deadline, "wall_limit")
            for frame in self.lines():
                require(isinstance(frame, dict) and frame.get("jsonrpc", "2.0") == "2.0", "invalid_response_envelope")
                if "method" in frame:
                    require(isinstance(frame["method"], str) and METHOD.fullmatch(frame["method"]),
                            "invalid_response_envelope")
                    if "id" in frame:
                        self.counts["server_requests"] += 1
                        raise ReadFailure("unexpected_server_request")
                    # Observed from installed 0.166.0 even though its generated
                    # JSONRPCNotification schema omits this transport metadata.
                    require(frame.keys() <= {"method", "params", "jsonrpc", "emittedAtMs"}
                            and ("emittedAtMs" not in frame or type(frame["emittedAtMs"]) is int),
                            "invalid_response_envelope")
                    self.counts["notifications"] += 1
                    continue
                require(not self.pending and answer is None and expected is not None and type(frame.get("id")) is int
                        and frame["id"] == expected and frame.keys() <= {"id", "result", "error", "jsonrpc"}
                        and ("result" in frame) != ("error" in frame), "unexpected_response_envelope")
                if "error" in frame:
                    error = frame["error"]
                    require(isinstance(error, dict) and type(error.get("code")) is int
                            and isinstance(error.get("message"), str), "invalid_rpc_error")
                    raise ReadFailure("rpc_error")
                require(isinstance(frame["result"], dict), "invalid_response_result")
                answer = frame["result"]
            if not self.pending and (expected is None or answer is not None):
                return answer
            if not self.stdout_open:
                raise ReadFailure("truncated_response" if self.buffer.strip() else "peer_exited")
            self.pump()


def group_exists(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


def cleanup(process):
    if process is None:
        return {"started": False, "reaped": None, "group_gone": None, "exit_code": None}
    for stream in (process.stdin, process.stdout, process.stderr):
        stream.close()
    deadline = time.monotonic() + CLEANUP_SECONDS
    signals = []
    try:
        for wait, action in ((0.20, None), (0.50, signal.SIGTERM), (CLEANUP_SECONDS - 0.70, signal.SIGKILL)):
            if process.poll() is not None and not group_exists(process.pid):
                break
            if action is not None:
                try:
                    os.killpg(process.pid, action)
                    signals.append(action.name)
                except ProcessLookupError:
                    pass
            stop = min(deadline, time.monotonic() + wait)
            while time.monotonic() < stop:
                if process.poll() is not None and not group_exists(process.pid):
                    break
                time.sleep(0.02)
        reaped = process.poll() is not None
        gone = not group_exists(process.pid)
    except OSError:
        reaped, gone = process.poll() is not None, False
    return {"started": True, "pid": process.pid, "reaped": reaped, "group_gone": gone,
            "exit_code": process.returncode, "signals": signals, "margin_seconds": CLEANUP_SECONDS}


def page_from(result, plan, limit, seen_cursors, seen_records):
    matching_scope(result, plan)
    data = result.get("data")
    require(isinstance(data, list), "invalid_page_data")
    require(len(data) <= limit, "overreturned_page")
    require("nextCursor" in result, "missing_response_cursor")
    next_cursor = result["nextCursor"]
    for value in (next_cursor, result.get("backwardsCursor")):
        require(value is None or valid_cursor(value), "invalid_response_cursor")
    require(next_cursor is None or (data and next_cursor not in seen_cursors), "cursor_no_progress")
    projected = [record(raw, plan) for raw in data]
    keys = {(row["turn_id"], row.get("item_id")) for row in projected}
    require(len(keys) == len(projected) and not keys & seen_records, "record_no_progress")
    selection = plan.get("assistant_text_selection")
    if selection is not None:
        match = next(((raw["item"], row) for raw, row in zip(data, projected)
                      if row["item_id"] == selection["item_id"]), None)
        require(match is not None, "selected_assistant_item_missing")
        item, row = match
        require(row["type"] == "agentMessage", "selected_assistant_item_wrong_type")
        require(row["serialized_item_sha256"] == selection["expected_sha256"], "selected_assistant_item_hash_mismatch")
        text, phase = item.get("text"), item.get("phase")
        require(isinstance(text, str) and phase in ASSISTANT_PHASES, "invalid_selected_assistant_content")
        row.update(assistant_text=text, assistant_phase=phase)
    return projected, keys, next_cursor


def collect(command, plan, plan_sha):
    records, requested, accepted = [], [], []
    cursor = plan["cursor"]
    seen_cursors = {cursor}
    seen_records = set()
    process, peer = None, None
    start = time.monotonic()
    receipt = {"schema_version": 1, "reader_version": VERSION, "transport": "codex app-server --stdio",
               "executable": command, "plan": plan, "plan_sha256": plan_sha, "started_at": utc(),
               "requests": requested, "accepted_pages": accepted, "app_server_version": None,
               "initial_cursor_provenance": "caller_supplied_unverified" if cursor is not None else "start_of_selected_scope"}
    try:
        try:
            process = subprocess.Popen([command, "app-server", "--stdio"], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, bufsize=0)
        except OSError:
            raise ReadFailure("startup_failed") from None
        peer = Peer(process, plan, start + plan["max_seconds"])
        with peer:
            initialized = peer.call({"id": 1, "method": "initialize",
                                     "params": {"clientInfo": {"name": "pia_selected_history", "version": VERSION}}})
            agent = initialized.get("userAgent")
            if isinstance(agent, str):
                version = re.match(r"^[\w.-]+/([0-9]+\.[0-9]+\.[0-9]+(?:[-+][\w.-]+)?)\b", agent)
                if version:
                    receipt["app_server_version"] = version.group(1)
            peer.call({"method": "initialized"})
            for index in range(plan["max_pages"]):
                limit = min(plan["page_size"], plan["max_records"] - len(records))
                params = {"threadId": plan["thread_id"], "limit": limit, "sortDirection": plan["direction"]}
                if cursor is not None:
                    params["cursor"] = cursor
                if plan["operation"] == "turns":
                    params["itemsView"] = "notLoaded"
                elif plan["turn_id"] is not None:
                    params["turnId"] = plan["turn_id"]
                request = {"id": index + 2, "method": "thread/" + plan["operation"] + "/list", "params": params}
                requested.append(request)
                result = peer.call(request)
                page, keys, next_cursor = page_from(result, plan, limit, seen_cursors, seen_records)
                require(time.monotonic() < peer.deadline, "wall_limit")
                records.extend(page)
                seen_records.update(keys)
                accepted.append({"request_id": request["id"], "record_count": len(page), "next_cursor": next_cursor})
                cursor = next_cursor
                seen_cursors.add(cursor)
                if cursor is None:
                    status, reason = "complete", "selected_scope_end"
                    break
                if len(records) == plan["max_records"]:
                    status, reason = "partial", "record_limit"
                    break
            else:
                status, reason = "partial", "page_limit"
        exit_code = 0
    except ReadFailure as error:
        status, reason, exit_code = ("partial" if accepted else "error"), str(error), 1
    except (OSError, ValueError, TypeError, RecursionError, KeyboardInterrupt):
        status, reason, exit_code = ("partial" if accepted else "error"), "local_transport_failure", 1
    finally:
        foreground = time.monotonic() - start
        # A second interrupt should not strand a peer during bounded cleanup.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        previous_interrupt = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            shutdown = cleanup(process)
        finally:
            signal.signal(signal.SIGINT, previous_interrupt)
    if shutdown["started"] and not (shutdown["reaped"] and shutdown["group_gone"]):
        status, reason, exit_code = ("partial" if accepted else "error"), "cleanup_uncertain", 1
    counts = peer.counts if peer else {"stdout_bytes": 0, "stderr_bytes": 0, "notifications": 0, "server_requests": 0}
    receipt.update(status=status, reason=reason, finished_at=utc(), foreground_seconds=round(foreground, 6),
                   elapsed_seconds=round(time.monotonic() - start, 6), cleanup=shutdown, last_safe_cursor=cursor,
                   boundary="returned_cursor" if accepted and cursor is not None
                   else "selected_scope_end" if accepted else "unadvanced_input_boundary",
                   accepted_records=len(records), accepted_page_count=len(accepted), attempted_page_count=len(requested),
                   received_bytes=counts["stdout_bytes"] + counts["stderr_bytes"], **counts)
    return receipt, records, exit_code


def interrupted(_signal, _frame):
    raise KeyboardInterrupt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    directory = None
    try:
        require(os.name == "posix", "posix_transport_required")
        plan, plan_sha = load_plan(args.plan)
        command = executable()
        output, directory = open_output(args.output)
    except (ReadFailure, OSError, RuntimeError) as error:
        code = str(error) if isinstance(error, ReadFailure) else "local_preflight_failure"
        print(json.dumps({"status": "refused", "reason": code}))
        return 2
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        receipt, records, status = collect(command, plan, plan_sha)
        records_sha = write_evidence(directory, "records.json", records)
        receipt["records_sha256"] = records_sha
        receipt_sha = write_evidence(directory, "receipt.json", receipt)
        print(json.dumps({"status": receipt["status"], "reason": receipt["reason"],
                          "pages": receipt["accepted_page_count"], "records": len(records),
                          "receipt": str(output / "receipt.json"), "receipt_sha256": receipt_sha,
                          "evidence": str(output / "records.json"), "records_sha256": records_sha}))
        return status
    except (ReadFailure, OSError, ValueError, TypeError, KeyboardInterrupt):
        print(json.dumps({"status": "error", "reason": "private_output_or_transport_failure"}))
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)
        os.close(directory)


if __name__ == "__main__":
    sys.exit(main())
