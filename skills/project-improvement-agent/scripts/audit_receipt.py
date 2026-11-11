#!/usr/bin/env python3
"""Check what a supplied Codex exec JSONL trace and bound receipts record."""

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Optional


SCHEMA_VERSION = 1
MAX_INPUT_BYTES = 256 * 1024 * 1024
MAX_EVENT_BYTES = 16 * 1024 * 1024
MAX_SIDECAR_BYTES = 1024 * 1024
SHA256 = re.compile(r"[0-9a-fA-F]{64}")
FACT_LABELS = {
    "recorded_shell_calls": "Recorded shell calls",
    "recorded_failed_shell_calls": "Recorded failed shell calls",
    "elapsed_seconds": "Elapsed seconds",
    "clock_reads": "Clock reads",
    "catalog_inspections": "Catalog inspections",
    "collection_end_utc": "Collection end (UTC)",
}
ERROR_EVENTS = {
    "error", "turn.failed", "turn.aborted", "turn.cancelled", "turn.canceled",
    "turn.interrupted",
}


class InvalidInput(ValueError):
    """The supplied input could not be parsed or had an invalid shape."""


class BindingFailure(ValueError):
    """A required binding was absent or did not match the supplied bytes."""


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate key")
        obj[key] = value
    return obj


def finite_float(token):
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("non-finite number")
    if value == 0 and any(char in "123456789" for char in token.lower().split("e", 1)[0]):
        raise ValueError("number underflows to zero")
    return value


def decode_object(data, label):
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_float=finite_float,
            parse_constant=finite_float,
        )
    except (ValueError, RecursionError):
        raise InvalidInput(f"{label}: invalid UTF-8 JSON, duplicate key, or out-of-range number.") from None
    if not isinstance(value, dict):
        raise InvalidInput(f"{label}: expected a JSON object.")
    return value


def open_input(path, label):
    try:
        if path.is_file():
            return path.open("rb")
    except OSError:
        pass
    raise InvalidInput(f"{label}: could not open a regular file.")


def read_sidecar(path, label):
    try:
        with open_input(path, label) as source:
            data = source.read(MAX_SIDECAR_BYTES + 1)
    except OSError:
        raise InvalidInput(f"{label}: could not read input.") from None
    if len(data) > MAX_SIDECAR_BYTES:
        raise InvalidInput(f"{label}: input exceeds 1 MiB.")
    return decode_object(data, label)


def hash_report(path):
    digest = hashlib.sha256()
    size = 0
    try:
        with open_input(path, "Report") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                size += len(block)
                if size > MAX_INPUT_BYTES:
                    raise InvalidInput("Report: input exceeds 256 MiB.")
                digest.update(block)
    except OSError:
        raise InvalidInput("Report: could not read input.") from None
    return digest.hexdigest()


@dataclass
class TraceFacts:
    digest: str
    count: Optional[int]
    failed_count: Optional[int]
    missing_exit: bool
    shape_complete: bool
    unfinished: bool

    @property
    def complete(self):
        return self.shape_complete and not self.unfinished and not self.missing_exit


