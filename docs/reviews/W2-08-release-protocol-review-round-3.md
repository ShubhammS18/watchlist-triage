# W2-08 release protocol — round 3 review

Scope: only `HEAD~1..HEAD` (`c4c971b..6e1c6e4`), against round 2 findings N1–N4 and round 1 findings 2 and 3. The repository was clean before and after this read-only review. No network or paid model call was made.

## Finding status

| Finding | Status | Evidence |
|---|---|---|
| N1 — all-rejected replay masks an invalid record | **RESOLVED** | `harness/release.py:309-316` now returns NOT ELIGIBLE if any freeze, record or targets problem exists, preserves the replay in `release`, and gives NO FRESH WORLD only when there is no such problem. `_check` passes its collected problems at `harness/release_check.py:227-230`. The new check-level cases cover a missing record, nine recorded rejections and a freeze change (`tests/w2_08_release_protocol/test_generation.py:145-170`). |
| N2 — killed log bound only by the run-set prefix | **RESOLVED** | The full indexed run-set ID is saved and compared with `run_started.run_set` (`harness/release.py:392-393, 445-455`). The new test changes only the suffix beyond the first eight characters (`tests/w2_08_release_protocol/test_logs.py:247-257`). |
| N3 — allowed files can be symlinks | **NOT RESOLVED** | Per-commit Git modes are checked (`harness/release.py:117-128`), and an `lstat` walk records unsafe paths (`:237-262`). But the disk read guard compares absolute unsafe paths with potentially relative input paths (`:270-274`). The documented `OUT` argument is relative (`docs/w2-08-release-protocol.md:119-120`), so release input reads can still follow a link. See R3-1 below. |
| N4 — completed log input hash is self-supplied | **RESOLVED** | The expected hash is recomputed from checked public bytes with the run step's `bundles` and `content_hash` (`harness/release.py:319-327`), then compared with completed and unfinished log records (`:466-472, 475-497`). Changed-hash tests cover both forms (`tests/w2_08_release_protocol/test_logs.py:260-277`). |
| Round 1 #2 — unfinished log integrity and identity | **RESOLVED** | The remaining full run-set identity gap is closed by the N2 change (`harness/release.py:445-455`); the existing chain, schema, run ID, freeze and world checks remain. |
| Round 1 #3 — generation record fully checked | **RESOLVED** | The existing field-by-field replay comparison now reaches the final result for an all-rejected record through the N1 change (`harness/release.py:293-316`; `harness/release_check.py:227-230`). |

## New issue in the changed lines

### R3-1 — BLOCKER — Relative `OUT` bypasses the symlink read guard

`harness/release.py:270-274`; `harness/release_check.py:254-255, 268-272`; `docs/w2-08-release-protocol.md:119-120`. `unsafe_paths` stores absolute paths built from `records.REPO`, but `readable` compares them directly with its `path` argument. The documented command passes `release/frozen` or `release/fresh` as a relative `OUT`, and `_check` keeps it relative. Consequently `readable(state, Path("release/frozen/index.json"))` returns `True` even when the absolute index path is in `state["bad"]`; `_check` then calls `records.read_index(out)` through the symlink. The same mismatch affects run files, logs and `SHA256SUMS`. A direct read-only call confirmed `readable` returned `True` for the relative path and `False` for the same absolute path. The Git-mode and `lstat` checks make the result NOT ELIGIBLE, but the check still reads mutable external content and its output can vary without a commit. The new tests use absolute clone paths and miss the documented CLI form.

**Fix:** Normalize `OUT` to an absolute path once before every release-mode read, or normalize both arguments inside `readable` without following symlinks. Keep the path comparison against the expected repository output. Add an end-to-end test that invokes `acceptance release/frozen ...` from the repository with a linked index and proves the link target is never read.

No other changed-line problem was found in this review.

## Verification

| Command/suite | Result | Pytest time | Wall time |
|---|---:|---:|---:|
| `tests/w2_08_release_protocol` | 128 passed, 1 skipped, 1 xfailed | 76.53 s | 76.81 s |
| `tests/w2_01_acceptance` | 68 passed | 71.86 s | 72.10 s |
| `tests/t06_harness` | 340 passed, 6 skipped | 70.33 s | 70.62 s |
| `tests/t02_world` | 699 passed | 27.49 s | 27.75 s |
| `tests/w2_02_agent` | 68 passed | 6.14 s | 6.36 s |
| `W2_08_MUTATION=1` on `test_mutation.py` | 2 passed; all 13 breakages caught | 40.39 s | 40.64 s |

All suites used `PYTHONDONTWRITEBYTECODE=1`, `-q` and `-p no:cacheprovider`. The W2-08 suite stayed under 120 s. Its golden test passed (`tests/w2_08_release_protocol/test_frozen_unchanged.py:10-24`): non-release stdout remains byte-identical to the saved hashes for 8f4050be (`c839620e06603dec04f549e5e1aed7ba1277b87f7c0b89066bd22b50f067ccbe`, exit 3) and f2e614d2 (`b4c3d94e66f47b68faf184d6f443ff317bf78892f4528d7757b4f4eef274fb5b`, exit 1). Neither the golden test nor the non-release entry path changed in `HEAD~1..HEAD`.
