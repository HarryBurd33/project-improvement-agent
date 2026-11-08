# Fictional sample — not a live portfolio audit

Mode: broad. Observation: illustrative. Sources: one selected local fixture directory. Two projects inventoried, one assessed and reviewed in depth, one inventoried only. Discovery is partial; global total/completion percentage unknown. Next manual action: inspect the essay assignment and draft before assessment.

## 1. Make empty chart data understandable

Project: Reading Dashboard, `/example/reading-dashboard`. Purpose: show reading progress. Evidence: fixture `renderer.py`, lines12–18, version `fixture-v1`, assumes a row exists; a fixture issue describes a first-use crash. Confidence: medium; fixture behavior, not a live product failure.

Improve empty-state handling so a new user can begin. Effort: small estimate. Preserve populated charts. Dependency: check the loader's empty-data contract. Question: prompt or blank chart?

Provisional ranking: benefit3, relevance3, evidence2, urgency1, effort1, risk1 → score18. First-use reliability outranks decorative upgrades. These are judgment estimates.

```text
Context: Reading Dashboard shows reading progress. Fixture renderer.py lines12–18 versionfixture-v1 assumes a nonempty row list; the fixture first-use report records an empty-data crash. Confirm current source and project instructions before editing.
Targets: /example/reading-dashboard/renderer.py, its loader and relevant tests.
Outcome: Empty input produces a useful declared state without crashing.
Scope: Input-to-render behavior and the smallest warranted tests.
Constraints: Check the loader contract first; avoid unnecessary dependencies. Choose wording from current product context.
Preserve: Existing populated charts, keyboard access and saved progress.
Verification: Exercise empty and populated inputs. Empty input does not throw and communicates the declared state; populated output and saved progress remain correct. Report actual checks and unresolved gaps.
```

No change is proposed for the inventoried essay because its content was not examined. New: one fixture finding. Changed/resolved/unchanged: no prior baseline. Rejected findings stay suppressed unless new evidence or an explicit user decision reopens them.


# Focused audit sample — synthetic fixture output, condensed

Request: “Use improvement agent to identify limitations or capabilities I have requested but still don't exist.” Scope: the current synthetic app/chat only. All listed synthetic source files and original fixture turns inspected; no account-wide discovery. Installation and release remain unknown unless explicitly checked.

| Stable request key | Original evidence | Status | Current evidence / next check |
| --- | --- | --- | --- |
| chat-a/u1 | “Add CSV export”; later assistant says done | Not started | Complete exporter fixture exposes JSON only; verify CSV with quotes, commas and Unicode and preserve JSON |
| chat-a/u2 | “Support offline notes” | Implemented but unverified | Offline code exists; disconnect, save a note, restart and compare contents |
| chat-a/u3 | “Handle empty input” | Verified complete | Current empty/populated acceptance passes; old TODO does not reopen it |
| chat-a/u4 | “Export PDF”, then user replaces it with CSV | Superseded | Keep only the later CSV request active |
| chat-a/a2 | Assistant proposes Slack; user rejects it | Rejected | Preserve rejection, no action |
| chat-a/u7 | Mobile sync deferred until desktop is complete | Deferred | Desktop milestone remains incomplete |

## First unfinished action: CSV export

Original basis: fixture chat-a/u1. Current evidence: complete fixture `export.py` exports JSON only; fixture acceptance reports unsupported CSV. Impact: export existing data in the requested format. Dependencies: confirm current exporter revision. Smallest action: add CSV serialization to the existing exporter. Acceptance: header and rows round-trip quoted, comma-containing and Unicode fields; JSON acceptance still passes. Destination: synthetic app / synthetic chat. Starting model/effort: GPT-6.1 Sol / Medium, subject to actual host availability.

```text
Starting model/effort: GPT-6.1 Sol / Medium
Destination: synthetic app / synthetic chat
Original request: fixture chat-a/u1, “Add CSV export.”
Current evidence: the complete synthetic exporter fixture has JSON only; the assistant's “done” reply is not acceptance evidence.
Implement CSV serialization in the existing exporter after checking current source and authority. Preserve JSON output and saved data. Verify headers and round-trip rows containing quotes, commas and Unicode; rerun existing JSON acceptance. Report source, installation and release outcomes separately. No external actions are authorized by this prompt alone.
```

Optional opportunities: none recommended in this condensed CSV example. An unaccepted dashboard proposal stays separate from user commitments and needs supporting evidence before an implementation recommendation.
