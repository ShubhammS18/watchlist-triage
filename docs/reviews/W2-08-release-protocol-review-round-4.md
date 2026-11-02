# W2-08 release protocol — round 4 review

Scope: only `HEAD~1..HEAD` (`6e1c6e4..369aee3`), focusing on R3-1 and regressions in changed lines. The repository was clean before and after this read-only review. No network or paid model call was made.

## R3-1

**RESOLVED** — `harness/release_check.py:211-218` makes `OUT` absolute and lexically normal before `prepare` or `_check` reads release inputs. It does not follow symlinks. This makes the paths passed to `readable` comparable with the absolute paths collected by `unsafe_paths` (`harness/release.py:237-274`). The non-release branch still returns before this new normalization.

The new test runs the acceptance entry point from a throwaway repository with the documented relative argument `release/frozen` (`tests/w2_08_release_protocol/test_logs.py:295-319`; `docs/w2-08-release-protocol.md:128-129`). It commits a linked `index.json`, watches file opens, makes the link target unreadable, and confirms the target is never opened. The result is NOT ELIGIBLE while the unsafe answer is still counted from the logs. The mutation proof replaces the normalization with the former relative path and confirms this test fails (`tests/w2_08_release_protocol/test_mutation.py:77-80`).

**New findings:** None in `HEAD~1..HEAD`.

## Verification

| Suite | Result | Pytest time | Wall time |
|---|---:|---:|---:|
| `tests/w2_08_release_protocol` | 129 passed, 1 skipped, 1 xfailed | 82.26 s | 82.52 s |
| `tests/w2_01_acceptance` | 68 passed | 71.65 s | 71.95 s |
| `tests/t06_harness` | 340 passed, 6 skipped | 71.58 s | 71.91 s |
| `tests/t02_world` | 699 passed | 27.49 s | 27.75 s |
| `tests/w2_02_agent` | 68 passed | 6.11 s | 6.34 s |
| `W2_08_MUTATION=1` on `test_mutation.py` | 2 passed; all 14 breakages caught | 40.42 s | 40.68 s |

All runs used `PYTHONDONTWRITEBYTECODE=1`, `-q` and `-p no:cacheprovider`. The W2-08 suite remained under 120 s. Its golden test passed (`tests/w2_08_release_protocol/test_frozen_unchanged.py:10-24`): the non-release stdout remains byte-identical to the saved hashes for 8f4050be (`c839620e06603dec04f549e5e1aed7ba1277b87f7c0b89066bd22b50f067ccbe`, exit 3) and f2e614d2 (`b4c3d94e66f47b68faf184d6f443ff317bf78892f4528d7757b4f4eef274fb5b`, exit 1). The golden test and non-release behavior were not changed in this commit.
