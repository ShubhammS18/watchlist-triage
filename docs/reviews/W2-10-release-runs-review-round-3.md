# W2-10 release-runs review: round 3

Read the round-1 and round-2 reports, the current W2-10 design, the W2-10 decisions including `DEC-W2-10-LOST-INDEX`, and the changes from round-2 commit `31315e1` to `e85a72f`. This review made no tracked repository change, model call, or network call.

## Earlier findings

| Earlier finding | Status | Evidence |
|---|---|---|
| Round 1 #1: check dirties its checkout | **RESOLVED** | Checks still write outside a clean worktree, then compare and copy (`docs/w2-10-release-runs.md:370-392`); G5 reproduces the committed bytes. |
| Round 1 #2: empty publish commit | **RESOLVED** | Results and total remain for the publish log commit (`docs/w2-10-release-runs.md:399-415`). |
| Round 1 #3: stop rules absent | **RESOLVED** | G12 still checks all three thresholds; the dry run breaks each. A new edge case in the changed refusal parser is finding R3-1. |
| Round 1 #4: unproved rehearsal | **RESOLVED within the stated practice-world limit** | G8 now requires completed-run files, links manifest, report, items, set report, index and verified log, and derives the candidate inputs from the freeze's own configuration even with no release run (`release_gate.py:172-210,376-507`). Deleted-file, falsified-manifest, wrong-settings and link mutations fail. The practice world's bytes are not committed, so its input hashes cannot be independently remade, as the design states. |
| Round 1 #5: annotated tag evidence | **RESOLVED** | Peeled tag line and target remain checked by G11. |
| Round 1 #6: ten rejected seeds | **RESOLVED** | The NO FRESH WORLD steps and zero run set remain, and that case now also reproduces both check outputs. |
| Round 1 #7: lost index after a crash | **RESOLVED by the accepted exception** | `DEC-W2-10-LOST-INDEX` allows publishing that world's untouched attempt as NOT ELIGIBLE. The steps provide `copy_as_is`, a log row and check path (`docs/w2-10-release-runs.md:320-368`), and a dry run publishes it. The omitted-index evidence gap is R3-2. A lost rehearsal index still requires stopping, as explicitly stated. |
| Round 1 #8: refused run and missing commands | **RESOLVED** | `after_run` branches on wrapper exit 2 before reading a new entry or copying a checkpoint; separate rehearsal, frozen, fresh and rerun commands are shown (`docs/w2-10-release-runs.md:123-136,194-204,290-302`). |
| Round 1 #9: freeze commit absent | **RESOLVED** | The freeze commit, hash, tag and push remain explicit. |
| Round 2 N1: rehearsal files and candidate binding | **RESOLVED within the stated practice-world limit** | G8's `_unit` and `_anchor` check the required file relationships and frozen candidate; the new dry-run mutations cover deleted and altered evidence, including with no release run (`release_gate.py:172-188,376-507`; `test_dry_run.py:223-281`). |
| Round 2 N2: partial items file crashes G12 | **RESOLVED for the reported crash** | `_share` returns a named problem for malformed complete lines and ignores an unfinished final fragment; the lost-index/cut-file release publishes NOT ELIGIBLE and passes (`release_gate.py:128-157`; `test_dry_run.py:173-217`). R3-1 is a separate undercount introduced by this fix. |
| Round 2 N3: rehearsal symlink read | **RESOLVED** | `_unsafe` checks on-disk and committed modes before reading rehearsal files; the linked-file mutation fails (`release_gate.py:191-210,422-427`). |
| Round 2 N4: alternate results skip G5 | **RESOLVED** | FAIL, NO FRESH WORLD and broken-freeze tests now pass reproduced outputs; an edited FAIL output fails G5 (`test_dry_run.py:158-217`). |
| Round 2 N5: loose log cells | **RESOLVED** | G6 requires an empty Reason on a valid row, and G9 rejects extra Results worlds or rows; three dry-run changes fail (`release_gate.py:301-303,340-350`). |

The changed files are the design, README, Genesis records and W2-10 gate/dry-run code. `git diff --name-only 31315e1..HEAD -- harness baseline_run worldgen model_interface triage_agent config data/world` is empty. The published-release test remains strict xfail while `release-1` is absent; each of the three W2-10 runs reported one xfail. The W2-10 dry run uses the model-free test candidate. No real model was called.

## New findings

