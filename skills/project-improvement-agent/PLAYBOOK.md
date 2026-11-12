# Portfolio review playbook — 1.3.0

## Inputs, authority, limits

Input: current manual request, optional goals/priorities, scope exclusions, mode and private store. For requested-but-missing capabilities, use [focused audit](references/focused.md) and its current project/chat scope. Bare broad invocation retains its default scope of all accessible project work: Codex/ChatGPT projects and active/archived chats; recognizable local folders, repositories, documents, skills, agents and outputs; relevant connected materials. Discover actual capabilities, do not assume account-wide access.

Default per-session limits: 30 minutes, 40 external calls, 120 state events, 300 newly inventoried projects, 30 examined materials, 2 MiB examined text, three deep reviews, three total repair attempts; serial coordinator, zero workers and zero paid API budget. All phases and repairs share these caps. Adjust only within an explicitly recorded finite run contract; raising limits needs current resource assessment, not an automatic retry. Stop earlier at resource/authority boundaries. Helper caps are a backstop; track calls/bytes before issuing reads and charge them with `usage` events, including failures.

The 30-material limit counts distinct project evidence items examined this run, including reads not yet recorded by the helper. Governing instructions read solely to operate the audit do not consume material slots; instructions reviewed as project evidence do. Rereads consume calls and bytes, but no additional material slot. The 40 source-access calls and 2 MiB of retrieved examined text include instruction, discovery and evidence reads, failures and rereads across all phases. Batched reads count each distinct evidence material. Reserve capacity before reading and carry intake usage into the same run; never reset counters when initializing the helper.

The default three deep reviews is a maximum and selection target, not a quota for recommendations. Fewer may be justified by evidence or time; document the reason. Never force changes. Sources remain read-only; private inventory/reports are the only run writes. No automation or outbound messages. Keep prior user decisions. Credentials, account tokens, raw chat archives, dependency/vendor caches and recovery stores are outside discovery targets.

## Before evidence — freeze scope and criteria

Read the current request and governing instructions, then save an explicit intake with scope and coverage/precision/decision/output/read-only criteria before project evidence, original history or prior findings. Ownership/resource metadata checks may precede intake; project findings may not. Instructions examined as project evidence count as evidence. Use [intake and finalization](references/session.md) for the optional helper, exact completion-before-read boundary, post-run classification review and finalized report bundle. Unsupported hosts retain an equivalent private intake and an unverified mechanical-order status. This does not reset existing run budgets or duplicate state.

## step-01 — Discover and connect

Inspect the private store before any new inventory. Discover source families and probe their actual access. Track each source's stable provider/scope key, searched scope, observation time, access result, cursor, complete/partial/blocked/unknown discovery and limits. Complete means a supported bounded scope was exhaustively listed, not every account/source is known. If no global listing or cursor exists, retain search terms/date bounds and the next query; never invent pagination.

Use stable native project IDs, repository URLs, document IDs and canonical local paths. A title match is only a possible association. Merge duplicates only with shared native identity, explicit file references, verified repository identity or matching purpose plus supporting content. Preserve aliases and source IDs; record uncertain links separately with evidence. Copies of material are aliases when identity/provenance proves it; an equal content hash alone does not prove two projects are one. Do not merge writing/coursework into software projects just because they share a directory.

## step-02 — Initially assess and rank

An inventoried-only project has no finding implied. Read a small relevant purpose artifact and current output/status before initial assessment. Record actual material/version/date and questions. Unclear purpose or missing access means blocked/needs-context. Classify the project by its purpose. Review technical and nontechnical work by their goals.

Rank provisionally when user priorities are unknown: assume completion/reliability and practical usefulness outweigh novelty. Use benefit, goal relevance, evidence strength and urgency (0–3 each) against effort and risk (0–3 each): `3*benefit + 2*relevance + 2*evidence + urgency - effort - risk`. This is a transparent sorting aid, not measured utility. Explain estimates, dependencies and ordering overrides. Do not hide dependencies inside the score. Favor high-value supported issues; speculative upgrades stay labeled and lower confidence.

## step-03 — Review in depth

Choose the strongest three candidates, diversifying types when comparable benefit warrants it. Inspect purpose/requirements, representative current deliverables and independent validation/user feedback/contradictions. Trace each material's locator and version. Depth requires evidence for every applicable facet and explicit unknowns:

