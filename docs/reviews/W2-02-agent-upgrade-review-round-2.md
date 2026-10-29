# W2-02 agent upgrade — independent review, round 2

Scope: `HEAD~1..HEAD` (`9cf5968`). Repository kept read-only; no network or paid calls; I did not open `data/world/hidden/`.

## Round 1 findings

1. **RESOLVED by accepted-risk disclosure, not by removing the false-close path.** `.genesis/project.json:1925-1929` records DEC-W2-02-MODEL-READING-RISK. `tests/w2_02_agent/test_model_reading_risk.py:22-28` sends a wrong but valid `NO_LINK` through the real child on three public bundles and confirms the code still recommends `CLOSE` without a failure flag, matching `triage_agent/recommend.py:60-63`. `docs/w2-02-report.md:114-117` and `README.md:55-56` state the limit and the attempt 1/2 observations. The underlying risk remains as the accepted decision says.

2. **NOT RESOLVED — the release check can still PASS on a cost it cannot prove.** `harness/release_check.py:117-130` removed the unsafe prompt-byte path and requires a successful retry, but still substitutes the retry's usage and the requested model's price for a failed call with unknown usage and model. `.genesis/project.json:1935-1939` and `docs/acceptance-design.md:34-57` now label this an assumption rather than proof. That corrects the claim, but the check still returns PASS under the assumption, as it does on the committed set with two failed calls. **Fix:** if PASS must mean verified cost, mark runs with unreported failed-call usage NOT ELIGIBLE until a provider-backed billing bound or independently checked bill is available. Otherwise give the result an explicit assumption-qualified status, separate from verified PASS.

3. **RESOLVED by narrowing the digest's stated scope.** `triage_agent/record.py:1-6` and `docs/w2-02-report.md:46-49` say the rule-code hash covers the four local triage decision files, and that shared dependencies are pinned by the clean git commit in the run-set inputs. It still does not hash all decision code on its own, but the recorded identity no longer claims that it does.

4. **RESOLVED.** `harness/release_check.py:141-153,259` binds prompt text to both prompt hashes and binds the manifest rule-code hash to the run-set input, making disagreement NOT ELIGIBLE. `tests/w2_01_acceptance/test_eligibility.py:132-160` exercises mismatches and matching controls. The committed run set still passes.

5. **NOT RESOLVED — the stronger import guard remains bypassable, and its new claim is too broad.** `tests/w2_02_agent/test_agent_static.py:25,43-55` rejects named `importlib`, `__import__`, `exec` and `eval`, but an agent module can still call `getattr(__builtins__, "__im" + "port__")("worldgen")` (or the dict form of `__builtins__`) without any forbidden AST name or declared import. Lines 1-5 say this proves no runtime import. The text guard at lines 80-89 remains a full-literal check and expressly omits short fragments and new-seed rendered text. Current agent code has no generator import or copied note text; the issue is the claimed guard. **Fix:** remove the absolute runtime-import claim and state the exact static cases checked, or add a mechanism that enforces the import boundary at runtime. Add a mutation case for indirect builtins access.

6. **RESOLVED.** `README.md:86-88` now covers upgraded model reasons, self-asserted reviewer identities and the narrow citation check; `docs/w2-02-report.md:118` states that citation accuracy does not validate the written reason.

## New issue in this commit

- **SHOULD — The new human-review wording describes a planned control as if it protected these runs.** `README.md:55-56` and `docs/w2-02-report.md:114-117` say human review of every close “is the control.” These W2-02 runs are evaluation runs with no human review or final dispositions (`SPEC.md:26`), and no operational review implementation is in this commit. The decision record at `.genesis/project.json:1927` correctly qualifies human approval as *in operational mode*. **Fix:** say human review is the planned operational control and was not exercised in the reported evaluation; retain the accepted model-reading risk disclosure.

## Verification

- `.venv/bin/python -m harness acceptance w2-02-runs 8f4050be0f28031f8ec64da2d193ecf12d9c5cb7aee868b4adda84e22c76f33e`: **PASS**, three valid runs.
- W2-02 suite: **57 passed**. T06 suite: **340 passed, 6 skipped**. W2-01 suite: **66 passed**. Suites were run separately because their local `conftest.py` modules collide when collected together.
- The changed lines add no agent decision or child-guard regression. The new issue above concerns the release-facing description of a control not yet exercised.
