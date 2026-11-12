# Recover history and qualify invocation evidence

## Older or oversized history

Use original user turns and corrections. Keep provider/chat/turn/item IDs, roles, source versions or timestamps when available, returned cursors, examined spans, truncation and exact errors in private state. Mark unavailable provenance unknown; never infer it from a summary. Public reports use sanitized references.

### Bounded recovery

1. Continue reading the selected chat at its exact returned cursor within the same API. For a size error, retry once with a smaller supported page and output preview within the run budget. A one-turn page can still fail because that turn is individually oversized; a short preview or omitted tool output does not prove the underlying turn can be read. Preserve the unread boundary instead of skipping it.
2. Check supported recovery routes available and authorized for that host. The [official app-server reference](https://learn.chatgpt.com/docs/app-server) documents `thread/turns/list` with `itemsView` values `notLoaded`, `summary` and `full`, and `thread/items/list`, optionally scoped by `turnId`. A missing desktop connector does not establish that all read routes are unavailable. Use an exposed authorized interface or the bounded foreground stdio route below when the installed CLI supports it. Documentation alone does not establish installed capability or permission.
3. Where those methods are exposed, use bounded turn pages to locate the relevant turns and item pages to retrieve the needed original user text and corrections. `notLoaded` and `summary` are navigation evidence, not recovered original wording. Copy opaque provider cursors and returned IDs unchanged; do not derive IDs from labels or offsets. Preserve role and version information with the exact recovered text. Record each covered span and each gap separately.
4. Stop that recovery route on a repeated cursor, no progress, unsupported operation, access denial, exhausted budget, or a page still oversized after the single smaller-page retry. An oversized item remains a gap even when adjacent items are readable. Do not invent a cursor, silently omit a turn, broaden to unrelated chats, or claim complete coverage from partial results.

### Bounded foreground stdio route

The official app-server reference supports `codex app-server --stdio`. When the installed CLI/interface and current selected-history scope permit it, a finite foreground subprocess can read history without resuming the chat or generating a model turn. Verify the installed CLI's supported methods/schema first. This is a read route, not desktop model selection or GUI access.

- Fix the selected chat and limits before launch. Default ceilings per probe are 15 seconds, two turn pages, two item pages, 20 total returned turns/items and 128 KiB of received output; use tighter run limits when applicable. Count the single smaller-page retry within those ceilings and stop at the first bound.
- Allow only `initialize`, the `initialized` notification, `thread/turns/list` and `thread/items/list`. Start with that API's own turn metadata (`itemsView: "notLoaded"`); use a returned `turnId` to scope item reads to a needed turn. Do not pass a desktop/UI cursor into a different API namespace. Use only that route's opaque returned pagination cursors, preserving the correspondence and any unmapped boundary as unknown.
- Use current native permissions and the normal native approval flow if required for this already authorized read. A startup permission error is a failed startup, not proof that the chat has no readable original text. A denied read remains controlling; do not bypass it. Do not start a daemon or network listener, discover private IPC, read raw stores/databases, migrate data, or use `thread/start`, `thread/resume`, `thread/fork`, model-turn or GUI operations.
- Close the subprocess and confirm child termination on success, timeout, size limit and every error path. Record exit/termination evidence with the private receipt. If termination is uncertain, reconcile that process before another probe; do not leave a background service or launch a duplicate.

This route adds no production worker, paid API call or runtime helper. Reading one original `userMessage` demonstrates recovery only of that item and its recorded span, not closure of the remaining history gaps.

If the installed CLI supports a selected-thread, read-only `codex migrate-rollouts --thread <selected-thread-id> --json` diagnostic, record its result and CLI version. `already_paginated` is not recovery of the unread text and does not justify `--apply`. An already-paginated chat with neither an exposed item interface nor an authorized supported CLI read route remains blocked. This procedure authorizes no migration mutation.

Search the existing task's indexed, selected-message records before requesting new material. A prior summary, build plan or acceptance receipt may show what was implemented, but cannot replace missing original user wording. Reconcile only original excerpts with preserved origin/version information; report partial coverage when provenance is incomplete. Retain stable IDs and distinguish portfolio jobs from reusable-system commitments.

### A concrete plan when recovery is blocked

Continue useful fixes supported by available evidence. Record the blocked requirement and prepare these scoped alternatives without implying that access has been enabled:

- **Host-owner prerequisite:** identify the selected chat and unread cursor/span privately. Distinguish a missing desktop connector from all authorized routes being unavailable; record the installed CLI/interface check and any stdio startup/read outcome without conflating a GUI denial with history-read authority. If no usable route exists, name the missing read-only `thread/turns/list` and `thread/items/list` capability, including the needed selected-chat/`turnId` scope, and the exact host prerequisite: expose a supported bounded reader or make the documented foreground CLI reader available under native permissions. Once available and authorized, read that API's metadata, map the needed boundary without reusing another API's cursor, and compare recovered requests/corrections with the ledger. Acceptance requires original text, recorded provenance, exact coverage and confirmed subprocess termination if used; remaining gaps stay explicit.
- **Private excerpt alternative:** identify the necessary requests/corrections and adjacent context, then have the user provide those original excerpts or a supported private export if available. Preserve the supplied source locator, role, time/version and any limits; compare with the ledger. Do not ask for an entire private archive by default or claim an export capability exists without checking.

`share_thread` publishes an immutable shared link and omits tool calls and tool input/output. It is not a default private recovery method or a full execution record. Separate explicit user authorization to publish the selected chat is required before using it; permission to read or audit that chat does not authorize sharing it. Do not offer sharing as a way around a denied read.

## Desktop invocation evidence

Use [the invocation checklist](../assets/invocation-checklist.md) for a fresh context. Preserve evidence kinds separately:

- `user_observation`: the user reports the actual result. Valid for an explicitly user-observed check, but not direct capture.
- `user_supplied_gui_capture`: the user attaches a screenshot or other GUI capture. Inspect the supplied pixels; this does not establish agent access to the desktop.
- `direct_gui_capture`: an agent-permitted GUI observation actually shows the tested state. Record the permitted route and exact visible bounds.
- `native_cli_trace`: a saved supported CLI trace, including a bounded stdio history read; it establishes only its recorded operation and coverage, not desktop behavior or model selection.
- `instruction_file_fallback`: the operator supplied the skill-file path; it does not establish native relevance selection.
- `not_run` or `blocked`: no actual result or required access unavailable.

For every capture, preserve the original attachment/file locator and content hash when available, who produced it, capture time, host/skill version and project/chat identity as visible or supplied. Distinguish visible facts from user statements. Record the exact pixels/bounds inspected, legibility and any crop or missing context; retain the original separately from derived crops. If the project is wrong, the capture is stale, or the model/effort is offscreen, record the mismatch or unknown. A screenshot proves only the state it visibly supports, not hidden settings, earlier execution or other test cases.

A host restriction is not a skill defect. Do not use another UI-control or capture route to evade an explicit prohibition. A voice-only screen-context tool is unavailable in a text conversation. Direct GUI access can remain blocked while a voluntarily supplied capture is inspected as evidence under its own provenance kind.

When direct capture is blocked, make a manual operator plan: name the relevant host/project and installed skill version; specify the three separate fresh-context cases in the checklist; have the operator run each authorized case and attach the chosen Codex-window screenshot showing the input and result, plus model/effort if visible. The [official Appshots guide](https://learn.chatgpt.com/docs/appshots) describes user-initiated attachment of a frontmost window using both Command keys on macOS or both Alt keys on Windows; it is not a CLI capture interface. Do not assume the app can capture itself. The user can instead manually attach a screenshot of the chosen Codex window. Never expand capture to unrelated windows or request permission changes as part of this procedure.

Acceptance compares each case's actual evidence with its expected behavior, preserving failed, blocked and unknown details. A natural-case screenshot does not establish the explicit or control result, and a visible response alone may not establish native skill selection. Do not claim all hosts or versions are certified.

Only launch fresh-context tests when separately authorized. Production audits remain manual and serial with zero workers and zero paid API calls; they do not create workers or chats to test themselves. A release can improve its recovery and verification procedures while honestly leaving host-dependent access blocked. No permission or host capability is created by this document.

