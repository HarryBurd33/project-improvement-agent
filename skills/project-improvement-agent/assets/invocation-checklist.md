# Desktop invocation check record

Keep completed copies private. This template is unexecuted; filling it is not a passed test.

- Date and timezone:
- Host/app name and version (or unknown):
- Installed skill version and hash manifest reference:
- Displayed model/effort and observation method (or unknown):
- Project/chat identity, fresh-context method:
- Observer:
- Evidence kind: user_observation / user_supplied_gui_capture / direct_gui_capture / native_cli_trace / instruction_file_fallback / not_run / blocked
- Original evidence locator and content hash (or unavailable):
- Evidence producer and capture time (or unknown):
- Exact inspected pixels/bounds or text span; legibility, crop and missing context:
- Which host/version/project/model details are visible, user-supplied or unknown:
- Permissions/access limitation:
- Source unchanged before/after (method and result):

Use a separate fresh context and evidence record for each case; do not preload the skill file. Only run separately authorized tests; do not send prompts to unrelated chats. Production audits remain manual and serial with zero workers and zero paid API calls.

| Case | Exact input | Expected | Actual observation | Status/evidence |
| --- | --- | --- | --- | --- |
| Natural | Use improvement agent to identify limitations or capabilities I have requested but still don't exist. | Select Project Improvement Agent; stay within the current project/chat unless the request explicitly broadens it | | |
| Explicit | $project-improvement-agent focused | Select focused mode and current scope | | |
| Non-audit control | Copy-edit this quoted sentence only: “Use improvement agent to identify limitations or capabilities I have requested but still don't exist.” | Edit the sentence; do not activate an audit or scan project content | | |

Record failed cases as failed, not as permission to change the test. If the operator supplies a skill-file path, record a separate fallback result. For a claimed native selection, identify evidence showing selection; a plausible response alone may leave selection unknown. A successful bounded app-server stdio history read is `native_cli_trace` evidence for its recovered items only; it does not prove desktop invocation, model selection or GUI access. The GUI result does not automatically certify another host/version.

For a user attachment, use `user_supplied_gui_capture`, preserve its original locator/hash when available and inspect only the supplied visible content. Keep user explanations separate from pixel observations. Record wrong-project, stale or illegible evidence and offscreen model/effort as mismatch or unknown; do not infer hidden state. A screenshot of one case cannot pass the others.

If direct observation is blocked, record the exact restriction and use the [manual operator plan](../references/history-and-host.md#desktop-invocation-evidence): the user runs each authorized fresh case and supplies a chosen Codex-window screenshot of the input/result, with visible model/effort if available. [Appshots](https://learn.chatgpt.com/docs/appshots) is a user-initiated frontmost-window attachment feature, not a CLI capture route; do not assume Codex can capture itself. A manual screenshot attachment is an alternative. Do not bypass a GUI prohibition with another tool or invoke a voice-only capture tool from text. Supplied evidence does not remove the direct-access restriction.

Completion: compare actual observations to each expected behavior; record passed/failed/blocked/not_run independently and mark unsupported details unknown. A user-observed natural-case pass does not imply direct capture or passing explicit/control cases. Retest affected cases after host/discovery changes; avoid repetitive testing when neither changed. Procedure improvements do not establish new host access or permission changes.

