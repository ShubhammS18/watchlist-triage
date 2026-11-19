# W2-10 release-runs review: round 2

Reviewed the revised design and `tests/w2_10_release_runs/` against the W2-10 outcome, the six named decisions, W2-08 protocol, wrapper, and round-1 report. This was a read-only review of tracked repository files. No real model or external network call was made.

## Round-1 findings

| # | Status | Evidence and remaining fix |
|---|---|---|
| 1 | **RESOLVED** | `docs/w2-10-release-runs.md:299-321` checks in a clean worktree, writes both outputs outside it, compares them, then copies them in. The base dry run checks byte equality. |
| 2 | **RESOLVED** | `docs/w2-10-release-runs.md:328-345` reserves Results, total, and any sign-off for the publish commit, and stages the log. The made-up FAIL and NO FRESH WORLD paths publish. |
| 3 | **RESOLVED for well-formed run files** | G12 at `tests/w2_10_release_runs/release_gate.py:341-359` enforces the three thresholds; `test_dry_run.py:99-101,185-186` breaks each one. The partial-file failure is new finding N2 below. |
| 4 | **NOT RESOLVED** | G8 requires a completed practice-world rehearsal, but it trusts the rehearsal manifest for world, state, cleanliness, and agent inputs, and does not require or compare the scored items or report (`release_gate.py:275-337`). An amended manifest and SHA list can make the wrong or incomplete rehearsal appear right. With no release-run manifest, `all(... for one in release_inputs)` is vacuously true (`release_gate.py:292-297,328-332`), so candidate identity is unbound. Fix in N1. |
| 5 | **RESOLVED** | `docs/w2-10-release-runs.md:193-201` captures the peeled annotated-tag line; G11 checks the line and tag target (`release_gate.py:259-269`); the tag-object mutation fails. |
| 6 | **RESOLVED** | `docs/w2-10-release-runs.md:348-359` gives the zero run-set and no-fresh steps. G6 accepts an empty fresh run set (`release_gate.py:198-199`), and the dry run publishes NO FRESH WORLD. Its reproduction coverage is weaker than the base path (N4). |
| 7 | **NOT RESOLVED** | `docs/w2-10-release-runs.md:123-126,264-288` adds snapshots and safe branches, but a crash before the manually timed snapshot can leave a nonempty run folder and lost index with no snapshot covering it. The only instruction is to stop; no path can publish the required result. Fix: make an index snapshot reliably at each run start before calls, or define a verifiable NOT ELIGIBLE publication path that preserves the unrecoverable attempt and its spend. |
| 8 | **NOT RESOLVED** | `docs/w2-10-release-runs.md:242-247` still runs `last_run` and the commit commands after the wrapper returns a refusal without starting a run. With an older index, `last_run` names the old run; with no index, it errors. Fresh and rerun invocations are still substitutions described in prose (`:242-254`), rather than separate executable commands. Fix: branch on the wrapper's exit and a new index entry; give explicit first, fresh, and `--rerun-cause` commands, and do not copy or commit a checkpoint after a refusal. |
| 9 | **RESOLVED** | `docs/w2-10-release-runs.md:175-195` shows the freeze commit, hash, tag, and push. |

## Gate and dry-run assessment

| Rule | What the dry run establishes | Remaining limit |
|---|---|---|
| G1 | Base release exercises a real freeze commit and matching outputs/log. | No direct wrong-freeze mutation in W2-10. |
| G2 | Post-freeze code change is caught; a consistently published broken freeze passes. | Correctly checks consistency, not PASS. |
| G3 | A wrong seed fails G3. | The accepted-record replay is separately checked by G4. |
| G4 | Base and NO FRESH WORLD paths pass; W2-08 tests exercise replay mismatches. | No direct W2-10 mutation of `recorded_matches`. |
| G5 | Base output and an edited output are checked byte for byte. | Alternate-result dry runs call `problems` without reproduced bytes (N4). |
| G6 | Missing/extra rows, wrong replacement, cost, spend arithmetic, and a sixth run fail. | A valid row's nonempty Reason is ignored at `release_gate.py:204-206`; minor log-consistency gap. |
| G7 | A fresh checkpoint committed before the generation record fails. | Actual run times remain a stated human limit. |
| G8 | Wrong world, aborted-only rehearsal, changed code/settings, and late evidence fail. | Missing rehearsal files and falsified manifest fields can pass (N1); links can be followed (N3). |
| G9 | Wrong total/result and tag at a different commit fail. | Extra Results rows for an unknown world are not rejected (`release_gate.py:242-249`). |
| G10 | Real gate invokes W2-08 `signoff_problem`; W2-08's own suite covers sign-off rows. | No separate W2-10 sign-off mutation. |
| G11 | An annotated tag-object line in place of the peeled line fails. | Remote push order is explicitly human evidence. |
| G12 | All three stop-rule breakages fail their named check. | A truncated items line can crash the gate (N2); Console truth and unrecorded runs remain stated limits. |

