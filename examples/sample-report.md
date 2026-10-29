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
