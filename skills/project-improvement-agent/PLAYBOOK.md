# Portfolio review playbook — 1.1.0

## Inputs, authority, limits

Input: current manual request, optional goals/priorities, scope exclusions, mode and private store. For requested-but-missing capabilities, use [focused audit](references/focused.md) and its current project/chat scope. Bare broad invocation retains its default scope of all accessible project work: Codex/ChatGPT projects and active/archived chats; recognizable local folders, repositories, documents, skills, agents and outputs; relevant connected materials. Discover actual capabilities, do not assume account-wide access.

Default per-session limits: 30 minutes, 40 external calls, 120 state events, 300 newly inventoried projects, 30 examined materials, 2 MiB examined text, three deep reviews, three total repair attempts; serial coordinator, zero workers and zero paid API budget. All phases and repairs share these caps. Adjust only within an explicitly recorded finite run contract; raising limits needs current resource assessment, not an automatic retry. Stop earlier at resource/authority boundaries. Helper caps are a backstop; track calls/bytes before issuing reads and charge them with `usage` events, including failures.

The default three deep reviews is a maximum and selection target, not a quota for recommendations. Fewer may be justified by evidence or time; document the reason. Never force changes. Sources remain read-only; private inventory/reports are the only run writes. No automation or outbound messages. Keep prior user decisions. Credentials, account tokens, raw chat archives, dependency/vendor caches and recovery stores are outside discovery targets.

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
