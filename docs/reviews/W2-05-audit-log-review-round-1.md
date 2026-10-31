# W2-05 audit log — Codex review, round 1

Range: `3788714..HEAD` (`11ed28c`). Read-only review; no network or model calls. I did not open `data/world/hidden/`.

## Findings

1. **BLOCKER — `harness/audit.py:105`: an edited record can make verify crash instead of naming it.** `problem()` does `event not in FIELDS` before checking that `event` is a string. A canonical JSON record with `"event":[]` raises `TypeError: unhashable type: 'list'`; `verify-log` does not print `FAILED: record k`. This is an edited-record AC-9 case, even though the four tested mutations pass. **Fix:** reject a non-string event in `problem()` before dictionary membership, and add a CLI test that edits a record's event to a list and expects its index.

2. **BLOCKER — `harness/audit.py:71` (used at `:86` and `:93`): model-ID fields can contain customer values.** The `MODEL` pattern is a character allowlist, not a customer-value boundary. It accepts date-of-birth and ID-number formats and many nationalities from the public agent-side customer file (616, 622, and 597 values respectively match the pattern). `requested_model` comes from configuration; `model_ids` comes from provider reports. The current fake-model scan at `tests/w2_05_audit/test_fields.py:22` does not exercise those values, so it cannot establish AC-22 for arbitrary model IDs. **Fix:** put a digest of each raw model identifier in structured audit fields, with a count or stable label as needed; bind the raw value through the existing items hash or a separate digest, and add an adversarial model-ID test against customer values.

3. **SHOULD — `harness/audit.py:71`, `harness/run.py:236`: a provider-reported model ID containing a space aborts an otherwise usable run.** `_Logged.append()` sends the raw ID to `Log.write()`, whose type check rejects it as `AuditWriteError`; the run stops after that item. The same restriction applies to a requested model with a space at `harness/run.py:429`. I would record such IDs safely rather than abort the run. **Fix:** use the digest representation above for arbitrary nonempty IDs, preserving their identity without placing their raw text in the structured log; test both requested and reported IDs containing spaces.

4. **SHOULD — `harness/audit.py:154` and `:126`: serialization can fail outside the `AuditWriteError` handler.** `Log.write()` hashes before its `try`, and `recommendation()` hashes out-of-bundle citations before `Log.write()`. An unpaired surrogate in a model-supplied string raises `UnicodeEncodeError` there (reproduced in `Log.write()`), so the run may be aborted under that error type instead of the promised `AuditWriteError`. **Fix:** make record construction, validation, hashing, and encoding one guarded audit operation; wrap serialization errors as `AuditWriteError` and test a non-UTF-8-encodable model string.

5. **NIT — `harness/audit.py:188`: checkpoint `v: true` passes as version 1.** Python treats `True == 1`; record version validation at `:82` correctly checks the type, but checkpoint validation does not. **Fix:** use the same type-strict version predicate for checkpoints and add a malformed-checkpoint case.

## Confirmed behavior and limits

- The writer uses sorted-key compact UTF-8 JSON with LF and each record links to the preceding record hash. The end record hashes the exact `items.jsonl` bytes that are then written. Against the original checkpoint, the four tested AC-9 mutations name the first bad record: edited content, deleted middle, swapped pair, and deleted last. Rehashing the changed record and every successor restores the internal chain, so verify names the last record when its head differs from the checkpoint. The anchor still depends on the owner committing and publishing that checkpoint.
- On a simulated audit-write failure, the parallel hand-off waits for calls in flight, includes their attempts in cost, stops new hand-offs, returns an aborted run, and keeps its log. The aborted run is excluded from valid-run counts. A failed final sync leaves a completed end record in an aborted run's log with no checkpoint; this is disclosed in the design.
- The four t06 edits only expand expected output-file lists. Their checks for environment leakage, score/hidden-file ordering, aborted state/cost, and absence of `items.jsonl` retain their original meaning.
- `harness/score.py`, `harness/schema.py`, and `harness/release_check.py` have no diff in the requested range.
- `git log --all --name-only -- '*.txt'` shows only the intentional evidence files, `requirements-dev.txt`, and `worldgen/names/*.txt` in reachable history. I found no stray build text file committed.

## Suites run at HEAD

| Suite | Result | pytest time |
|---|---:|---:|
| `tests/w2_05_audit` | 38 passed | 7.53 s |
| `tests/t06_harness` | 340 passed, 6 skipped | 69.96 s |
| `tests/w2_01_acceptance` | 68 passed | 73.59 s |
| `tests/w2_02_agent` | 68 passed | 6.52 s |
| `tests/w2_03_harness_fixes` | 38 passed | 6.06 s |

Commands used `.venv/bin/python -m pytest tests/<suite> -q -p no:cacheprovider` with `PYTHONDONTWRITEBYTECODE=1`. The W2-03 suite includes re-scoring the committed baseline and upgrade outputs against their committed figures. Working tree remained clean.
