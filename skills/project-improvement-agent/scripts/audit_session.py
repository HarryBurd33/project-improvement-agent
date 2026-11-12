#!/usr/bin/env python3
"""Write a declared audit intake, check recorded order, or finalize a finished trace."""

import argparse
from dataclasses import dataclass, field
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

_previous_bytecode_setting = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    import audit_receipt as receipt
finally:
    sys.dont_write_bytecode = _previous_bytecode_setting


TOOL_VERSION = "1.3.0"
ORDER_SCOPE = "Order of supplied command labels in the supplied trace. Label accuracy requires independent review."
FINAL_SCOPE = "Recorded execution facts for the supplied trace. Narrative remains unverified."
LIMITATIONS = [
    "Hashes bind supplied bytes and do not authenticate their producer or trace.",
    "Ordering applies only to supplied labels and recorded commands.",
    "Narrative, unrecorded activity, and global tool or byte totals are unverified.",
]
BODY_PREFIX = b"## Unverified narrative\n\n"
ITEM_EVENTS = ("item.started", "item.updated", "item.completed")
PASSIVE_ITEMS = ("reasoning", "agent_message")
COMMAND_LABELS = ("intake", "governing", "evidence", "other")


class PartialEvidence(ValueError):
    """The supplied evidence does not establish a required fact."""


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "Invalid command arguments. Use --help for syntax.\n")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8")


def read_bytes(path, label, limit):
    try:
        with receipt.open_input(path, label) as source:
            data = source.read(limit + 1)
    except OSError:
        raise receipt.InvalidInput(f"{label}: could not read input.") from None
    if len(data) > limit:
        raise receipt.InvalidInput(f"{label}: input exceeds the supported size.")
    return data


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def parse_intake(data):
    spec = receipt.decode_object(data, "Intake")
    receipt.version(spec, "Intake")
    scope = spec.get("scope")
    if (
        not nonempty(spec.get("run_id"))
        or not isinstance(scope, dict)
        or any(key not in scope or (scope[key] is not None and not isinstance(scope[key], str))
               for key in ("chat", "project"))
        or not nonempty(scope.get("basis"))
    ):
        raise receipt.InvalidInput("Intake: invalid run_id or scope.")
    criteria = spec.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise receipt.InvalidInput("Intake: expected a nonempty criteria list.")
    ids = set()
    for entry in criteria:
        if not isinstance(entry, dict) or any(
            not nonempty(entry.get(key)) for key in ("id", "expected", "method")
        ):
            raise receipt.InvalidInput("Intake: invalid criterion.")
        if entry["id"] in ids:
            raise receipt.InvalidInput("Intake: duplicate criterion ID.")
        ids.add(entry["id"])
    return {
        "type": "pia.intake",
        "schema_version": receipt.SCHEMA_VERSION,
        "run_id": spec["run_id"],
        "intake_sha256": sha256(data),
    }


def safe_destination(path):
    path = path.absolute()
    if not path.name or ".." in path.parts or path.parent.resolve(strict=True) != path.parent:
        raise receipt.InvalidInput("Output: expected a destination in a canonical directory.")
    return path


def write_blocks(stream, blocks):
    for block in blocks:
        if stream.write(block) != len(block):
            raise OSError("short write")


def write_private(path, *blocks):
    def opener(name, flags):
        return os.open(name, flags, 0o600)

    with open(path, "xb", opener=opener) as stream:
        write_blocks(stream, blocks)


def verify_file(path, expected, label):
    if receipt.hash_report(path) != expected:
        raise receipt.BindingFailure(f"{label}: SHA-256 changed or readback did not match.")


def intake(args):
    data = read_bytes(args.spec, "Intake", receipt.MAX_SIDECAR_BYTES)
    marker = parse_intake(data)
    output = safe_destination(args.output)
    write_private(output, data)
    verify_file(output, marker["intake_sha256"], "Intake output")
    return marker