| Type | Required facets |
| --- | --- |
| software / skill / agent | purpose, implementation, validation, limitations |
| writing | purpose, draft, sources, audience |
| research | question, method, evidence, limitations |
| coursework | objectives, work, feedback, gaps |
| design / other | purpose, output, validation, limitations |

Each facet links examined evidence, not merely a checked box. A missing facet prevents depth completion; retain partial progress. Adapt a type with a written rationale if necessary, retaining equivalent independent evaluation. Read supporting tests/logs as evidence; execution can be a future recommendation. Distinguish observed failures, inferred causes and speculative opportunities. Record intentional tradeoffs and successful behavior to preserve. “No worthwhile change identified” is valid.

## step-04 — Recommend and verify

Every recommendation needs project identity/targets, specific evidence and confidence, problem/opportunity, proposed change, benefit, effort, tradeoffs, dependencies, questions, observable acceptance checks, preservation constraints and a standalone implementation prompt. Follow assets/implementation-prompt.md. The prompt must work without this chat; include the context and evidence locators rather than “as discussed.” Allow implementation choices to follow current evidence. Do not include secrets or unnecessary private text. Prompts remain private and unsent.

A finished run may use the opt-in [session finalizer](references/session.md) to preserve its narrative, generate recorded facts and bind the actual final report. Validate declared intake/evidence order separately and independently inspect command classifications. The current audit cannot certify its own totals before its trace finishes.

When execution claims rely on a supported saved trace, follow [receipt verification](references/receipts.md): generate evidence facts, bind the structured claims to the exact report and trace, and run the checker before delivery. A failed/partial gate blocks the affected verified claim; unsupported hosts or unavailable receipts remain explicit unknowns. Keep raw traces private. Use [history and host recovery](references/history-and-host.md) for oversized original turns and invocation observations.

Before finalizing, independently compare each claim to the examined materials, check that alternative explanations were considered, and verify that acceptance checks could fail if the issue persists. Separate suggested change from tested benefit. Report a count of inventory, assessment, depth, blocked and deferred work only when supported. Distinguish new/changed/resolved/unchanged findings. Rejected findings do not return without materially new evidence or explicit user reconsideration; explain any reopening. Never infer resolution just because a finding disappeared.

## step-05 — Save and continue

Save inventory, evidence pointers, source observations, findings, decision history, run checks/results and the next action/verification in private storage. Finish with assets/report.md. Read back the saved status/report. A stopped run can be finished with an honest partial report even when its event/time limit is reached. The next manual session rechecks authority, access, resources and changed sources before continuing. No automatic activation. See references/comprehensive.md for exhaustive queue/change semantics.

## Outcome checks, failures and learning

| Check | Expected | Method | Evidence |
| --- | --- | --- | --- |
| check-01 | Honest source and review coverage | Compare listing limits with examined boundaries | Private source observations and report |
| check-02 | Supported recommendations and standalone prompts | Trace facts and independently read prompt fields | Private material and finding records |
| check-03 | Durable continuation and decisions | Restart with fixture or observed next action | Run records and tests |
| check-04 | Limits and read-only source behavior | Check counters, stops and source hashes | Private run usage and before/after hashes |
| check-05 | Accurate package/host claims | Structural audit plus actual host readback | Release validation and private receipts |

Freeze acceptance before every pilot/run: source coverage is honest; evidence supports recommendations; prompts are standalone; ranking assumptions are explicit; run limits respected; no source mutation; continuation and decisions preserved. Record `id`, `expected`, `method`, `status`, `evidence`, `observed` for every check. Required unknown checks prevent a completed claim. A structural audit cannot prove quality, actual access, manual invocation or absence of all secrets.

Construction lessons are added only after observed failures and retests. Reusable source stays separate from private run evidence. Keep durable state until the user requests deletion; temporary scratch may be removed after seven days. Do not copy raw transcripts by default. References, minimal excerpts, hashes and selected material boundaries suffice.

## Verified construction lessons

