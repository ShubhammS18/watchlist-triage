# W2-05 audit log — Codex review, round 2

Range: `HEAD~1..HEAD` (`11ed28c..ad871a2`). Read-only review; no network, paid, or real-model calls. I did not open `data/world/hidden/`.

## Round 1 findings

| Finding | Status | Evidence |
|---|---|---|
| 1. Non-string `event` crashes verify | **RESOLVED** | `harness/audit.py:107` checks for a string before membership; `tests/w2_05_audit/test_verify.py:154` exercises the CLI and names the edited record. |
| 2. Model names may equal customer values | **RESOLVED to the accepted decision, with residual risk deferred** | `DEC-W2-05-MODEL-ID` at `.genesis/project.json:2094` says readable names matching the pattern remain raw, odd names are hashed, and the full customer-value check belongs to W2-06. `harness/audit.py:117-122`, `:136`, and `harness/run.py:431-432` implement that policy. The pattern still admits some customer values; the original technical concern remains for W2-06, as the record and `docs/w2-05-audit-log.md:46` disclose. |
| 3. Space in a model name aborts the run | **RESOLVED** | `harness/audit.py:122` hashes names outside the pattern; `harness/run.py:431-432` applies it to requested names, and `harness/audit.py:136` applies it to reported names. Whole-run tests are at `tests/w2_05_audit/test_model_names.py:50` and `:56`. |
| 4. Record construction errors escape `AuditWriteError` | **RESOLVED** | `harness/run.py:237` builds the recommendation body inside `Log.write`; `harness/audit.py:162-173` guards building, hashing, encoding, and writing. `tests/w2_05_audit/test_fault.py:155` covers both a bad field and a bad cited ID. |
| 5. Checkpoint `v: true` passes as version 1 | **RESOLVED** | `harness/audit.py:199` uses the type-strict version predicate; `tests/w2_05_audit/test_verify.py:168` covers boolean, float, text, and wrong integer versions. |

## New issues in changed lines

1. **SHOULD — `harness/audit.py:122`, `harness/run.py:453`: a lone-surrogate reported model name is hashed in the audit but crashes run finalization.** The new `model_name()` explicitly accepts and hashes this case (`tests/w2_05_audit/test_model_names.py:23`). The raw ID still remains in each attempt; building the completed `items.jsonl` with `ensure_ascii=False` then raises `UnicodeEncodeError` outside the run's fault handling. I reproduced a fake-provider run that raises this exception and leaves its index entry at `started`, with no completed or aborted manifest. **Fix:** handle invalid Unicode consistently across the audit, items, and manifest paths, or reject it as a controlled provider fault before logging and narrow the claim that every odd name can complete. Add a whole-run regression test for this case.

2. **NIT — `harness/audit.py:122`: a literal model name can collide with the hash representation.** For any odd name `x`, the literal provider name `sha256:<SHA-256(x)>` matches `MODEL` and produces the same logged string as `x`. The log cannot tell which name was reported, and the set at `harness/audit.py:136` can collapse both into one entry. This conflicts with the decision's reason for keeping names readable: identifying which model ran from the log. **Fix:** reserve the `sha256:` prefix for digests and escape or tag a literal model name using that prefix; test the two names together.

No other changed line raised a review finding. `harness/score.py`, `harness/schema.py`, and `harness/release_check.py` remain unchanged in this range.

## Suites at `ad871a2`

| Suite | Result | pytest time |
|---|---:|---:|
| `tests/w2_05_audit` | 45 passed | 9.16 s |
| `tests/t06_harness` | 340 passed, 6 skipped | 70.03 s |
| `tests/w2_01_acceptance` | 68 passed | 72.84 s |
| `tests/w2_02_agent` | 68 passed | 6.44 s |
| `tests/w2_03_harness_fixes` | 38 passed | 5.94 s |

Each ran with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/<suite> -q -p no:cacheprovider`. The W2-03 suite re-scored the committed baseline and upgrade outputs. The repository working tree remained clean.