def parse_classification(data, trace_digest, intake_digest):
    classification = receipt.decode_object(data, "Classification")
    receipt.version(classification, "Classification")
    receipt.binding(classification, "trace_sha256", trace_digest, "Classification")
    receipt.binding(classification, "intake_sha256", intake_digest, "Classification")
    commands = classification.get("commands")
    if not isinstance(commands, dict) or any(
        not nonempty(key) or label not in COMMAND_LABELS for key, label in commands.items()
    ):
        raise receipt.InvalidInput("Classification: invalid command labels.")
    intake_ids = [key for key, label in commands.items() if label == "intake"]
    if len(intake_ids) != 1:
        raise receipt.InvalidInput("Classification: exactly one intake command is required.")
    return commands, intake_ids[0]


@dataclass
class Lifecycle:
    starts: dict = field(default_factory=dict)
    completions: dict = field(default_factory=dict)
    item_types: dict = field(default_factory=dict)
    marker: object = None
    marker_exit: object = None
    marker_count: int = 0
    unsupported: bool = False

    def observe(self, event, index, intake_id):
        kind = event["type"]
        if kind not in ITEM_EVENTS:
            if kind not in ("thread.started", "turn.started", "turn.completed"):
                self.unsupported = True
            return

        item = event["item"]
        item_id, item_type = item.get("id"), item["type"]
        if item_id is not None and self.item_types.setdefault(item_id, item_type) != item_type:
            raise receipt.InvalidInput("Trace: an item ID changes type.")
        if item_type in PASSIVE_ITEMS:
            return
        if item_type != "command_execution":
            self.unsupported = True
            return

        if kind == "item.started":
            if item_id in self.starts:
                raise receipt.InvalidInput("Trace: duplicate command start.")
            self.starts[item_id] = index
            return
        if item_id not in self.starts:
            raise PartialEvidence("Trace: command lifecycle lacks a preceding start.")
        if kind == "item.completed":
            self.completions[item_id] = index
            marker = read_marker(item.get("aggregated_output"))
            if marker is not None:
                self.marker_count += 1
            if item_id == intake_id:
                self.marker = marker
                self.marker_exit = item["exit_code"]


def read_lifecycle(path, expected_digest, intake_id):
    lifecycle = Lifecycle()
    digest = hashlib.sha256()
    size = 0
    with receipt.open_input(path, "Trace") as source:
        index = 0
        while True:
            line = source.readline(receipt.MAX_EVENT_BYTES + 1)
            if not line:
                break
            size += len(line)
            if len(line) > receipt.MAX_EVENT_BYTES or size > receipt.MAX_INPUT_BYTES:
                raise receipt.InvalidInput("Trace: input exceeds the supported size.")
            digest.update(line)
            if not line.strip():
                continue
            index += 1
            event = receipt.decode_object(line, "Trace lifecycle event")
            # The receipt parser validated this shape before the lifecycle pass.
            try:
                lifecycle.observe(event, index, intake_id)
            except (AttributeError, KeyError, TypeError):
                raise receipt.InvalidInput("Trace: invalid lifecycle event.") from None
    if digest.hexdigest() != expected_digest:
        raise receipt.BindingFailure("Trace: SHA-256 changed during ordering verification.")
    return lifecycle


def read_marker(output):
    if not isinstance(output, str) or not output.startswith("{"):
        return None
    try:
        marker = receipt.decode_object(output.encode("utf-8"), "Intake marker")
    except (receipt.InvalidInput, UnicodeError):
        return None
    return marker if marker.get("type") == "pia.intake" else None


def marker_matches(lifecycle, expected):
    return (
        lifecycle.marker_count == 1
        and lifecycle.marker_exit == 0
        and lifecycle.marker == expected
        and type(lifecycle.marker["schema_version"]) is int
    )