- Continuation must preserve the saved mode at the helper and CLI boundaries. A new comprehensive run followed by an omitted-mode start previously reverted to broad. Both paths now retain comprehensive mode; an explicit mode still changes it. Regression checks cover the installed CLI from another directory.
- Validate the complete release inventory after adding a resource. The initial package omitted NOTICE and the comprehensive reference from its index. Publication now requires exact root and skill inventories, checked local Markdown targets, and an intentional broken-link fixture that must fail. These gates supplement review of the actual staged public files.
- A publication path scanner must not match its own regex literal. Restrict the username shape and require a following directory separator; inspect actual publication bytes as the separate release gate.

- Focused audits reconcile user requests against current source, acceptance, installation and release independently. The 1.0.0 portfolio finding record could not express those distinctions or reliably separate an assistant proposal from a user commitment; the additive requirement ledger preserves both without replacing existing findings.

- Standalone prompts must carry destination, request basis and starting model/effort inside the copied prompt. Report fields outside the prompt are insufficient for handoff; focused rendering now repeats these fields in the copyable block. Evidence role is part of evidence identity so an acceptance observation cannot collide with an otherwise identical user/artifact record.

- Enforce focused scope at startup, shared-record updates and status rendering as well as project events. A focused start previously changed an unrelated deep review to needs-recheck and made its finding stale; status also exposed portfolio-wide counts, sources, findings, associations and the previous run's next action. Regression fixtures now snapshot unrelated records, test active/finished/continued summaries, and cover aliases, standalone chats, shared material/source rejection and broad/comprehensive controls. Canonical aliases must update the retained project, not its merged record.

- Independent behavioral validation needs an executor given only original input evidence, a separately frozen expected-results oracle, and the actual report/tool trace. Replaying preclassified helper records verifies persistence and rendering, not model judgment. Native metadata discovery, fresh native invocation and the instruction-file fallback are separate checks; fallback cannot pass native-selection acceptance. Record host-specific execution limits and retain a non-audit control rather than generalizing one host's success to every host.

- Independent model runs correctly classified requirements but omitted impact for verification-only actions and confused “do not implement during an audit” with “no worthwhile opportunity.” The requested-capability output contract now applies in every scope, requires explicit Impact and Dependencies/holds for each action, and checks the separate optional-opportunities assessment before delivery. Preserve original failed outputs and rerun affected cases with the external oracle unchanged.

- A historical audit claimed tool counts and an exact time that its retained trace could not establish. Preserve the original output, derive only supported recorded facts, bind the exact report/trace, and keep missing events unknown. The receipt checker supplements semantic review; hashes do not authenticate a host or verify arbitrary prose. Its saved procedure must be exercised on changed input before claiming reuse.

- Intake must be a standalone command whose stdout contains only the helper receipt. A native repeat correctly preserved requirements and decisions but printed a spec-save status before the receipt, so strict ordering validation rejected it. The saved instructions now require spec creation separately and intake-only stdout; a fresh changed-input repeat passed independent order and semantic review. Keep the original failure; never normalize a trace to manufacture a pass. Trailing whitespace is allowed; a leading prefix is not.

- Toolbox dependencies name indexed resource IDs, not file paths. A ready audit rejected the session helper dependency written as a path; binding the existing receipt-helper resource ID fixes resolution without changing execution. Exact inventories and the ready audit verify this relationship before delivery.

- Preserve the minimum Python version in release CI when hosted image aliases move. The first 1.3.0 branch run selected Ubuntu 26.04, which had no setup-python 3.9 build, so no tests ran on that job. Explicit compatible Ubuntu and Intel macOS images retain all four OS/Python checks; require a fresh successful matrix before publication.

- A single oversized turn can fail the native reader even when the selected chat is already paginated. A read-only migration inspection is not a recovery result, and migration is not a substitute for an unavailable item-pagination interface. Preserve the exact unread boundary; use only a supported scoped interface or provenance-preserving original excerpts. Sharing a chat creates a publication, not a private export.

- GUI evidence has a producer and visible boundary. Inspect a user-supplied image before using it, preserve its origin separately from an agent capture, and leave offscreen model settings and unexecuted controls unknown. User-controlled evidence collection does not authorize an agent to evade an explicit GUI restriction.

- A missing desktop-selector socket did not establish that every supported history route was blocked. The official CLI's finite foreground stdio transport successfully read selected turn metadata and original user items without resuming the chat. Distinguish this bounded read connection from a daemon, desktop control or model selection; require current native permissions, returned cursor namespaces, finite bounds and confirmed child cleanup. Preserve the earlier failed connector observation and remaining unread items.
