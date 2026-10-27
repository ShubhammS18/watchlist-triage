# W2-01-harness-acceptance — independent review, round 3 (final)

Range: `HEAD~1..HEAD` (`4a268fe`). Read-only review under the same folder, hidden-world, network, and paid-call limits.

## Round 2 blocker

**NOT RESOLVED** — [`harness/release_check.py:143`](/home/shubham/projects/watchlist-triage/harness/release_check.py:143), [`harness/release_check.py:156`](/home/shubham/projects/watchlist-triage/harness/release_check.py:156). The new `check_world(world, listed)` correctly rejects a stable, changed public file, and the two new tests prove that case. It reads and hashes the public files, however, then `expected_items(world)` opens `alerts.jsonl`, `twin_alerts.jsonl`, and `evidence.jsonl` again. The bytes used to build the expected item set are not the bytes that were verified. A public list changed between those reads can again omit an alert while a self-consistent incomplete run is judged PASS. The later `check_world(..., hidden=True)` does not recheck public files. **BLOCKER fix:** build the expected set from the same public-file bytes whose hashes were checked, or hash the exact bytes read for that set before accepting it. Add a test that changes the public list between verification and loading.

## Fixed-hash read chain

- [`harness/release_check.py:135`](/home/shubham/projects/watchlist-triage/harness/release_check.py:135): targets bytes are compared with the fixed target hash, but mismatched bytes are still parsed for mechanism-only results. They cannot lead to PASS.
- [`harness/release_check.py:139`](/home/shubham/projects/watchlist-triage/harness/release_check.py:139), [`harness/run.py:158`](/home/shubham/projects/watchlist-triage/harness/run.py:158): the manifest's `world_hash` is compared with the fixed frozen hash; `check_world` checks that its file list hashes to that value, then checks listed public-file bytes. The loader re-reads some public files afterward, as above. Hidden-file bytes are checked at [`harness/release_check.py:187`](/home/shubham/projects/watchlist-triage/harness/release_check.py:187) before truth loading, but truth loading also re-reads them.
- [`harness/release_check.py:159`](/home/shubham/projects/watchlist-triage/harness/release_check.py:159), [`harness/score.py:396`](/home/shubham/projects/watchlist-triage/harness/score.py:396): run items are checked against their own manifest hashes; `index.json` and run manifests have schema and internal-consistency checks, not fixed hashes. These are dynamic run outputs, so the literal claim that *every file read* has a fixed hash is false.
- [`harness/release_check.py:182`](/home/shubham/projects/watchlist-triage/harness/release_check.py:182): the price table embedded in each run is compared with `config/prices.json` at that run's git commit; the embedded time parameters are compared with the fixed `TIME_SHA256` at line 184. Mismatches make PASS impossible.

## New changed-line issue

**SHOULD — A non-frozen manifest is used to choose files to read.** [`harness/release_check.py:140`](/home/shubham/projects/watchlist-triage/harness/release_check.py:140), [`harness/release_check.py:143`](/home/shubham/projects/watchlist-triage/harness/release_check.py:143). When `listed["world_hash"]` differs from the fixed frozen hash, the code only appends an ineligibility reason and still passes that untrusted manifest to `check_world`. If its file list is internally consistent with the altered hash, `check_world` follows its arbitrary public paths; it can read outside the chosen world directory before reporting NOT ELIGIBLE. **Fix:** stop processing the world before `check_world` when its hash is not the fixed one. Do not use an unverified file list to select read paths.

No other changed-line error found.

## Gates

- `.venv/bin/python -m pytest tests/w2_01_acceptance`: **51 passed** in 55.42 s.
- `.venv/bin/python -m pytest tests/t06_harness`: **340 passed, 6 skipped** in 59.96 s.

The repository remained clean.