def order_check(trace_path, intake_data, classification_data, result):
    trace = receipt.read_trace(trace_path)
    result["trace_sha256"] = trace.digest
    result["intake_sha256"] = sha256(intake_data)
    result["classification_sha256"] = sha256(classification_data)
    if not trace.complete:
        raise PartialEvidence("Trace: a complete single turn is required.")

    marker = parse_intake(intake_data)
    commands, intake_id = parse_classification(classification_data, trace.digest, marker["intake_sha256"])
    lifecycle = read_lifecycle(trace_path, trace.digest, intake_id)
    completed_ids = lifecycle.completions.keys()
    if commands.keys() - completed_ids:
        raise receipt.BindingFailure("Classification: includes a command absent from the trace.")
    if completed_ids - commands.keys():
        raise PartialEvidence("Classification: omits a recorded command.")
    if not marker_matches(lifecycle, marker):
        raise receipt.BindingFailure("Trace: intake completion lacks the exact successful receipt.")
    evidence_ids = [key for key, label in commands.items() if label == "evidence"]
    intake_completed = lifecycle.completions[intake_id]
    first_evidence = min((lifecycle.starts[key] for key in evidence_ids), default=None)
    result["facts"].update(
        declared_commands=len(commands),
        evidence_commands=len(evidence_ids),
        intake_completed_event=intake_completed,
        first_evidence_started_event=first_evidence,
    )
    if first_evidence is not None and first_evidence <= intake_completed:
        raise receipt.BindingFailure("Trace: declared evidence started before intake completed.")
    if lifecycle.unsupported or first_evidence is None:
        raise PartialEvidence("Trace: unsupported events or no declared evidence prevent a positive order check.")
    result["status"] = "passed"


def order_result():
    return {
        "schema_version": receipt.SCHEMA_VERSION,
        "status": "failed",
        "scope": ORDER_SCOPE,
        "trace_sha256": None,
        "intake_sha256": None,
        "classification_sha256": None,
        "facts": {},
        "errors": [],
    }


def read_order_inputs(args):
    return (
        read_bytes(args.intake, "Intake", receipt.MAX_SIDECAR_BYTES),
        read_bytes(args.classification, "Classification", receipt.MAX_SIDECAR_BYTES),
    )


@dataclass
class ExecutionSnapshot:
    """Expose captured runner bytes through the existing checker's file reader."""

    data: bytes

    def is_file(self):
        return True

    def open(self, mode):
        return io.BytesIO(self.data)


def checked_receipt(trace, execution, *, report=None, claims=None):
    result, code = receipt.evaluate(SimpleNamespace(
        trace=trace, execution=execution, report=report, claims=claims,
    ))
    if code:
        error_type = {1: receipt.BindingFailure, 2: receipt.InvalidInput, 3: PartialEvidence}[code]
        raise error_type(" ".join(result["errors"]))
    return result


def recorded_facts(result):
    lines = ["\n\n## Recorded execution facts\n"]
    for key, label in receipt.FACT_LABELS.items():
        value = result["facts"][key]["value"]
        lines.append(f"- {label}: **{'unknown' if value is None else value}**")
    lines.extend((
        "- All-tool total: **unknown**",
        "- Byte totals: **unknown**",
        "",
        FINAL_SCOPE,
        "",
    ))
    return "\n".join(lines).encode("utf-8")


def commit_manifest(output, manifest, inputs):
    data = json_bytes(manifest)
    # Stage a closed, verified file on the same filesystem, then publish it
    # with a hard link that cannot replace an existing destination.
    fd, name = tempfile.mkstemp(prefix=".pia-manifest-", dir=output)
    staged = Path(name)
    committed = False
    try:
        with os.fdopen(fd, "wb") as stream:
            write_blocks(stream, (data,))
        verify_file(staged, sha256(data), "Manifest staging file")
        for key, path in inputs.items():
            if path is not None:
                verify_file(path, manifest["input_hashes"][key], f"{key.capitalize()} input")
        os.link(staged, output / "manifest.json")
        committed = True
    finally:
        try:
            staged.unlink()
        except OSError:
            if not committed:
                raise


