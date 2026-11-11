# Recover history and qualify invocation evidence

## Older or oversized history

Use original user turns and corrections. Keep the provider/chat IDs, returned cursor, examined spans, truncation and error text in private state.

If a provider reports a size limit, try a smaller supported page and output preview once within the run budget. An individually oversized turn remains an explicit boundary. Do not invent a cursor, silently skip a turn, broaden to unrelated chats, or bypass access controls.

Search the existing task's indexed, selected-message records before requesting new material. A prior summary, build plan or acceptance receipt may show what was implemented, but it cannot replace missing original user wording. Reconcile only original excerpts with preserved origin/version information. Report partial coverage when provenance is incomplete.

A recovery plan names: the unread chat/cursor/span; the needed original user requests/corrections; a supported export or user-provided relevant excerpts; the existing ledger to compare; and the acceptance check. Ask only for necessary text, not an entire private archive by default. After recovery, retain stable IDs and distinguish portfolio jobs from reusable-system commitments. No provider/export capability is implied by this method.

## Desktop invocation evidence

Use [the invocation checklist](../assets/invocation-checklist.md) for a fresh context. Preserve evidence kinds separately:

- `user_observation`: the user reports the actual result. Valid for an explicitly user-observed check, but not direct capture.
- `direct_gui_capture`: a permitted GUI observation actually shows the tested state. Record exact bounds and what is visible.
- `native_cli_trace`: a saved supported CLI trace; it does not establish desktop behavior.
- `instruction_file_fallback`: the operator supplied the skill-file path; it does not establish native relevance selection.
- `not_run` or `blocked`: no actual result or required access unavailable.

A host restriction is not a skill defect. Do not use another UI-control route to evade an explicit prohibition. If direct GUI observation is unavailable, retain the user-observed result and a concrete operator test plan. Do not claim all hosts are certified.

Only launch fresh-context tests when separately authorized. Production audits do not create workers or chats to test themselves. A release can improve its verification procedure while honestly leaving a host-dependent direct-capture check blocked.

