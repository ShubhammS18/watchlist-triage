# W2-06 boundary checks — independent review, round 2

Scope: `HEAD~1..HEAD` only. Read-only repository review, with no Genesis writes, external network or paid calls, and no direct inspection of `data/world/hidden/`.

## Round 1 findings

1. **RESOLVED — deliberate legacy-abort break.** `.genesis/project.json:2139-2143`, `docs/w2-06-boundary-checks.md:27-32`, `harness/schema.py:139-143`, `harness/score.py:374-394,709-712`. The accepted `DEC-W2-06-LEGACY-ABORT` states that old aborted manifests with raw exception text are refused and can make every set in the same output folder ineligible. The doc now states the same consequence and says the release runs use new folders. The code still requires the new hash field and applies the global fail-closed rule. All six committed baseline and upgrade manifests are completed with `aborted: null`; their figures are unaffected. This resolves the review concern as an explicit owner decision, not as backward compatibility.

2. **RESOLVED — mutation 36 now reaches its guard assertion.** `tests/t06_harness/mutations.py:166-171`, `docs/w2-06-boundary-checks.md:37-40`. The mutation now inserts the environment in the final manifest assembly, after the W2-03 preflight. An isolated proof returned `passed, failed`; its broken-copy result was `FAILED ...test_no_environment_variable_reaches_any_output - assert ...sentinel-value... not in ...`. The full `T06_MUTATION=1` suite passed, including the exact-reason and untouched-copy checks. The proof now fails for the intended assertion, not a fixture `KeyError`.

## New issues

None found in the changed lines. `git diff --check HEAD~1..HEAD` passed. Nothing under `model_interface/` changed. The W2-03 re-score suite passed its comparisons with the committed baseline and upgrade reports.

## Test runs

Wall times are `/usr/bin/time -p` `real`; pytest durations are shown separately. Each command used `PYTHONDONTWRITEBYTECODE=1`, `-q`, `-p no:cacheprovider`, and `--tb=no` to limit repeated sandbox tracebacks.

| Suite | Result | Real | Pytest |
|---|---:|---:|---:|
| `tests/w2_06_boundary` | 127 passed | 8.86 s | 10.07 s |
| `tests/t04_model_interface` | 89 passed, 48 errors | 10.65 s | 10.43 s |
| `tests/t05_agent` | 291 passed | 64.86 s | 67.68 s |
| `tests/t06_harness` | 340 passed, 6 skipped | 70.07 s | 72.82 s |
| `tests/w2_03_harness_fixes` | 38 passed | 4.92 s | 6.19 s |
| `tests/t06_harness`, `T06_MUTATION=1` | 346 passed | 107.74 s | 112.14 s |

T04 has the same environment limit as round 1: this sandbox denies the localhost server fixture's `socket.socket()` at `tests/t04_model_interface/test_isolation.py:88` with `PermissionError: [Errno 1] Operation not permitted`. The nested T04 mutation cases depend on that fixture too. This is not evidence of a changed model interface. No external network was used. The repository's `git status --short` remained empty.