The dry-run breakages prove the named cases fail their checks; they do not establish that every malformed release produces a gate finding. The published-release test calls the same `problems` function with reproduced bytes for both worlds (`test_published.py:21-31`). It is marked `xfail(..., strict=True)` while `release-1` is absent (`test_published.py:16-22`), and all three runs observed one xfail. The dry run uses W2-08's test-only candidate registered as model-free (`conftest.py:20-39`, `made_up.py:44-51`); the real-release test did not execute because the tag is absent. No W2-10 test calls a real model.

`git diff --name-only 16d1ec5..HEAD` lists only `.genesis/KICKOFF.md`, `.genesis/project.json`, `docs/README.md`, `docs/w2-10-release-runs.md`, and the five new W2-10 test files. Run, scoring, audit, release-check, world-generation, model-interface, agent, config, target, and wrapper files are unchanged. The tracked working tree was clean after the tests.

## New findings

1. **N1 — BLOCKER — `tests/w2_10_release_runs/release_gate.py:275-337`: G8 does not prove the committed rehearsal it claims to prove.** A rehearsal folder can omit `items.jsonl`, `report.json`, or the set file and still satisfy its own SHA list, row/index match, manifest checks, and audit-chain verification. The gate never compares the manifest's world, agent, state, and inputs with the audit start record or scored run files. If there are no release-run manifests, the candidate comparison is vacuous. The dry-run wrong-world case uses a genuinely wrong world and therefore does not exercise this bypass. **Fix:** validate required rehearsal files and their bindings as a unit, compare the completed run's scored output and audit log to its manifest and index, and anchor the candidate to the freeze's configured agent even when release runs are absent. Add mutations deleting a required file and falsifying a manifest field, plus a no-release-run case.

2. **N2 — BLOCKER — `tests/w2_10_release_runs/release_gate.py:104-110,221-224`: G12 can raise on a killed run's partial items file.** `_refusals` parses every JSONL line without handling a cut-off line, missing `result`, or invalid JSON. A WSL crash can leave such an items file. The task must still publish a consistent NOT ELIGIBLE result, but the gate errors before returning findings, so the release can become unpublishable for an infrastructure reason. The dry run's killed run has well-formed items. **Fix:** handle partial/malformed items as a named gate problem, count only complete records according to a stated rule, and test a crash-truncated items file on a published NOT ELIGIBLE release.

3. **N3 — SHOULD — `tests/w2_10_release_runs/release_gate.py:278-283,299-314`: G8 may read rehearsal files through symlinks.** `Path.is_file()` and `read_bytes()` follow links, and the W2-08 `unsafe_paths` guard covers `release/` and `audit/checkpoints/`, not `rehearsal/`. A link committed before the freeze is not caught by the post-freeze history check. This breaks the gate's committed-files-only claim and can make evidence depend on a file outside git. **Fix:** reject non-regular git modes and on-disk links under `rehearsal/` before reading or hashing them; add a linked rehearsal-file dry run.

4. **N4 — SHOULD — `tests/w2_10_release_runs/test_dry_run.py:140-163`: alternate-result cases skip G5.** FAIL, NO FRESH WORLD, and broken-freeze tests call `gate.problems(made.clone)` with no reproduced outputs, which disables G5 (`release_gate.py:177-181`). They prove result acceptance, but not that the committed output equals the documented command in those branches. **Fix:** reproduce both worlds in each alternate-result case and pass the bytes to `problems`, then add an edited-output break on at least one non-PASS branch.

5. **N5 — NIT — `tests/w2_10_release_runs/release_gate.py:204-206,242-249`: some log cells are not constrained.** G6 ignores a nonempty Reason on a valid row, and G9 permits extra Results rows whose World is neither `frozen` nor `fresh`. Both can mislead a reader while the gate passes. **Fix:** require an empty valid-run Reason and exactly one Results row for each of the two worlds.

## Gate runs

Commands used `.venv/bin/python -m pytest tests/<suite> -q -p no:cacheprovider`, one suite at a time. Wall times are `/usr/bin/time` elapsed seconds; pytest times are in parentheses. No Genesis command or paid call was run.

| Suite | Run | Result | Wall time |
|---|---:|---|---:|
| `w2_10_release_runs` | 1 | 28 passed, 1 xfailed | 82.36 s (pytest 79.95 s) |
| `w2_10_release_runs` | 2 | 28 passed, 1 xfailed | 83.13 s (pytest 79.71 s) |
| `w2_10_release_runs` | 3 | 28 passed, 1 xfailed | 83.08 s (pytest 80.70 s) |
| `w2_08_release_protocol` | 1 | 129 passed, 1 skipped, 1 xfailed | 80.56 s (pytest 77.05 s) |
| `w2_01_acceptance` | 1 | 68 passed | 72.94 s (pytest 70.57 s) |
| `t06_harness` | 1 | 340 passed, 6 skipped | 71.14 s (pytest 68.50 s) |
| `t02_world` | 1 | 699 passed | 28.25 s (pytest 26.86 s) |
| `w2_02_agent` | 1 | 68 passed | 6.27 s (pytest 6.05 s) |
