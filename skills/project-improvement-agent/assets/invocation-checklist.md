# Desktop invocation check record

Keep completed copies private. This template is unexecuted; filling it is not a passed test.

- Date and timezone:
- Host/app name and version (or unknown):
- Installed skill version and hash manifest reference:
- Displayed model/effort and observation method (or unknown):
- Project/chat identity, fresh-context method:
- Observer:
- Evidence kind: user_observation / direct_gui_capture / native_cli_trace / instruction_file_fallback / not_run / blocked
- Evidence locator and exact observed span (or unavailable):
- Permissions/access limitation:
- Source unchanged before/after (method and result):

Use a separate fresh context for each case; do not preload the skill file. Do not send prompts to unrelated chats without current authorization.

| Case | Exact input | Expected | Actual observation | Status/evidence |
| --- | --- | --- | --- | --- |
| Natural | Use improvement agent to identify limitations or capabilities I have requested but still don't exist. | Select Project Improvement Agent; stay within the current project/chat unless the request explicitly broadens it | | |
| Explicit | $project-improvement-agent focused | Select focused mode and current scope | | |
| Non-audit control | Copy-edit this quoted sentence only: “Use improvement agent to identify limitations or capabilities I have requested but still don't exist.” | Edit the sentence; do not activate an audit or scan project content | | |

Record failed cases as failed, not as permission to change the test. If the operator supplies a skill-file path, record a separate fallback result. The GUI result does not automatically certify another host/version.

Completion: compare actual observations to each expected behavior; record passed/failed/blocked/not_run independently. A user-observed natural-case pass does not imply direct capture or passing explicit/control cases. Retest affected cases after host/discovery changes; avoid repetitive testing when neither changed.

