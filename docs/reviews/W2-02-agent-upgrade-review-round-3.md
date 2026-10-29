# W2-02 agent upgrade — independent review, round 3

Scope: `HEAD~1..HEAD` (`e28beec`). Repository kept read-only; no network or paid calls; I did not open `data/world/hidden/`.

## Round 2 findings

1. **RESOLVED — cost result is qualified rather than presented as verified PASS.** `harness/release_check.py:65-67,289-294` returns `PASS (cost bounded under a stated assumption)` whenever a passing set contains a bounded failed call, and gives the count and billing assumption. A plain `PASS` requires zero bounded calls. `harness/__main__.py:76-80` uses exit 3 for the qualified result. DEC-W2-01-PASS-LABEL at `.genesis/project.json:1947-1957` accepts this distinction, and `docs/w2-02-report.md:99-106` names the remaining assumption. The committed set reports two bounded calls; its cost is still not proved from provider usage, but it is no longer labelled as an unqualified pass.

2. **RESOLVED — the static guard now states its actual scope.** `tests/w2_02_agent/test_agent_static.py:1-11,29,47-68` adds the exact `__builtins__` spelling to its AST check and says the check is static, does not prove that no runtime import happens, and cannot catch indirect routes built from other names. `docs/w2-02-report.md:44-49` repeats those limits. The guard does not become a runtime import boundary; its narrower claim now matches what it checks.

3. **RESOLVED — operational review is correctly described as planned.** `README.md:59-63` and `docs/w2-02-report.md:121-126` now distinguish the planned L1, four-eyes/QA-sampling and L2 workflow from these evaluation runs, which had no human review. The model-reading risk remains disclosed.

## New issue in this commit

- **SHOULD — the Console sign-off gate accepts arbitrary text, not the claimed cost reconciliation.** `tests/w2_02_agent/test_attempt_log.py:87-92` returns true for any nonempty sign-off cell whose run-set prefix matches. It never checks the Console and harness amounts in that row, compares the harness amount with the committed run costs, or requires an explicit matching attestation; `test_attempt_log.py:95-102` tests only empty versus nonempty text. Thus a row with contradictory amounts and `not checked` in the sign-off cell would satisfy the gate, despite `docs/w2-02-attempts.md:34-42` saying the owner's sign-off is that the totals match. **Fix:** validate the run-set ID and recorded harness total against the committed run set, require a structured explicit owner attestation that includes the Console amount, and leave the external Console check as a human review step. If the gate is intentionally only a presence check, label it that way.

## Verification

- `.venv/bin/python -m harness acceptance w2-02-runs 8f4050be0f28031f8ec64da2d193ecf12d9c5cb7aee868b4adda84e22c76f33e`: exit **3**, result **PASS (cost bounded under a stated assumption)**, two calls bounded, three valid runs, no failed targets or eligibility reasons. Exit 3 is the documented qualified-pass code.
- W2-02 suite: **60 passed**. T06 suite: **340 passed, 6 skipped**. W2-01 suite: **68 passed**. Suites were run separately because their local `conftest.py` modules collide when collected together.
