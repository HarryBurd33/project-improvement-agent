# Verify execution receipts before delivery

Use this check when a report relies on a supported saved execution receipt. It validates recorded facts and hash bindings; it does not authenticate a host, inspect the current chat, interpret arbitrary prose, or prove unrecorded activity did not happen.

The checker is read-only Python 3.9+ standard library code: [audit_receipt.py](../scripts/audit_receipt.py). Inputs are explicit private files; no connector, model call, background capture or network access is added. Keep traces, claims, reports and generated receipts outside installed/published source. Reserve and charge their reads against the same run call/byte/time limits; parser size ceilings do not enlarge the production audit budget.

For a completed current run, [intake and finalization](session.md) automates report/claims/receipt assembly after the trace is finished. It also checks declared criteria-before-evidence order with independent classification review. Use the manual procedure below for existing supplied reports or hosts where the finalizer is unavailable. Neither route authenticates the host or certifies narrative prose.

## Procedure

1. Identify the actual run and preserve its trace unchanged. Confirm its provenance through the existing run record. Do not substitute another run's trace or infer missing metadata.
2. Summarize supported recorded events:
   ```sh
   python3 scripts/audit_receipt.py --trace /private/run/trace.jsonl
   python3 scripts/audit_receipt.py --trace /private/run/trace.jsonl --format markdown
   ```
   These paths are illustrative. Run from the installed skill directory or use its absolute script path. Use the generated evidence section rather than hand-invented counts.
3. If using runner duration, supply a private JSON receipt containing `trace_sha256` and finite nonnegative `elapsed_seconds`. Optional `schema_version` must be integer 1. Bind it to the exact trace only after verifying that the runner receipt belongs to that run. Preserve the original receipt and its provenance. Adding a hash does not establish the truth of caller-supplied timing.
If the generated section needs that duration, regenerate it with `--execution` before finalizing the report.
4. Finish the actual report. Save a claims sidecar with `schema_version: 1`, exact `trace_sha256`, exact `report_sha256`, and a `claims` object. Supported claim names are `recorded_shell_calls`, `recorded_failed_shell_calls`, `elapsed_seconds`, `clock_reads`, `catalog_inspections`, and `collection_end_utc`. Omitted or null unknown claims do not assert a fact. Clock/catalog counts and exact collection time are unknown for this trace adapter.
5. Check the exact delivered bytes:
   ```sh
   python3 scripts/audit_receipt.py --trace /private/run/trace.jsonl --execution /private/run/bound-runner.json --claims /private/run/claims.json --report /private/run/audit.md
   ```
   Omit `--execution` when no bound duration is available. Nonempty claims require the actual report and its hash. After editing the report, regenerate its binding and rerun the check. A hash binds bytes, not the semantic accuracy of arbitrary prose.
6. Inspect the returned status, facts, unknowns and claim checks. Exit 0 is passed, 1 is a claim/evidence binding failure, 2 is invalid input, and 3 is partial/incomplete evidence. A partial trace or missing exit code cannot certify full execution. Never promote failed/partial evidence to a verified claim; correct the report or retain the affected unknown.
7. Independently compare the final prose with the checked fields and original evidence. Save the checker output and input hashes in the existing private run record. Recheck changed claims before delivery.

## What is and is not established

Counts refer to unique **recorded completed shell commands**, not every tool call. A known zero failed-command count is valid. Missing exit codes do not mean success. Missing clocks, catalog events or collection timestamps do not mean zero. Complete turn markers establish the supported trace shape, not global recording completeness. Unsupported or malformed formats need an explicit limitation, not a guessed adapter.

The supplied runner receipt can support a bound duration, including valid zero. It is not an independent wall clock or cryptographic attestation. There is no automatic detector for false claims elsewhere in arbitrary free prose; the final semantic review remains required.

For hosts without a supported trace, record available native receipts/user observations and explicit unknowns. Do not create a new model worker or bypass a host restriction merely to obtain a trace. Production bounds and manual activation remain unchanged.

## Discriminating examples

- Thirteen recorded successful commands and a bound claim of fourteen: fail. Correct claim thirteen: pass on a complete valid trace.
- No clock events and a claimed exact collection time: unsupported; fail the asserted claim.
- Valid zero failures or a valid bound duration of zero: preserve zero.
- Duplicate completion IDs, malformed JSON, wrong types or stale report/trace hashes: reject.
- Truncated or failed turns: incomplete/failed evidence, not a complete audit.
- A passing receipt checker does not prove recommendation quality, source access beyond the trace, desktop GUI selection or authorization.