def read_trace(path):
    digest = hashlib.sha256()
    size = line_number = event_count = count = failed = 0
    first = second = last = None
    threads = starts = terminals = 0
    error = missing_exit = False
    completed_ids = set()
    pending_commands = set()

    try:
        with open_input(path, "Trace") as source:
            while True:
                line = source.readline(MAX_EVENT_BYTES + 1)
                if not line:
                    break
                line_number += 1
                label = f"Trace line {line_number}"
                size += len(line)
                if len(line) > MAX_EVENT_BYTES:
                    raise InvalidInput(f"{label}: event exceeds 16 MiB.")
                if size > MAX_INPUT_BYTES:
                    raise InvalidInput("Trace: input exceeds 256 MiB.")
                digest.update(line)
                if not line.strip():
                    continue
                event = decode_object(line, label)
                kind = event.get("type")
                if not isinstance(kind, str) or not kind.strip():
                    raise InvalidInput(f"{label}: expected a nonempty event type.")

                event_count += 1
                if event_count == 1:
                    first = kind
                elif event_count == 2:
                    second = kind
                last = kind
                threads += kind == "thread.started"
                starts += kind == "turn.started"
                terminals += kind == "turn.completed"
                error = error or kind in ERROR_EVENTS

                if kind not in ("item.started", "item.updated", "item.completed"):
                    continue
                item = event.get("item")
                if not isinstance(item, dict):
                    raise InvalidInput(f"{label}: expected an item object.")
                item_kind = item.get("type")
                if not isinstance(item_kind, str) or not item_kind.strip():
                    raise InvalidInput(f"{label}: expected a nonempty item type.")
                is_command = item_kind == "command_execution"
                item_id = item.get("id")
                if ("id" in item or is_command) and (
                    not isinstance(item_id, str) or not item_id.strip()
                ):
                    raise InvalidInput(f"{label}: expected a nonempty item ID.")

                if kind != "item.completed":
                    if is_command:
                        if item_id in completed_ids:
                            raise InvalidInput(f"{label}: command lifecycle event follows its completion.")
                        pending_commands.add(item_id)
                    continue
                if item_id is not None:
                    if item_id in completed_ids:
                        raise InvalidInput(f"{label}: duplicate completed item ID.")
                    completed_ids.add(item_id)
                if not is_command:
                    continue

                pending_commands.discard(item_id)
                count += 1
                status = item.get("status")
                if "status" in item and status not in ("completed", "failed"):
                    raise InvalidInput(f"{label}: invalid terminal command status.")
                code = item.get("exit_code")
                if code is None:
                    missing_exit = True
                elif type(code) is not int:
                    raise InvalidInput(f"{label}: command exit code must be an integer or null.")
                elif status == "failed" and code == 0:
                    raise InvalidInput(f"{label}: failed command status conflicts with exit code zero.")
                elif code != 0:
                    failed += 1
    except OSError:
        raise InvalidInput("Trace: could not read input.") from None

    shape_complete = (
        first == "thread.started" and second == "turn.started" and last == "turn.completed"
        and threads == starts == terminals == 1 and not error
    )
    return TraceFacts(
        digest.hexdigest(),
        count if event_count else None,
        failed if event_count and not missing_exit else None,
        missing_exit,
        shape_complete,
        bool(pending_commands),
    )


def version(receipt, label, *, required=True):
    if not required and "schema_version" not in receipt:
        return
    value = receipt.get("schema_version")
    if type(value) is not int or value != SCHEMA_VERSION:
        raise InvalidInput(f"{label}: unsupported schema_version; expected integer 1.")


def binding(receipt, key, expected, label):
    if key not in receipt:
        raise BindingFailure(f"{label}: missing {key} binding.")
    value = receipt[key]
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise InvalidInput(f"{label}: {key} must be a 64-character hexadecimal SHA-256 digest.")
    if expected is None or value.lower() != expected:
        raise BindingFailure(f"{label}: {key} does not match supplied input bytes.")


def duration(value):
    return (
        (type(value) is int or (type(value) is float and math.isfinite(value)))
        and value >= 0
    )


def read_execution(path, trace_digest):
    receipt = read_sidecar(path, "Execution receipt")
    version(receipt, "Execution receipt", required=False)
    binding(receipt, "trace_sha256", trace_digest, "Execution receipt")
    value = receipt.get("elapsed_seconds")
    if not duration(value):
        raise InvalidInput("Execution receipt: elapsed_seconds must be a finite nonnegative number.")
    return value


def read_claims(path, trace_digest, report_digest):
    receipt = read_sidecar(path, "Claims receipt")
    version(receipt, "Claims receipt")
    claims = receipt.get("claims")
    if not isinstance(claims, dict):
        raise InvalidInput("Claims receipt: claims must be an object.")
    if any(key not in FACT_LABELS for key in claims):
        raise InvalidInput("Claims receipt: contains an unrecognized claim name.")
    if claims and report_digest is None:
        raise InvalidInput("Claims receipt: nonempty claims require --report.")
    binding(receipt, "trace_sha256", trace_digest, "Claims receipt")
    if report_digest is not None or "report_sha256" in receipt:
        binding(receipt, "report_sha256", report_digest, "Claims receipt")

    for key, value in claims.items():
        if value is None:
            continue
        if key == "elapsed_seconds":
            valid = duration(value)
        elif key == "collection_end_utc":
            valid = isinstance(value, str) and bool(value.strip())
        else:
            valid = type(value) is int and value >= 0
        if not valid:
            raise InvalidInput(f"Claims receipt: invalid value for {key}.")
    return claims


def fact(value, basis):
    return {"value": value, "basis": basis}


def initial_result():
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "failed",
        "trace_sha256": None,
        "trace_complete": None,
        "facts": {
            "recorded_shell_calls": fact(None, "No trace events verified."),
            "recorded_failed_shell_calls": fact(None, "No command exit codes verified."),
            "elapsed_seconds": fact(None, "No valid runner receipt bound to the trace."),
            "clock_reads": fact(None, "The supported Codex exec events do not establish clock reads."),
            "catalog_inspections": fact(None, "The supported Codex exec events do not establish catalog inspections."),
            "collection_end_utc": fact(None, "The supported receipts do not establish a collection end timestamp."),
        },
        "claim_checks": {},
        "errors": [],
    }


