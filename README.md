# Project Improvement Agent

A manually activated Codex skill that reviews technical and nontechnical projects, identifies worthwhile improvements, and produces prioritized recommendations with standalone implementation prompts. Source projects stay read-only. Private inventory, evidence and progress stay outside the reusable package.

## Focused audit and portfolio modes

**Focused requested-capability audit:** “Use improvement agent to identify limitations or capabilities I have requested but still don't exist.” Reconstruct original requests/corrections for the current project/chat, reconcile source, acceptance, installation and release, and separate unfinished commitments from optional opportunities. Standalone chats stay chat-scoped. Explicit broader requests retain their scope.

**Broad (bare invocation default):** discover accessible projects and standalone work across native project/chat tools, local folders/documents/skills and relevant connected services. Initially assess proportionately, rank promising opportunities, and deeply review up to three projects. Inventory-only entries remain distinct from actual reviews.

**Comprehensive:** continue through every discovered project across manually activated sessions. Preserve completed depth work, source cursors, uncertain associations, findings, decisions and next actions. Reobserve source versions and revisit affected findings. Unknown versions require reinspection. Completion is relative to discovered accessible inventory and recorded dates; incomplete source discovery remains visible.

No schedules, monitors, background jobs, cross-chat messages, automatic implementation, or paid API fallback. Rejecting a recommendation is durable. “No worthwhile change identified” is valid.

## Prerequisites and installation

Use a local Codex host with skills support and access to a designated private state directory. Python 3.9+ on POSIX supports the optional deterministic record helper; the method can also use an equivalent existing private task store. Account and connector access vary and are probed during each run. No API key or third-party Python dependency is required by this package.

Clone this repository, review its source, then run from the clone:

```sh
python3 scripts/install.py
```

