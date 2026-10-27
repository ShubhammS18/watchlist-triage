# W2-01-harness-acceptance — independent review, round 4 (final)

Range: `HEAD~2..HEAD` (`cbf24ea`, `2fda89b`). Read-only, scoped to the four requested checks.

| Check | Status | Evidence |
|---|---|---|
| 1. Each world file read once; expected items and truth use verified bytes | **RESOLVED** | [`harness/run.py:163`](/home/shubham/projects/watchlist-triage/harness/run.py:163) reads each selected file into `checked` once and hashes those bytes. [`harness/release_check.py:152`](/home/shubham/projects/watchlist-triage/harness/release_check.py:152) retains the checked public bytes; [`harness/release_check.py:166`](/home/shubham/projects/watchlist-triage/harness/release_check.py:166) builds expected IDs from them. [`harness/release_check.py:197`](/home/shubham/projects/watchlist-triage/harness/release_check.py:197) retains checked hidden bytes; [`harness/release_check.py:199`](/home/shubham/projects/watchlist-triage/harness/release_check.py:199) passes them to `load_truth(texts=...)`. The manifest is read once at line 142. No world file is reopened on this path. The test at [`tests/w2_01_acceptance/test_eligibility.py:127`](/home/shubham/projects/watchlist-triage/tests/w2_01_acceptance/test_eligibility.py:127) overwrites files after verification and still scores the checked bytes. |
| 2. Wrong world hash stops before following its file list | **RESOLVED** | [`harness/release_check.py:143`](/home/shubham/projects/watchlist-triage/harness/release_check.py:143) compares with the fixed frozen hash and returns NOT ELIGIBLE at lines 147–153, before `check_world`, index loading, or expected-item construction. [`tests/w2_01_acceptance/test_eligibility.py:115`](/home/shubham/projects/watchlist-triage/tests/w2_01_acceptance/test_eligibility.py:115) supplies an outside-path list and proves neither `check_world` nor `expected_items` is called. |
| 3. `load_truth` without `texts=` behaves as before | **RESOLVED** | [`worldgen/truth.py:14`](/home/shubham/projects/watchlist-triage/worldgen/truth.py:14) retains the original `Path(folder).joinpath(name).read_text(encoding="utf-8")` path when `texts is None`; [`worldgen/truth.py:23`](/home/shubham/projects/watchlist-triage/worldgen/truth.py:23) defaults `texts` to `None`. The three original reads, keying, and twin construction retain their order and operations at lines 30–40. Existing no-`texts` callers, including `load_snippet_tags`, keep that branch. |
| 4. New record matches code | **RESOLVED** | [`DEC-W2-01-ELIGIBILITY-WORLD` in `.genesis/project.json:1821`](/home/shubham/projects/watchlist-triage/.genesis/project.json:1821) says a wrong world hash stops processing and each target is `not worked out`, mechanism only, with the reason. [`harness/release_check.py:145`](/home/shubham/projects/watchlist-triage/harness/release_check.py:145)–153 returns that shape and reason. Other ineligibility paths still calculate target results. The added review-budget record at line 1811 accurately records this fourth, limited round. |

**New changed-line errors:** none found.

## Gates

- `.venv/bin/python -m pytest tests/w2_01_acceptance`: **53 passed** in 53.57 s.
- `.venv/bin/python -m pytest tests/t06_harness`: **340 passed, 6 skipped** in 59.52 s.

The repository remained clean.
