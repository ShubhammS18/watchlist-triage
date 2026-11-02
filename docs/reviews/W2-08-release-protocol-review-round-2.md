# W2-08 release protocol — round 2 code review

Reviewed `docs/w2-08-release-protocol.md`, the four named decisions and W2-08 outcome in `.genesis/project.json`, `harness/release.py`, the release changes in `harness/release_check.py` and `harness/__main__.py`, and the W2-08 tests. The repository was clean before and after the runs. No files in the repository were edited, and no network or paid model was used.

## Round 1 findings

| # | Status | Evidence and remaining issue |
|---|---|---|
| 1. Early refusal hides safety counts | **RESOLVED** | The design separates eligibility from safety (`docs/w2-08-release-protocol.md:118-121`). `_check` collects run problems, reads logs before hidden truth, and counts logged answers even with an ineligible run set (`harness/release_check.py:252-320`). The cap and missing-checkpoint tests include unsafe answers. |
| 2. Unfinished log integrity and identity | **NOT RESOLVED** | Chain, schema, run ID, freeze commit and world checks are present (`harness/release.py:334-385`). The log's *full* `run_set` is not compared with the index: line 373 checks only the run ID's eight-character suffix. Two different 64-character set IDs with the same first eight characters pass this binding. See finding N2. |
| 3. Generation record fully checked | **NOT RESOLVED** | `generation_problems` compares the record with replay, including rejected error hashes and the ten-try shape (`harness/release.py:186-203`). But when all ten are rejected, `_check` returns `NO FRESH WORLD` even if the record is missing or differs. See finding N1. |
| 4. Unlisted run folder | **RESOLVED** | Inventory compares run folders with index entries, checks `SHA256SUMS`, counts the union against the cap, and reads unlisted logs (`harness/release.py:267-319, 452-465`). |
| 5. End-point-only freeze diff | **RESOLVED** | `freeze_problems` examines each commit from freeze through HEAD and rejects merges (`harness/release.py:97-129`). The change-and-revert test exercises it. |
| 6. Qualified pass sign-off | **RESOLVED for the pre-release design** | The gate has a test of the real committed output and `release.signoff_problem` checks the matching run set, cost and sign-off row (`tests/w2_08_release_protocol/test_signoff.py:21-24`; `harness/release.py:546-571`). The test is strictly xfailed until W2-10 commits `release/check-frozen.json`; it cannot yet prove a real sign-off. |
| 7. Finished log/items mismatch | **RESOLVED** | Completed logs are checked for ending hash and count, exact item coverage, and answer fields made by `audit.recommendation` (`harness/release.py:388-409`). Tests change an answer, outside citation and item coverage. See N4 for a separate unchecked input hash. |
| 8. Push-before-generation evidence | **RESOLVED as a documented human check** | Steps require the remote tag observation and owner statement in the release log (`docs/w2-08-release-protocol.md:278-287, 312-333`). Limits explicitly say the local check cannot prove the order (`:456-465`). |

## New findings

### N1 — BLOCKER — All-rejected replay masks an invalid generation record

`harness/release_check.py:223-228`; `harness/release.py:240-260`. `prepare` records a missing or mismatched `release/generation.json` as an eligibility problem. If replay rejects all ten seeds, `_check` immediately calls `no_fresh_world`, which unconditionally labels the result `NO FRESH WORLD`; `finish` preserves that label. The design says a differing record is NOT ELIGIBLE (`docs/w2-08-release-protocol.md:92-102`), and the W2-08 outcome requires every rejection to be recorded. A missing or shortened record can therefore be published under the same headline as a verified all-rejected generation. The returned object also lacks the promised `release` block. **Fix:** Return `NOT ELIGIBLE` when any freeze or record problem exists, retaining the replayed ten-rejection result in `release.generation`; reserve `NO FRESH WORLD` for a matching committed record and otherwise eligible freeze. Test the check, not only `generation_problems`, with a missing and shortened all-rejected record.

### N2 — SHOULD — A killed run's log is bound only to an eight-character run-set prefix

`harness/release.py:368-379`. `read_log` accepts `run_started.run_set` when its first eight hex digits match the run ID suffix. It never compares all 64 digits with the indexed entry's `run_set` or the requested set. A log from another set sharing that prefix can be labeled as belonging to the indexed run, contrary to the design's claim that it names the run's own set (`docs/w2-08-release-protocol.md:202-209`). **Fix:** Pass the full indexed run-set ID into `read_log`, require exact equality, and test a different ID with the same eight-character prefix. For an unlisted folder, report that no indexed set identity can be verified.

### N3 — BLOCKER — Allowed post-freeze paths can be committed as symlinks

`harness/release.py:88-94, 114-121, 267-285, 330-351`. The freeze rule checks change status and path, but never Git file mode. An added `release/frozen/index.json`, `release/generation.json`, or checkpoint can be a tracked symlink to a mutable file outside Git. `git status` stays clean because Git tracks the link text, while the release check follows the link and trusts its target. The committed check output can then change without any post-freeze commit, defeating the allowed-files rule and reproducibility. **Fix:** Reject symlinks and non-regular Git modes for every allowed file in each commit, and use `lstat` or equivalent before reading release inputs. Test a committed symlink at an allowed path, including an index and a checkpoint.

### N4 — SHOULD — The completed log's input hash comparison is self-supplied

`harness/release.py:404-408`. `items_problem` calls `audit.recommendation(line, record["input_sha256"])`. It supplies the log's own input hash to the function used as the expected record, so changing that hash in the log and rechaining it with a matching checkpoint cannot fail the field-by-field comparison. The log can claim a different framed input than the run actually used while still passing the stated equality rule. **Fix:** Recompute the input hash from the checked world bundle and framing (or bind it to a separately checked run input hash) before comparing the logged record. Test a changed input hash with valid log chain and checkpoint.

## Verification

| Suite | Result | Pytest time |
|---|---:|---:|
| `tests/w2_08_release_protocol` | 117 passed, 1 skipped, 1 xfailed | 68.52 s |
| `tests/w2_01_acceptance` | 68 passed | 77.63 s |
| `tests/t06_harness` | 340 passed, 6 skipped | 74.36 s |
| `tests/t02_world` | 699 passed | 29.44 s |
| `tests/w2_02_agent` | 68 passed | 6.60 s |
| `W2_08_MUTATION=1` on `test_mutation.py` | 2 passed; all eight breaks caught | 27.27 s |

The W2-08 suite's separate wall timer read 63.92 s, also below 120 s. The other wall timers read 74.62, 71.41, 28.11, 6.84 and 25.89 s respectively. All commands used `-p no:cacheprovider` and `PYTHONDONTWRITEBYTECODE=1`.

The golden test passed: non-release command stdout matched the saved SHA-256 digests `c839620e06603dec04f549e5e1aed7ba1277b87f7c0b89066bd22b50f067ccbe` (8f4050be, exit 3) and `b4c3d94e66f47b68faf184d6f443ff317bf78892f4528d7757b4f4eef274fb5b` (f2e614d2, exit 1). The no-release branch calls `_check` with `state=None`; its original flow remains guarded, apart from the manifest block that is always entered on the legacy path (`harness/release_check.py:198-349`). `git diff 8f87432..HEAD` is empty for `harness/run.py`, `harness/score.py`, `harness/audit.py`, `harness/manifest.py`, `worldgen/` and `model_interface/`. The W2-08 candidate answers from test truth and calls only the local stub once for the failed-call case (`tests/w2_08_release_protocol/release_common.py:29-67`); no real model was called.
