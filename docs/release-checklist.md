# Release checklist (W2-09)

Every public-facing claim in `README.md` for release 1, with the committed evidence it rests on (NFR-8). Decision
records such as `DEC-W2-SCOPE` are in `.genesis/project.json`. The gate test `tests/w2_09_readme` checks that every
evidence path below exists, that the README's gap list equals `DEC-W2-SCOPE`'s, that every release figure the README
gives equals the committed check output, and that the cited statistic carries its DOI. It does not check that a claim
says what its evidence says: that is the review's job.

"Owner" in the Evidence column means the claim rests partly on my word, not only on a committed file.

## Industry statistics

Every industry statistic in public text, with its citation.

| # | Statistic | Where | Citation | Evidence |
|---|---|---|---|---|
| S1 | False positives make up over 90% of sanctions screening alerts | `README.md` (opening), `SPEC.md` (Problem) | Kim and Yang (2024), Frontiers in Artificial Intelligence, doi 10.3389/frai.2024.1374323. They report it citing earlier industry sources (owner, 19 Nov 2026). `SPEC.md` (Problem) says only that "published research reports" it; the specification is approved and left unchanged, and the README carries the narrower wording. | `SPEC.md`, `docs/reviews/spec-review-round-3.md` |
| S2 | Vendor claims of review times, used as modelled-time assumptions | `README.md` (What the evidence does not show) | Each vendor source with its URL and read date, beside the figure | `config/modelled_time.json` |

## Claims

