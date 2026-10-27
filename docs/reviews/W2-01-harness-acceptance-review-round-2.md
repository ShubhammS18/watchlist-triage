# W2-01-harness-acceptance — independent review, round 2

Range: `HEAD~1..HEAD` (`c6d4c14`). Read-only; no repository edits, Genesis writes, network, paid calls, or direct opening of `data/world/hidden/`.

## Round 1 findings

| # | Status | Evidence |
|---|---|---|
| 1. Incomplete run can PASS | **NOT RESOLVED** | [`harness/release_check.py:150`](/home/shubham/projects/watchlist-triage/harness/release_check.py:150), [`harness/release_check.py:159`](/home/shubham/projects/watchlist-triage/harness/release_check.py:159): the new item-set comparison rejects missing items when the public world files are intact, but the expected set is read from public files that this command never verifies. See blocker below. |
| 2. Superseded set can PASS | **RESOLVED** | [`harness/release_check.py:145`](/home/shubham/projects/watchlist-triage/harness/release_check.py:145): a superseded selected set is NOT ELIGIBLE; [`tests/w2_01_acceptance/test_eligibility.py:116`](/home/shubham/projects/watchlist-triage/tests/w2_01_acceptance/test_eligibility.py:116) covers a passing oracle set marked superseded. |
| 3. Per-target mechanism-only marker missing | **RESOLVED** | [`harness/release_check.py:193`](/home/shubham/projects/watchlist-triage/harness/release_check.py:193): every target entry receives the marker; eligibility and oracle tests check both values. |
| 4. Alternative time settings show only booleans | **RESOLVED** | [`harness/release_check.py:120`](/home/shubham/projects/watchlist-triage/harness/release_check.py:120): all five alternatives now include assisted and manual time per alert and the comparison boolean; [`tests/w2_01_acceptance/test_oracle.py:94`](/home/shubham/projects/watchlist-triage/tests/w2_01_acceptance/test_oracle.py:94) checks their shape. |

## Changed-line issue

- **BLOCKER — The new coverage check trusts an unauthenticated public alert list.** [`harness/release_check.py:75`](/home/shubham/projects/watchlist-triage/harness/release_check.py:75), [`harness/release_check.py:150`](/home/shubham/projects/watchlist-triage/harness/release_check.py:150), [`harness/release_check.py:181`](/home/shubham/projects/watchlist-triage/harness/release_check.py:181). `expected_items` reads `agent/alerts.jsonl` and `agent/twin_alerts.jsonl` before validation. The only later `check_world(..., hidden=True)` checks hidden files and skips all public files ([`harness/run.py:163`](/home/shubham/projects/watchlist-triage/harness/run.py:163)). Removing an alert from the public list and its rows from a passing run, then keeping the run's manifest counts and item hash internally consistent, makes the reduced set appear complete. The manifest can still carry the fixed frozen-world hash, so the check can return PASS without covering that alert. The new tests alter run rows but keep the world files intact; they do not catch this path. **Fix:** verify the public world files against the fixed world manifest with `check_world(world, listed, hidden=False)` before calling `expected_items`, and test a changed public alert list against a consistent incomplete run. Keep the hidden-file check as well.

No other changed-line error found.

## Gates

- `.venv/bin/python -m pytest tests/w2_01_acceptance`: **49 passed** in 53.67 s.
- `.venv/bin/python -m pytest tests/t06_harness`: **340 passed, 6 skipped** in 60.94 s.

The repository remained clean after both gates.
