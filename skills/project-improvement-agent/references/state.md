# Private state helper — schema 1

Use Python 3.9+ on POSIX. Set `HELPER` to the installed `scripts/portfolio.py` and `STATE` to the absolute designated private directory. Check that it is outside the installed skill and reviewed repositories. Do not change `HOME` or `CODEX_HOME`. Create state once:

```sh
python3 "$HELPER" --state "$STATE" init
python3 "$HELPER" --state "$STATE" status
python3 "$HELPER" --state "$STATE" start --owner CURRENT-CHAT-ID --mode broad --checks /absolute/private/checks.json
```

`checks.json` is an array of frozen `{id, expected, method}` objects, normally coverage, evidence, prompts, ranking, readonly and continuation. `start` returns the exact run token. On continuation omit `--mode` to retain the previous finished mode; the first run defaults to broad. An explicit `--mode` changes it. Keep it private. It prevents another run from acquiring the same store. There is no automatic lease expiry or takeover. For interrupted runs, verify the originating chat/process has stopped and reconcile uncertain outcomes; resume events with that same token under current authority, or finish partial. `finish` is permitted after limits expire. OS advisory locking serializes individual mutations; remote/network filesystem coordination and hostile concurrent writers are unsupported.

Submit one event in a private JSON file:

```sh
python3 "$HELPER" --state "$STATE" event --token EXACT-TOKEN --json /absolute/private/event.json
```

Every identity is a stable namespaced native ID or canonical local path. Helper returns a deterministic hashed ID; use returned IDs in references. Event operations:

| op | Required fields beyond op |
| --- | --- |
| source | identity, scope, discovery (`complete`, `partial`, `blocked`, `unknown`), limits; optional cursor |
| project | identity, title, type (PLAYBOOK types), source ID |
| material | identity, source ID, locator, version (content hash/provider revision or null) |
| evidence | project ID, material ID, location (exact examined section/turns), observation (minimal facts, no raw transcript) |
| assess | project ID, evidence ID array, conclusion |
| review | project ID, evidence ID array, facets (required type facet → evidence ID array), conclusion, questions array, next_action |
| finding | project ID, stable key, kind (`observed`, `inferred`, `speculative`), confidence (`low`, `medium`, `high`), evidence IDs, problem, improvement, benefit, effort, tradeoffs, dependencies, questions, ranking_reason, scores, prompt |
| usage | counts object containing nonnegative integer calls and/or bytes |

Finding text fields must be nonempty; use an explicit “none known” rather than omit dependencies/questions. Scores contain benefit, relevance, evidence, urgency, effort, risk, each an estimated integer 0–3. Prompt is an object with nonempty context, targets, outcome, scope, constraints, preserve and verification. Include actual project identity and source locators in context/targets. Structure cannot establish whether prose is useful; the runner must check it.

Evidence means material actually examined, not a title/summary listing. Use a SHA256 of the exact examined bytes for local versions; metadata revisions are conditional on the provider's guarantees. Never turn a timestamp into a content hash. Null versions require reinspection on later sessions. Charge calls and bytes **before** reads; helper cannot observe external tool use. Materials counted by helper are unique per run, but rereads still consume bytes/calls. Never launch the next read if remaining allowance is insufficient.

Finish with JSON `{next_action, verification, reason, results}`, where results maps every frozen check ID to `{status, evidence: [...], observed}`. Allowed statuses: passed, failed, partial, blocked, not_run. Passing needs evidence. Then:

```sh
python3 "$HELPER" --state "$STATE" finish --token EXACT-TOKEN --json /absolute/private/finish.json
python3 "$HELPER" --state "$STATE" report
python3 "$HELPER" --state "$STATE" status
```

Save the report output and a run/review record in the same private task storage and index their path, purpose, version, checks and validation. State includes the immutable finished run criteria/results. Inspect `state.json` to retrieve IDs, evidence history, run records, prior mode and token. Atomic writes use a checksummed envelope, restrictive permissions and a verified `previous.json`. On corruption, stop; inspect both copies and actual outcomes before any manual recovery. Never blindly restore an old state over newer decisions or active work. Schema migration is explicit; unsupported versions fail closed. The helper opens only designated state paths and private event/check files; locators are inert references.
