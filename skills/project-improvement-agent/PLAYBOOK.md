# Portfolio review playbook — 1.13.0

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

Every recommendation needs project identity/targets, specific evidence and confidence, problem/opportunity, proposed change, benefit, effort, tradeoffs, dependencies, questions, observable acceptance checks, preservation constraints and a standalone implementation prompt. Follow assets/implementation-prompt.md. The prompt must work without this chat; include the context and evidence locators rather than “as discussed.” Allow implementation choices to follow current evidence. Do not include secrets or unnecessary private text. For broad/comprehensive finding records, save optional model, reasoning_effort and destination fields when supplied. The existing effort field is a workload estimate. A copied prompt includes supplied dependencies and routing. Missing routing stays explicitly unknown. Prompts remain private and unsent.

A finished run may use the opt-in [session finalizer](references/session.md) to preserve its narrative, generate recorded facts and bind the actual final report. Validate declared intake/evidence order separately and independently inspect command classifications. The current audit cannot certify its own totals before its trace finishes.

When execution claims rely on a supported saved trace, follow [receipt verification](references/receipts.md): generate evidence facts, bind the structured claims to the exact report and trace, and run the checker before delivery. A failed/partial gate blocks the affected verified claim; unsupported hosts or unavailable receipts remain explicit unknowns. Keep raw traces private. Use [history and host recovery](references/history-and-host.md) for oversized original turns and invocation observations. Save a one-operation selected plan before invoking its optional reader. Verify the actual evidence bytes and last accepted boundary, then run a separately authorized changed-turn check from the saved method when qualifying reuse.

When the request calls for the whole selected history, choose an explicit terminal cutoff and use the [closed-history walk](references/history-and-host.md) with a saved private plan. Keep the active request separately as current input. In live qualification, standard pages with single-item fallback ended 15 of 24 selected turns at 512 probes and 16 at 1024. A fresh `bounded_large_pages` plan then ended 17 turns at its 128 MiB ceiling. A separately authorized 512 MiB plan using the same strategy completed all 24 selected turns, matching 6,790 ordered items against an independent read. Choose the finite limits from observed volume and retain each prior receipt with its original plan. The walker charges local work and rechecks time after saving intent because a delayed write previously led to a launch after the active deadline.

For changed-input qualification, save a fresh plan and output with the newly selected cutoff. Compare the independently observed scope, ordered records, per-turn ends and totals, and check the remaining limits. Record complete observed coverage only for that cutoff, with snapshot consistency unverified.

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


### Reuse a verified selected-history plan

Inspect the newest private receipt and confirm its transport, original plan hash, selected scope, elapsed and received-byte counters, last accepted boundary and process cleanup. During qualification the installed app-server emitted a notification with an integer emittedAtMs field. A first read refused that observed envelope. The reader now accepts and counts this metadata while discarding the notification body. It still refuses server requests. An actual selected read then recovered one original user item and stopped at its record limit. Preserve the failed observation and keep the unread continuation partial.

For an authorized changed-turn check, use the same [selected-history procedure](references/history-and-host.md) with a different known turn in the selected chat. Set its turn_id in a new plan and start without a cursor unless a cursor is already verified for that exact new scope. Use a fresh output directory. Independently compare the actual private user item and turn IDs with the expected changed selection and verify group cleanup. Keep the original receipt and do not report either bounded read as a full-chat recovery.

The independent transport check caught an earlier one-byte probe beyond the configured receive ceiling. The reader now stops at the ceiling and validates complete buffered responses there. Verify both the exact-cap success case and the one-byte-short failure case from the actual stdout and stderr counters. A page that needs more bytes leaves its previous validated cursor unchanged.


### Recheck one oversized selected item