def finalize(args):
    if (args.intake is None) != (args.classification is None):
        raise receipt.InvalidInput("Ordering requires both intake and classification inputs.")
    execution_data = (
        read_bytes(args.execution, "Execution receipt", receipt.MAX_SIDECAR_BYTES)
        if args.execution is not None else None
    )
    execution = ExecutionSnapshot(execution_data) if execution_data is not None else None
    preliminary = checked_receipt(args.trace, execution)
    trace_digest = preliminary["trace_sha256"]
    ordering = "not_checked"
    order = None
    if args.intake is not None:
        order = order_result()
        order_check(args.trace, *read_order_inputs(args), order)
        if order["trace_sha256"] != trace_digest:
            raise receipt.BindingFailure("Trace: SHA-256 changed between validations.")
        ordering = "verified"

    suffix = recorded_facts(preliminary)
    body = read_bytes(args.body, "Body", receipt.MAX_INPUT_BYTES - len(BODY_PREFIX) - len(suffix))
    try:
        body.decode("utf-8")
    except UnicodeError:
        raise receipt.InvalidInput("Body: expected UTF-8.") from None
    input_hashes = {
        "trace": trace_digest,
        "body": sha256(body),
        "execution": sha256(execution_data) if execution_data is not None else None,
        "intake": order["intake_sha256"] if order else None,
        "classification": order["classification_sha256"] if order else None,
    }
    report_digest = hashlib.sha256()
    for block in (BODY_PREFIX, body, suffix):
        report_digest.update(block)
    report_hash = report_digest.hexdigest()
    claims_data = json_bytes({
        "schema_version": receipt.SCHEMA_VERSION,
        "trace_sha256": trace_digest,
        "report_sha256": report_hash,
        "claims": {key: fact["value"] for key, fact in preliminary["facts"].items()},
    })

    output = safe_destination(args.output)
    output.mkdir(mode=0o700)
    report_path = output / "audit.md"
    claims_path = output / "claims.json"
    write_private(report_path, BODY_PREFIX, body, suffix)
    write_private(claims_path, claims_data)
    final_receipt = checked_receipt(args.trace, execution, report=report_path, claims=claims_path)
    if final_receipt["trace_sha256"] != trace_digest or final_receipt["report_sha256"] != report_hash:
        raise receipt.BindingFailure("Trace or report: SHA-256 changed during final validation.")
    final_receipt.update(scope=FINAL_SCOPE, ordering=ordering, order_check=order, input_hashes=input_hashes)
    receipt_data = json_bytes(final_receipt)
    write_private(output / "receipt.json", receipt_data)

    output_hashes = {"audit.md": report_hash, "claims.json": sha256(claims_data), "receipt.json": sha256(receipt_data)}
    for name, expected in output_hashes.items():
        verify_file(output / name, expected, "Bundle output")
    manifest = {
        "schema_version": receipt.SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "status": "passed",
        "scope": FINAL_SCOPE,
        "ordering": ordering,
        "receipt_status": final_receipt["status"],
        "input_hashes": input_hashes,
        "output_hashes": output_hashes,
        "limitations": LIMITATIONS,
    }
    commit_manifest(output, manifest, {key: getattr(args, key) for key in input_hashes})
    return manifest


def main(argv=None):
    parser = ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    intake_parser = commands.add_parser("intake")
    order_parser = commands.add_parser("check-order")
    finalize_parser = commands.add_parser("finalize")
    for subparser, required in (
        (intake_parser, ("spec", "output")),
        (order_parser, ("trace", "intake", "classification")),
        (finalize_parser, ("trace", "body", "output")),
    ):
        for name in required:
            subparser.add_argument(f"--{name}", type=Path, required=True)
    for name in ("execution", "intake", "classification"):
        finalize_parser.add_argument(f"--{name}", type=Path)

    args = parser.parse_args(argv)
    result = order_result() if args.command == "check-order" else {
        "schema_version": receipt.SCHEMA_VERSION,
        "status": "failed",
        "scope": FINAL_SCOPE if args.command == "finalize" else "Intake bytes and receipt.",
        "errors": [],
    }
    code = 0
    try:
        if args.command == "intake":
            result = intake(args)
        elif args.command == "check-order":
            order_check(args.trace, *read_order_inputs(args), result)
        else:
            result = finalize(args)
    except receipt.BindingFailure as exc:
        code = 1
        result["errors"].append(str(exc))
    except receipt.InvalidInput as exc:
        code = 2
        result["errors"].append(str(exc))
    except (OSError, RuntimeError):
        code = 2
        result["errors"].append("Input/output operation failed or destination is unsafe or already exists.")
    except PartialEvidence as exc:
        code = 3
        result["status"] = "partial"
        result["errors"].append(str(exc))
    print(json_bytes(result).decode("utf-8"), end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