This copies only `skills/project-improvement-agent` to `~/.agents/skills/project-improvement-agent`, checks identical hashes and refuses an existing destination. It preserves unrelated skills and configuration. For a custom user skill root use `--dest /absolute/skills-directory`. Inspect an existing installation before updating; this installer does not merge or overwrite it. File installation is distinct from native discovery and execution. Codex normally detects changes; restart if it does not appear. See [official local skill documentation](https://learn.chatgpt.com/docs/build-skills).

## Manual invocation

In a local Codex chat, audit the current project and chat with:

```text
Use improvement agent to identify limitations or capabilities I have requested but still don't exist.
```

Or use the explicit focused invocation:

```text
$project-improvement-agent focused
```

For portfolio modes:

```text
$project-improvement-agent
```

```text
$project-improvement-agent comprehensive
```

```text
$project-improvement-agent continue using /absolute/private/state
```

Continuation retains the saved mode unless explicitly changed. Default private storage: `~/.local/state/project-improvement-agent/default`. Name a writable private directory when needed, outside reviewed repositories and installed/published source. Native discovery is eligible only for explicit requests described in the skill metadata; execution still requires a current manual request. Exact natural-language selection is host-dependent. Use `$project-improvement-agent focused` or the instruction-file fallback if needed. A new chat verifies current authority, resources, source state and ownership; saved text grants no permissions.

Without native discovery, explicitly ask Codex to read the installed `SKILL.md` and follow it. This instruction-file fallback is distinct from native skill selection. No slash-command alias is implemented. The focused contract is in [focused audit](skills/project-improvement-agent/references/focused.md).

Included: [runner](skills/project-improvement-agent/AGENT.md), [playbook](skills/project-improvement-agent/PLAYBOOK.md), [state protocol](skills/project-improvement-agent/references/state.md), [comprehensive protocol](skills/project-improvement-agent/references/comprehensive.md), [toolbox](skills/project-improvement-agent/toolbox/index.json) and [report template](skills/project-improvement-agent/assets/report.md). The helper manages records; Codex performs source discovery and judgment.

## Output and bounds

Each recommendation includes project identity/targets, evidence/confidence, problem/opportunity, change/benefit, effort estimates, dependencies/tradeoffs/questions, acceptance checks, preservation constraints and a standalone prompt. Ranking is explained and provisional when priorities are unknown. Separate observed problems, inferred causes and speculative upgrades.

Every report distinguishes searched sources/limits, inventory, initial assessment, depth review, blocked work, deferrals, decisions and a verified next manual action. Supported counts replace invented totals/percentages. See the [fictional sample](examples/sample-report.md).

Default caps: 30 minutes, 40 external calls, 120 state events, 300 newly inventoried projects, 30 examined materials, 2 MiB text, three deep reviews, three shared repair attempts. Serial execution, zero workers and paid budget. The helper enforces state/time/material/depth caps and charged usage; the runner charges calls/bytes before reads. All repairs share limits. Stop with partial results and a saved continuation point.

## Validation and limitations

Run `python3 -B -m unittest discover -s tests -v` and `python3 scripts/validate.py` from the clone. CI runs Linux/macOS. [Validation evidence](docs/validation.md) separates fixtures, bounded live observations, installation and discovery. Structural checks cannot prove recommendation quality, full access, absence of all secrets or a completed portfolio review.

API caps, inaccessible archives, unenumerable services and unknown revisions remain gaps. Advisory POSIX locks and durable tokens support one cooperative local writer; no hostile-writer or cross-device lease guarantee. Checksummed atomic state and a previous copy detect some interrupted/corrupt saves; restoration needs explicit reconciliation. Back up private records through an authorized private channel separately from source.

## Contributions and license

Submit sanitized reproductions, expected behavior and version assumptions. Add discriminating fixtures, run checks and keep inventories, private reports, credentials, checkpoints and personal configuration out of commits. Do not weaken coverage or authority boundaries to satisfy tests.

MIT, copyright 2026 Harrison Black. [NOTICE](NOTICE) retains MIT notices for adapted Agent Forge contracts and the installer. [Provenance](docs/provenance.md) describes reuse. Private audit data is excluded.

## Execution evidence and host limits (1.2)

The optional standard-library [receipt checker](skills/project-improvement-agent/references/receipts.md) checks recorded CLI command counts, bound runner duration and structured claims against exact report/trace hashes. It generates an evidence section and rejects unsupported assertions; it does not authenticate evidence or interpret all free prose. Missing events remain unknown. No background collection or production worker is added.

[History recovery](skills/project-improvement-agent/references/history-and-host.md) preserves oversized/unread boundaries and distinguishes original messages from summaries. The [invocation checklist](skills/project-improvement-agent/assets/invocation-checklist.md) records natural, explicit and non-audit controls with separate user-observed, user-supplied-image, permitted direct-GUI, CLI and fallback evidence. A host restriction remains a limitation, not a claimed successful test.


## Intake and final accounting (1.3)

Save scope and outcome criteria before project evidence reads. The optional [session workflow](skills/project-improvement-agent/references/session.md) records intake, checks declared command ordering, and finalizes a completed audit into a private report/claims/receipt bundle. It generates supported totals from the finished trace, preserves valid zero and unknowns, and refuses existing destinations. A final manifest binds the verified output files. No model execution or background collection is added. Narrative correctness and actual command classifications still require independent review; unsupported hosts retain explicit unverified states.


## Supported history and GUI recovery (1.7.1)

The [recovery procedure](skills/project-improvement-agent/references/history-and-host.md) distinguishes an oversized reader response, available turn/item pagination, an already-paginated store, and an unavailable host interface. Where the installed CLI and current permissions support it, a finite foreground stdio connection can read selected turn/item pages without resuming a chat or starting a model turn. It preserves unread boundaries and original-message provenance. The optional [Python reader](skills/project-improvement-agent/scripts/read_history.py) writes private records and a receipt. Version 1.5.0 keeps the standard 128 KiB limit and adds an explicit larger budget for one item in a known turn. The manual, serial audit and its existing host-evidence boundaries still apply.

Version 1.6.0 adds an optional [closed-prefix walker](skills/project-improvement-agent/scripts/walk_history.py). It saves ordered per-turn receipts and a bounded resume state, and reports the observed scope separately from provider snapshot guarantees. The reader and walker support explicitly selected larger item pages within a known turn. The standard profiles and default audit limits remain in force unless a plan explicitly selects the larger profile.

Version 1.7.0 adds [explicit one-message assistant context recovery](skills/project-improvement-agent/references/history-and-host.md#recover-one-selected-visible-assistant-message). With a known turn, item ID and prior item hash, an authorized one-page read can retain that message's exact visible text and observed phase in private evidence. Default assistant and other non-user records remain minimized.

The [desktop checklist](skills/project-improvement-agent/assets/invocation-checklist.md) accepts inspected user-supplied screenshots as a distinct evidence kind. It records visible state and unknowns separately for natural, explicit and non-audit cases. A screenshot or user-observed result does not imply agent GUI access or certify unseen state. Host-dependent checks retain concrete operator and host-owner acceptance steps.

Version 1.7.1 preserves one-item reads through the rest of a turn after the standard adaptive walker recovers an oversized page. An orderly resume retains the recovered size.

Version 1.8.0 preserves each recommendation's supplied routing, dependencies and full prompt inside its copyable block. Missing legacy routing is explicitly unknown, workload estimates remain separate, and embedded backtick fences are enclosed safely.

Version 1.9.0 validates supported non-text user inputs before accepting a history page and records bounded omission counts by type. Attachment payloads and locators remain omitted, and older aggregate-only records leave the modality mix unknown.

Completed history walks also provide a digest of the ordered retained records. Compare separately bounded observations of the same closed scope to detect changes to the retained content even when turn metadata matches.

Version 1.10.0 adds an optional exclusive after_turn_id to bounded history walks. A fresh range inventories and validates both endpoints, reads only the selected later item bodies, and preserves its own resume state and observation digest. Earlier prefix coverage requires its separate evidence.

Version 1.11.0 adds explicit read-only verification for a captured terminal final-write witness. It derives scoped coverage under separate finite artifact checks while preserving the original partial run, marker and collection budget. The saved procedure covers captured stdout, unchanged evidence, origin exit and idempotent verification.

Version 1.12.0 adds a bounded read-only inspector for committed evidence from exact released history formats. It reports retained counts and stopped scope without certifying original completion or deadline compliance. The existing walker and reader bytes retain their previous resume and witness-verification behavior.

Version 1.13.0 extends the offline inspector to exact tagged v1.6.0, v1.7.0 and v1.8.0 source pairs. Compatibility profiles preserve their original reader versions, page-reset behavior and missing view field. Matching bytes provide a compatible source reference while the original package identity remains unverified.

Version 1.14.0 adds one exact pre-release source pair to offline committed-evidence inspection. It enforces that producer's historical 128 MiB collection ceiling and labels compatibility without inventing a release or package identity. Released profiles and the current collection helpers remain unchanged. See the [saved procedure](skills/project-improvement-agent/PLAYBOOK.md#inspect-the-explicitly-selected-pre-release-pair).