An actual standard read at a saved selected-turn cursor stopped at 131072 received bytes with no accepted record and left that cursor unchanged. The larger profile makes a new chosen receive allowance visible in a separate plan. Use the [single-item large-page procedure](references/history-and-host.md#select-a-larger-budget-for-one-known-turn-and-item) only for an authorized known turn, with one page and one item and an explicit finite byte budget. Keep the original failing receipt and exact selected scope. Do not infer an item size or a permission failure from the wire count.

Independently check the returned item identity, exact user text or minimized non-user hash, returned cursor, actual received count and confirmed process cleanup. Preserve a size/time stop and its unread boundary. For a changed-input qualification, save the new known turn or exact cursor and expected item before the run. Use the same procedure with a new private plan and output directory, then compare the original and changed receipts and retain remaining gaps.

Qualification of the explicit larger profile recovered the same previously unread item and matched an independently recorded identity, minimized non-user hash and returned cursor. A changed-turn read from this saved method also matched independently witnessed original user text. Both reads stopped at their one-record limits with confirmed cleanup; keep their remaining history partial. The normal mode continued to stop at its unchanged byte ceiling.


### Resolve a reference to one historical assistant message

The default reader retained the identity and hash of an earlier answer while omitting its body. That preserved privacy but left the user's reference to numbered recommendations unresolved. Keep the minimized receipt. When the exact referent is necessary and currently authorized, use the [one-message selection](references/history-and-host.md#recover-one-selected-visible-assistant-message). Save a new one-page plan bound to the already observed item ID and hash, the exact known turn and its returned page boundary. Keep the output private.

Verify the new receipt and actual records against the expected identity, canonical hash, text, observed phase and returned boundary, including process cleanup. Treat a null phase as unknown. Compare the original user's wording with the recovered list in order, record which entries they selected, and preserve the original evidence status of the recommendations. A source finding does not establish reproduction or implementation. Leave unresolved references open if the page or evidence does not match.

To qualify reuse with a changed item, choose another already identified visible assistant message from authorized evidence. Save its own ID, expected hash, verified page scope and expected observed phase before the read. Run the same procedure with a new plan and output. Check the actual private records and receipt against the independently observed changed item, boundary and phase. Keep commentary labeled commentary.

### Close a selected history prefix

An actual bounded selected read can succeed while the chat's item coverage is still partial. Start a separate [closed-prefix walk](references/history-and-host.md#walk-a-complete-closed-prefix-when-needed) only when the requested audit needs full observed coverage of that one chat. Before it starts, bind the selected terminal cutoff and an explicit finite override for the actual probe, byte, elapsed and record costs. Keep active and after-cutoff inputs outside the closed-history claim.

Stop after an orderly bounded prefix and inspect the saved state and probe hashes. Resume from that exact private directory, confirm fresh matching turn inventory before item progress, and preserve any unresolved scope. Check the original and resumed bytes against the recorded plans, per-turn cursors, ordered exact user text and minimized non-user identities, and verify confirmed process cleanup. A complete_observed result requires a final matching turn inventory and every selected turn's explicit end. A separate changed-input qualification uses its own selected cutoff and expected evidence and never spends the previous run's saved capacity again.


The selected-context procedure has also been exercised on two different visible messages from a real bounded page. The primary recovered numbered recommendation context; the changed input retained its observed commentary phase. Keep these outcomes separate from the earlier proposals' implementation status. A baseline model's pre-RPC startup failure remained a failed attempt with unknown cause. Use the normal approved foreground route when required by the host; never turn a transport failure into guessed source text or silently retry under a different policy.

- Before resuming a saved history gap, compare newer verified coverage for the same thread and cutoff. When a batch exceeded its byte cap and a one-item probe advanced the cursor, continue that turn with one-item pages. The adaptive walker restores batching at the next turn.

### Check copied recommendation prompts

A report formerly showed routing or dependencies elsewhere while omitting them from the copied block. Literal backtick fences inside a field could also end that block early. The shared renderer now includes model, reasoning effort, destination, dependencies and every prompt field in one fence longer than any backtick run in its content. Focused actions also retain their requirement ID and original request basis.

Before handing off a recommendation, copy only its block and compare it against that record's supplied routing, dependencies and seven prompt fields. Keep workload effort separate from reasoning effort. Legacy records with missing routing show Unknown (not supplied). Empty or invalid supplied routing shows Unknown (invalid supplied value), requiring clarification in the report rather than a guessed model choice.

For changed-input qualification, save a second synthetic finding with a different model, reasoning effort, destination, dependency and context. Include a literal multiline fence. Run the same read-only report command from the [state procedure](references/state.md), compare the actual copied block with those new fields and ensure verification remains inside its fence. Compare state bytes before and after both reports. Record source findings and planned checks with their original evidence status.


### Verify omitted user content

A synthetic provider check found that malformed image, audio, skill and mention parts were accepted while only their aggregate omission count was saved. The reader now checks each recognized non-text variant against the inspected provider schema before accepting the page. A failed part rejects that entire page and preserves any earlier accepted page and cursor. The output keeps an aggregate omission count and a bounded count by type, allowing the audit to name omitted modalities without saving their locators or bodies.

Before interpreting a user record as evidence, inspect omitted_nontext_parts and, when present, omitted_nontext_parts_by_type. Images and audio remain unread attachments. Skills and mentions remain omitted references. An item count or page end alone cannot establish the meaning of those parts. Text-only records keep the existing projection. Older records with just an aggregate count leave the modality mix unknown.

For a changed-input qualification, provide a different synthetic mix of the supported non-text variants and use the same saved selected-history plan with a fresh private output. Compare the returned type counts and aggregate with the known fixture, verify exact text and absence of locators and bodies, and check cleanup. Include a malformed part on a second page to confirm that the first page remains accepted and its cursor is preserved. Keep helper versions pinned with unfinished historical walks because their saved state binds both source hashes.

### Compare repeated history observations

Turn inventories can match even when item text differs. When checking for this kind of change, follow the comparison procedure in references/history-and-host.md. Compare only completed observations made with matching scope and projection versions. Keep the two receipts and report exactly what agreed or differed. Attachment counts identify unexamined inputs. If the user separately supplies media, identify what you actually viewed and record its provenance before associating it with a historical item.


### Continue after an already covered turn

A small continuation after a previously covered prefix needed a separate private script because the walker always selected all item bodies up to its cutoff. Use the [closed-range option](references/history-and-host.md#select-a-closed-range-after-an-earlier-turn) when the current task authorizes only later history. Save the earlier terminal turn as after_turn_id and the inclusive new terminal cutoff as through_turn_id in a fresh plan and private output. Keep the earlier receipts separately.

Check that the provider inventory contains both endpoints in order. The walker inventories turn metadata, rechecks the anchor and selected rows, and requests item bodies only after the anchor through the new cutoff. Equal endpoints cover an empty range only after metadata revalidation. Missing, reversed or changed boundaries leave the read partial. The range digest identifies both endpoints, anchor metadata and selected projection; it cannot establish earlier item coverage.

To qualify changed input, save a fresh plan selecting a different known terminal anchor/cutoff from the same authorized provider scope. Independently compare item requests, ordered selected records and closed item scopes against that interval. Pause at a finite probe limit, verify a partial digest is absent, then resume with the same source versions and confirm fresh matching anchor/suffix metadata before additional item calls. Check cleanup and retained shared usage. Preserve snapshot consistency as unverified.


### Verify a witnessed slow final write

A hosted scope test reached its terminal observation but a final durable write exceeded the reserved 250 ms. The walker correctly left a partial snapshot and invocation marker, which ordinary resume refused. When this timing-only stop follows complete observations and the final durable marker write still finishes within the original deadline, version 1.11.0 can release a finalization_witness in captured stdout. It binds the exact frozen snapshot and invocation. Keep that capture private with the original run.

Follow [final-write verification](references/history-and-host.md#verify-a-witnessed-final-write) after the originating process has exited. Run the public verifier from a distinct process with the run directory and captured stdout. It replays the exact source/plan/journal/receipts and selected ends under its own finite local verification limits. A derived complete result and digest do not change the original partial snapshot or reopen collection. Missing or conflicting witnesses, active origins, pending probes and old uninstrumented markers remain refused.

For changed-input qualification, save a fresh selected plan, private output and stdout capture for a different terminal scope. Use the same saved verification command after that originating process exits. Compare the derived digest and selected records against independently observed changed evidence. Check run-file hashes and provider call counts before and after verification, repeat it to confirm idempotence, and keep any failed or over-budget result partial. Keep exact closing duration unknown when the witness only certifies the original deadline bound.


### Inspect older committed history evidence

An older terminal-looking partial retained useful hashed records but could not use the newer final-write witness verifier. The [committed-evidence inspector](references/history-and-host.md#inspect-supported-older-committed-evidence) now replays only exact qualified released formats without running the archived producer. Its result identifies retained observations and missing scope while leaving original completion and deadline compliance unverified.

Run the inspector on the quiescent original private directory after checking its owner. Compare its trusted producer pair, raw plan binding, committed probe hashes, record counts and closed versus incomplete scopes with independent retained evidence. A pending next slot has an unknown outcome. Its directory may contain incomplete or complete-looking files, but those bytes are excluded. A producer-rejected conflicting observation is refused rather than counted as a recovered item. Preserve the original run, marker, budgets and stopped decisions.

For changed-input qualification, use a separately saved known partial with a different selected scope and stop point. Follow the same saved inspector command, compare its committed counts, partial cursor and unreached scopes against the independently frozen fixture, and verify all original files and provider call records remain identical. Repeat inspection to confirm the same committed digest. A successful inspection never authorizes collection or implementation of historical requests. Use the earlier helper versions for a separately authorized source-bound resume.


### Match early producer bytes before interpreting the archive

An older saved 1.6 artifact was refused by the first inspector because its reader version, missing view field and page-reset behavior differed from the current engine. The inspector now selects a small compatibility profile from the exact observed walker version and both source hashes. It checks every original receipt reader version before adapting a local copy for pure replay. It never changes installed version globals or loads code from a run.

Follow the [supported-source registry](references/history-and-host.md#inspect-supported-older-committed-evidence). Report internal versions and compatible tagged references separately. The v1.7 release uses the same walker label as v1.6 with a different reader. The v1.8 tagged bytes use the internal walker label 1.7.1, which is also shared by an intermediate commit. Those bytes do not establish the original installed package, and no missing tag should be invented.

For changed-input qualification, use another exact tagged-source synthetic partial at a different stop point. Check the actual saved cursor and item stage: v1.6/v1.7 reset successful fallback pages to the wider count, while v1.8 keeps the single-item size until the turn ends. Verify replayed requests and committed counts through a persisted pause and distinct-process resume. Compare all original hashes and the committed digest before and after inspection. Keep old missing subtype information unknown and original completion/deadline unverified.
