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


## Supported history and GUI recovery (1.3.1)

The [recovery procedure](skills/project-improvement-agent/references/history-and-host.md) distinguishes an oversized reader response, available turn/item pagination, an already-paginated store, and an unavailable host interface. Where the installed CLI and current permissions support it, a finite foreground stdio connection can read selected turn/item pages without resuming a chat or starting a model turn. It preserves unread boundaries and original-message provenance. It adds no daemon, migration mutation or shared-chat workaround.

The [desktop checklist](skills/project-improvement-agent/assets/invocation-checklist.md) accepts inspected user-supplied screenshots as a distinct evidence kind. It records visible state and unknowns separately for natural, explicit and non-audit cases. A screenshot or user-observed result does not imply agent GUI access or certify unseen state. Host-dependent checks retain concrete operator and host-owner acceptance steps.