def evaluate(args):
    result = initial_result()
    facts = result["facts"]
    errors = result["errors"]
    try:
        trace = read_trace(args.trace)
        result["trace_sha256"] = trace.digest
        result["trace_complete"] = trace.complete
        if trace.count is not None:
            facts["recorded_shell_calls"] = fact(trace.count, "Unique completed command_execution items in the supplied trace.")
        if trace.failed_count is not None:
            facts["recorded_failed_shell_calls"] = fact(trace.failed_count, "Completed command_execution items with a recorded nonzero exit code.")
        elif trace.missing_exit:
            facts["recorded_failed_shell_calls"] = fact(None, "At least one recorded completion has no exit code.")
        if not trace.shape_complete:
            errors.append("Trace does not show a normal, complete single turn.")
        if trace.unfinished:
            errors.append("Trace contains a command with no recorded completion.")
        if trace.missing_exit:
            errors.append("Trace contains a completed command with no recorded exit code.")

        if args.report is not None:
            result["report_sha256"] = hash_report(args.report)
        if args.execution is not None:
            elapsed = read_execution(args.execution, trace.digest)
            facts["elapsed_seconds"] = fact(elapsed, "Runner-supplied duration bound to the trace SHA-256.")
        if args.claims is not None:
            claims = read_claims(args.claims, trace.digest, result.get("report_sha256"))
            checks = result["claim_checks"]
            for key in FACT_LABELS:
                if key not in claims:
                    continue
                actual, asserted = facts[key]["value"], claims[key]
                if asserted is None:
                    checks[key] = "not_asserted"
                elif actual is None:
                    checks[key] = "unsupported"
                    errors.append(f"Claim {key} has no supporting evidence.")
                elif actual != asserted:
                    checks[key] = "mismatch"
                    errors.append(f"Claim {key} differs from the supported fact.")
                else:
                    checks[key] = "matched"
            if any(value in ("unsupported", "mismatch") for value in checks.values()):
                return result, 1
    except InvalidInput as exc:
        errors.append(str(exc))
        return result, 2
    except BindingFailure as exc:
        errors.append(str(exc))
        return result, 1

    if not trace.complete:
        result["status"] = "partial"
        return result, 3
    result["status"] = "passed"
    return result, 0


def markdown(result):
    lines = [
        "## Execution evidence",
        "",
        f"- Receipt status: **{result['status']}**",
    ]
    if result["trace_sha256"] is not None:
        lines.append(f"- Trace SHA-256: `{result['trace_sha256']}`")
    if "report_sha256" in result:
        lines.append(f"- Report SHA-256: `{result['report_sha256']}`")
    complete = result["trace_complete"]
    shape = "unknown" if complete is None else ("yes" if complete else "no")
    lines.append(f"- Complete single-turn trace: {shape}")
    for key, label in FACT_LABELS.items():
        entry = result["facts"][key]
        value = "unknown" if entry["value"] is None else str(entry["value"])
        lines.append(f"- {label}: **{value}**. {entry['basis']}")
    if result["claim_checks"]:
        lines.extend(("", "Structured claims:"))
        for key, status in result["claim_checks"].items():
            lines.append(f"- {FACT_LABELS[key]}: {status.replace('_', ' ')}")
    if result["errors"]:
        lines.append("")
        lines.extend(f"- {error}" for error in result["errors"])
    lines.extend((
        "",
        "Counts describe recorded items only. Hashes bind supplied bytes; they do not authenticate the host or verify report prose.",
    ))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Check a supplied Codex exec --json single-turn trace and optional bound receipts. "
            "Prints evidence to stdout without changing inputs. Only structured claims are checked; "
            "hashes bind bytes and do not authenticate the host."
        ),
        epilog=(
            "Exit codes: 0 passed; 1 failed claim or binding; 2 invalid input; "
            "3 partial trace. A report and claims are optional in facts-only mode. "
            "For claim checks, hash the final report bytes and keep the generated receipt separate."
        ),
    )
    parser.add_argument("--trace", required=True, type=Path, help="Codex exec JSONL trace")
    parser.add_argument(
        "--execution", type=Path,
        help="runner JSON with trace_sha256 and elapsed_seconds (optional schema_version 1)",
    )
    parser.add_argument(
        "--claims", type=Path,
        help="JSON with schema_version 1, trace_sha256, report_sha256 when --report is supplied, and claims",
    )
    parser.add_argument("--report", type=Path, help="exact report bytes; required with nonempty claims")
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="stdout format")
    args = parser.parse_args(argv)
    result, code = evaluate(args)
    if args.format == "markdown":
        print(markdown(result))
    else:
        print(json.dumps(result, indent=2, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