| # | Claim | Where in README | Evidence |
|---|---|---|---|
| C1 | All data is synthetic; TRUE_MATCH is a benchmark label, not a legal determination; no claim of compliance, sufficiency or production fitness | opening | `SPEC.md`, `LICENSE` |
| C2 | Nothing asks a human yet; the output is a recommendation nobody approves | opening, What was not built | `.genesis/project.json` (`DEC-W2-SCOPE`), `docs/w2-05-audit-log.md` |
| C3 | The world's 90% clear false positives were set for testing, not measured | opening | `SPEC.md`, `docs/world-design.md` |
| C4 | Frozen in commit `fb4ab457ae95`, tag `release-1-freeze`; published at the tag `release-1`, 18 Nov 2026 | Release 1 | `docs/release-log.md` |
| C5 | Fresh seed from the freeze commit's hash; counter 0 accepted, no rejected try | Release 1 | `release/generation.json`, `release/check-fresh.json`, `docs/w2-08-release-protocol.md` |
| C6 | All six runs valid, none replaced | Release 1 | `release/check-frozen.json`, `release/check-fresh.json`, `docs/release-log.md` |
| C7 | Frozen world PASS on every release target | Release 1 | `release/check-frozen.json`, `targets/release-targets.json` |
| C8 | Fresh world PASS (safety counts only); its other rates information only, not a pass on every target | Release 1 | `release/check-fresh.json`, `.genesis/project.json` (`DEC-W2-RELEASE-RULES`) |
| C9 | Every figure in the release table | Release 1 | `release/check-frozen.json`, `release/check-fresh.json` |
| C10 | Frozen cost needed no assumption; fresh world had 2 failed calls bounded under the stated assumption, each retried successfully | Release 1 | `release/check-frozen.json`, `release/check-fresh.json`, `docs/release-log.md`; the two items: `release/fresh/20261118T080337937147Z-ea98bd39/items.jsonl` line 778 (item ALT-0260/1) and `release/fresh/20261118T085818577239Z-ea98bd39/items.jsonl` line 1559 (item ALT-0520/2), each with a ProviderError attempt and no token counts, then a successful attempt with token counts and a non-failure result; no other release item has a failed attempt; both files are in `release/fresh/SHA256SUMS` |
| C11 | Release 1 cost USD 0.70 and wave 2 USD 1.65; Console balances are my readings | Release 1 | `docs/release-log.md`, `.genesis/project.json` (`DEC-W2-10-REVIEW`); owner |
| C12 | The thirteen gaps, each with its requirement ID; the specification is unchanged | What was not built | `.genesis/project.json` (`DEC-W2-SCOPE`), `SPEC.md` |
| C13 | No reviewer identities yet; when built they are self-asserted, with no authentication | What was not built | `SPEC.md` (FR-13, Non-goals), `.genesis/project.json` (`DEC-W2-SCOPE`) |
| C14 | The audit log records recommendations, not human decisions, and what it can and cannot show | What was not built | `docs/w2-05-audit-log.md`, `.genesis/project.json` (`DEC-W2-05-CHOICES`) |
| C15 | No human spot-check of the reasons was done | What was not built | `SPEC.md` (Risks names the mitigation); owner, 19 Nov 2026 |
| C16 | Two synthetic worlds from my generator; neither may represent real alerts | What the evidence does not show | `docs/world-design.md`, `release/generation.json` |
| C17 | 6 true matches per primary family in each world | What the evidence does not show | `SPEC.md` (FR-2), `docs/world-design.md` |
| C18 | I can see the labels; the agent's loader does not read the hidden files | What the evidence does not show, How it is evaluated | `docs/world-design.md`, `tests/t05_agent/test_payload_prompt.py` |
| C19 | The rules come from the generator's rubric | What the evidence does not show, History | `docs/w2-02-report.md` |
| C20 | The frozen world is not unseen by the design | What the evidence does not show | `docs/w2-02-report.md`, `docs/w2-02-attempts.md` |
| C21 | The fresh world tests overfitting to cases, not planting assumptions | What the evidence does not show | `SPEC.md` (Risks) |
| C22 | The seed could have been chosen through the freeze commit; the order of push and generation rests on the log and my statement | What the evidence does not show | `docs/w2-08-release-protocol.md`, `docs/release-log.md`; owner |
| C23 | Modelled times are assumptions, mostly vendor claims, not measurements | What the evidence does not show | `config/modelled_time.json` |
| C24 | Three runs at temperature 1 show the spread, not a bound | What the evidence does not show | `config/model.json`, `docs/w2-02-report.md` |
| C25 | Reasons may contain synthetic customer values, in the run output and the audit log's one free-text field | What the evidence does not show | `SPEC.md` (FR-15), `docs/w2-05-audit-log.md`, `docs/w2-06-boundary-checks.md` |
| C26 | Closes that rest on reading a note rest on the model's answer, with no automatic double-check | What the evidence does not show | `docs/w2-02-report.md` |
| C27 | The citation checks test which evidence is cited, not whether the reason is right | What the evidence does not show | `SPEC.md` (Metrics), `docs/acceptance-design.md` |
| C28 | The injection check is decided by verdicts only; citation differences are information | What the evidence does not show | `SPEC.md` (AC-12), `docs/acceptance-design.md` |
| C29 | Network isolation covers ordinary, accidental and injected routes on Python 3.12.3 on Linux; hostile code is out of scope | What the evidence does not show | `docs/isolation-design.md`, `SPEC.md` (FR-9) |
| C30 | The capability allowlist equals a reviewed list; its purpose rests on reading it | What the evidence does not show | `docs/w2-06-boundary-checks.md` |
| C31 | The drift check covers Python 3.12 only, on runs GitHub makes, and does not block a merge | What the evidence does not show | `docs/w2-04-ci-drift.md`, `.github/workflows/` |
| C32 | The release check cannot tell an infrastructure failure from a stop on purpose | What the evidence does not show | `docs/w2-08-release-protocol.md`, `docs/release-log.md` |
| C33 | 600 alerts: 30 true matches, 30 ambiguous, 540 clear false positives; three framings; three runs | How it is evaluated | `docs/world-design.md`, `docs/framings-design.md` |
| C34 | Modelled-time assumptions committed before the baseline's first run; targets set after the baseline and committed before the upgrade and release results; release rules fixed before the freeze | How it is evaluated | `config/modelled_time.json`, `docs/baseline-report.md`, `targets/release-targets.json`, `.genesis/project.json` (`DEC-W2-RELEASE-RULES`), `docs/release-log.md` |
| C35 | Each task with a review gate reviewed by a fresh session from another provider; some later fixes checked only by me. T01-rubric, a low-risk task, had no review gate. Round 4 of W2-10 was saved by the owner on 19 Nov 2026 straight from the Codex session, unedited, which is why it has no title | How it is evaluated | `docs/reviews/`, `docs/reviews/W2-10-release-runs-review-round-1.md`, `docs/reviews/W2-10-release-runs-review-round-2.md`, `docs/reviews/W2-10-release-runs-review-round-3.md`, `docs/reviews/W2-10-release-runs-review-round-4.md`, `.genesis/project.json` (`DEC-W2-10-TEST-CLONES`) |
| C36 | Over-escalation, framing-agreement and citation-accuracy targets no looser than the baseline | How it is evaluated | `targets/release-targets.json`, `docs/baseline-report.md` |
| C37 | Baseline figures | History | `docs/baseline-report.md`, `baseline/` |
| C38 | Upgrade figures, and its pass resting on a cost assumption | History | `docs/w2-02-report.md`, `w2-02-runs/` |
| C39 | Run the tests at `main`, not at `release-1`, and why | Running the tests | `.genesis/project.json` (`DEC-W2-10-TEST-CLONES`), `tests/w2_08_release_protocol/release_common.py`, `tests/w2_10_release_runs/made_up.py` |
| C40 | No test needs an API key; `tests/w2_07_isolation/` needs user namespaces | Running the tests | `tests/t07_baseline/fake_api.py`, `tests/t07_baseline/test_adapter.py`, `tests/w2_07_isolation/` |
| C41 | Apache-2.0 | Licence | `LICENSE` |
