# Save intake before evidence; finalize after execution

Use this fixed workflow when a supported Codex CLI trace and designated private files are available. The optional Python 3.9+ [session helper](../scripts/audit_session.py) performs local file operations only. It does not launch an audit, model, connector or project code. Keep its files outside reviewed repositories and the installed skill. Existing run limits include these reads/writes and remain controlling; parser ceilings are not a larger audit budget.

## 1. Freeze the intake

Before reading project evidence, original history, earlier findings or a prior audit report, save the current scope and outcome criteria. The current user request and governing skill instructions may be read first. Minimal ownership/resource checks may precede intake but must not inspect project findings. An instruction file examined as evidence about a project is an evidence read; do not relabel that use as governing. If scope is uncertain, record null and its reason, then resolve it within the frozen scope rather than guessing a project.

Reuse the task's existing private storage with a new run-specific record. Do not create a second portfolio inventory or take another writer's lease. Prepare an intake spec from the current request and governing contract:

```json
{
  "schema_version": 1,
  "run_id": "example-focused-run",
  "scope": {"chat": "current-chat", "project": null, "basis": "Current manual request; project identity not yet evidenced"},
  "criteria": [
    {"id": "coverage", "expected": "Name examined and unread evidence boundaries", "method": "Compare actual reads with the report"},
    {"id": "precision", "expected": "Every unfinished commitment has original request and current-state evidence", "method": "Independent requirement-by-requirement review"},
    {"id": "decisions", "expected": "Preserve completed, corrected, rejected and deferred decisions", "method": "Compare original turns, current artifacts and stable IDs"},
    {"id": "output", "expected": "Every action has impact, dependencies, acceptance and a standalone prompt", "method": "Inspect the final focused-audit checklist"},
    {"id": "readonly", "expected": "Project evidence is unchanged", "method": "Compare before/after evidence hashes"}
  ]
}
```

Use actual current identifiers and criteria. The example is not an assertion of evidence access. Save the spec privately in a separate command, then run the intake helper alone:

```sh
python3 scripts/audit_session.py intake --spec /private/run/spec.json --output /private/run/intake.json
```

Commands are relative to the installed skill; use an absolute helper path from another working directory. Use canonical paths with no symlinked output ancestors. The output must not exist. Intake validates the spec, preserves its bytes, and prints a `pia.intake` receipt after successful readback. Only then collect project evidence. For an order-checkable CLI run, use recorded command executions for intake and project reads; other actionable tool shapes remain unsupported by this adapter and cannot acquire a passed ordering claim. The intake command stdout must contain exactly the one JSON receipt printed by the helper (trailing whitespace is allowed). Do not add status messages, echo commands, spec-writing output or other stdout to that command; create the spec in an earlier separate command. Do not combine evidence reading with the intake command. This explicit completion-before-read boundary is needed for later order validation.

On hosts without this helper/trace, save equivalent scope/criteria in the existing private run record before evidence collection. Mark mechanical ordering unverified. A timestamp or a later claim that criteria existed earlier is not a substitute for recorded order. Do not restart an audit merely to erase a late intake; preserve the deviation and obtain a new run only within current authority and bounds.

## 2. Complete the audit

Follow the focused or portfolio contract. Inspect actual source and original requests read-only, retain stable requirement IDs and decisions, and produce a body report that passes the semantic/action-completeness checks. Do not invent exact current-run shell/tool/byte/time totals. The finished trace is not available until execution ends. Unsupported totals remain unknown; observed collection spans are not whole-run duration.

The existing authorized runner/operator retains the actual completed JSONL trace and, if available, a duration receipt bound to its exact SHA-256. No new runner, background service or model worker is supplied by this package. Keep raw traces private and preserve the original body/report and any failures.

## 3. Independently classify recorded commands

After the run, inspect every actual command and its effects against the evidence scope. Save a classification sidecar:

```json
{
  "schema_version": 1,
  "trace_sha256": "<exact trace SHA-256>",
  "intake_sha256": "<exact intake SHA-256>",
  "commands": {"item_0": "governing", "item_1": "intake", "item_2": "evidence", "item_3": "other"}
}
```

Use IDs from this trace, not these illustrative IDs. Cover every command exactly once. `governing` means instructions used only to operate the audit; `evidence` includes original turns, project outputs, prior findings and reports used for conclusions; `other` covers non-evidence bookkeeping. Exactly one command is the successful intake. A mixed intake/evidence command or misclassified evidence read fails independent semantic review even if its JSON labels pass a structural check. Do not change labels just to admit a failed run.

```sh
python3 scripts/audit_session.py check-order --trace /private/run/trace.jsonl --intake /private/run/intake.json --classification /private/run/classification.json
```

The check requires intake completion before every declared evidence command **starts**, including overlapping commands. It binds the exact intake marker and inputs, requires complete command lifecycle/classification coverage and preserves unsupported actionable/tool events as unknown. Passive agent messages/reasoning are not evidence-read proof. Missing starts, stale bindings, duplicate lifecycles or incomplete turns cannot pass. The result proves order within the supplied trace/classification; it does not authenticate the producer, validate the labels or prove absence of unrecorded reads. Retain independent semantic classification review separately.

## 4. Finalize the completed run

Use the saved body and actual finished trace:

```sh
python3 scripts/audit_session.py finalize --trace /private/run/trace.jsonl --body /private/run/body.md --execution /private/run/runner.json --intake /private/run/intake.json --classification /private/run/classification.json --output /private/run/final
```

Omit `--execution` if no valid bound runner duration exists; duration remains unknown. A known zero is valid. Omit both ordering arguments when order cannot be checked; the result must say `not_checked`. Supplying only one is invalid. Optional order evidence, when supplied, must pass. A complete trace may contain failed shell commands; they are counted accurately, not hidden or confused with a failed receipt check.

The finalizer preserves the body bytes in a narrative section explicitly outside mechanical certification, then generates supported recorded-execution facts. It writes `audit.md`, exact-byte-bound `claims.json`, and a separate `receipt.json`. It verifies actual output bytes before exclusive-writing `manifest.json` last. The manifest records the exact output hashes, input hashes, version, scoped status, ordering checked/not_checked and limitations. It excludes its own recursive hash. No receipt or self-hash is injected back into the final report.

The output directory must be new, including when an existing directory is empty. Files/directories are private. The local output filesystem must support ordinary hard links: the helper stages the verified manifest inside the output directory and publishes it with an exclusive hard link, then removes the owned staging file. On a failed write/readback, no valid success manifest is produced. An interrupted write can leave an incomplete directory: preserve and inspect it; do not blindly overwrite or treat its mere presence as success. No hostile concurrent-writer or power-loss durability guarantee is claimed.

Exit codes: 0 scoped success, 1 contradicted claim/binding/order, 2 invalid input or local operation, 3 incomplete/unsupported evidence. Inspect actual status and errors. Input hashes must remain consistent through finalization. Revalidate claims with [audit_receipt.py](../scripts/audit_receipt.py) if the delivered report changes; never reuse a stale binding.

## 5. Review and deliver

Independently compare narrative claims with original evidence and the generated facts. A passing receipt/manifest certifies neither arbitrary prose nor recommendation quality. Keep unsupported clocks, catalog totals, all-tool totals and byte counts unknown. Hashes establish byte identity, not host authenticity. Deliver the final report with its precise coverage and evidence scope, preserve raw originals privately, and retain any failed ordering or semantic checks. This workflow creates no desktop GUI evidence and recovers no hidden chat history.
