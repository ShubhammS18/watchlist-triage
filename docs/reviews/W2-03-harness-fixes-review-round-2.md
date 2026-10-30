# W2-03 harness fixes — Codex review, round 2

Range: `HEAD~1..HEAD` (`67b2f93..758961f`). Repository kept read-only; no direct access to `data/world/hidden/`, network, or paid calls.

## Round-1 findings

1. **RESOLVED — `harness/run.py:376-382`, `harness/run.py:423`.** The preflight now checks `infra_invalid.threshold` against the shared completed-manifest schema before creating the run directory, and the final manifest reuses the checked `threshold`. The run-set input and infra-invalid marking also use that same value (`harness/run.py:343`, `harness/run.py:407`). The new tests exercise refusal with malformed thresholds and equality of the two recorded locations (`tests/w2_03_harness_fixes/test_start_checks.py:75-88`). Caveat: malformed thresholds are also rejected by the already existing `run_set_inputs` check, so the refusal test alone does not isolate the new leaf check; the code inspection establishes that it is present.

2. **RESOLVED — `tests/w2_03_harness_fixes/test_rescore.py:61-79`, used at line 119.** The W2-02 comparison now requires exact `per_run` values and compares full spread rate objects. A different min/max object is accepted only if both exact objects occur among the runs' values and have the same rational value. This closes the round-1 gap where changes to `decimal`, `rounded`, or an invented fraction could be discarded. Run-order normalization remains limited to the runs list (`tests/w2_03_harness_fixes/test_rescore.py:51-54`). The baseline's separate exact figure gate still passes.

## New issues

None found in the changed lines. The documentation and refreshed before/after evidence counts agree with the seven added tests (38 after; 15 failed, 4 errors, 19 passed before). `git diff --check HEAD~1..HEAD` passed. Historical manual evidence retains the provenance limit noted in round 1.

## Gates run in this review

`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest <suite> -q -p no:cacheprovider --tb=short`

| Suite | Result |
| --- | --- |
| `tests/w2_03_harness_fixes` | 38 passed |
| `tests/t06_harness` | 340 passed, 6 skipped |
| `tests/w2_01_acceptance` | 68 passed |
| `tests/w2_02_agent` | 68 passed |

`git status --short` was empty after the gates.