1. **R3-1 — BLOCKER — `tests/w2_10_release_runs/release_gate.py:147-157`: a complete final refusal without a newline is discarded.** `_share` drops every nonempty tail when the manifest is unfinished. A WSL kill can cut `items.jsonl` immediately after a complete JSON item, before its newline. The wrapper counts that line with `splitlines()` (`baseline_run/wrapper.py:219-225`), but G12 does not. Direct read-only reproduction: `_share(b'{"result":{"failure_kind":"model_refusal"}}', False)` returns a refusal share of zero. A later run could therefore pass G12 despite the greater-than-2% stop rule. **Fix:** parse a nonempty tail; count it if it is a complete valid item record, and discard it only when it is genuinely cut off in an unfinished run. Add a dry-run mutation with a complete no-newline refusal followed by another run.

2. **R3-2 — SHOULD — `docs/w2-10-release-runs.md:343-355`, `tests/w2_10_release_runs/release_gate.py:281-290`, `tests/w2_10_release_runs/made_up.py:240-244`: lost-index evidence is optional in a release the gate accepts.** The steps require pasting the SHA-256 of an omitted invalid index or `.tmp` file into the log. The lost-index dry run passes without doing so, and G6 only requires NOT ELIGIBLE plus rows for the visible folders. A reader cannot even tell from committed files whether omitted bytes existed. **Fix:** require a structured log entry for every omitted file, with path and SHA-256, and test its absence. To make those bytes independently verifiable under the committed-files-only claim, preserve them in an allowed committed evidence form rather than only outside git; record any necessary exception before the freeze.

3. **R3-3 — SHOULD — `tests/w2_10_release_runs/release_gate.py:441-476`: G8 does not check the rehearsal log's State or Run set cells.** It matches run IDs, cost, spend and agent commit, then reads the manifest and index, but never compares those two displayed cells with the index. A log can call an aborted try completed or name another run set while G8 passes, if another valid rehearsal exists. **Fix:** compare both cells with the index and manifest for every rehearsal row; add one altered-row dry-run case for each.

4. **R3-4 — SHOULD — `docs/w2-10-release-runs.md:611-630`: the gate-time conclusion is stale at the pre-freeze review.** The document's slowest W2-10 time is 85.10 seconds and projects about 91 seconds after publication. This review measured 93.22 seconds wall time; adding its own measured 5.76-second published-test work gives about 98.98 seconds, already near the document's 100-second trigger for moving the dry run behind a by-hand switch. The design also records a prior 105.3-second wall run, which would project to about 111 seconds. **Fix:** update the timing table and decide the documented switch before freezing, with a direct post-publication measurement still required. The current projection is under 120 seconds; it is not a guarantee for slower machine conditions.

## Gate runs and 120-second limit

Completed runs used the local Python with bytecode writes disabled and pytest's cache provider disabled. Wall times include process startup. The first W2-08 invocation was interrupted by the session restart and has no result; it was run again and passed. The secrets gate ran with HTTPS git transport disabled, so it could use the installed local hook without network access.

| Gate | Run | Result | Wall time |
|---|---:|---|---:|
| W2-10 `tests` | 1 | 36 passed, 1 xfailed | 83.79 s |
| W2-10 `tests` | 2 | 36 passed, 1 xfailed | 85.99 s |
| W2-10 `tests` | 3 | 36 passed, 1 xfailed | 93.22 s |
| W2-08 | 1 completed | 129 passed, 1 skipped, 1 xfailed | 84.84 s |
| W2-01 | 1 | 68 passed | 77.04 s |
| W2-02 | 1 | 68 passed | 6.65 s |
| Secrets (`pre-commit run gitleaks --all-files`) | 1 | passed | 0.36 s |
| T06 supporting suite | 1 | 340 passed, 6 skipped | 70.29 s |
| T02 supporting suite | 1 | 699 passed | 27.73 s |

Every completed gate measured here is below 120 seconds. The real-release test cannot run before the publish tag; the design's two largest-made-up-release probes measured 5.73 and 5.76 seconds for its work. Adding 5.76 seconds to this review's slowest W2-10 wall time projects 98.98 seconds, 21.02 seconds under the limit. This is a projection, not a post-publication measurement. The design records a 119.61-second W2-08 run on a slower day, so a safe margin for that gate is not established across known machine conditions.

The tracked working tree was clean after all runs.
