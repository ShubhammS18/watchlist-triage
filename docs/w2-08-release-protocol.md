# Release protocol (W2-08)

Status: Built, for review round 2. Round 1 reviewed the design only, before any code (`DEC-W2-08-REVIEW-BUDGET`).
It found two blockers and six SHOULDs, and the owner accepted all eight; the changes are listed under "Review round
1". Requirements: FR-23 and AC-19, and AC-1, AC-2, AC-5 and AC-12 on the fresh-seed world. Rules:
`DEC-W2-RELEASE-RULES`, as built by `DEC-W2-08-CHOICES` and `DEC-W2-08-CHECKPOINTS`, within
`DEC-W2-01-ELIGIBILITY-3`, `DEC-W2-01-PASS-LABEL`, `DEC-W2-01-RUN-RULE` and `DEC-W2-05-CHOICES`.

No model is called. The tests' runs are made by a test-only candidate agent that answers from a world's truth and
calls no model. The T04 stub is called once, in the one test run that needs a failed call. The release itself is
W2-10's task, and the README's account of it is W2-09's.

This task adds four things:
- a documented seed function;
- a `fresh-world` command that writes the fresh world and its generation record;
- a release mode of the release check, for both worlds;
- the release steps below.

Without the release mode, the release check is the one `acceptance-design.md` describes, and its output is
byte-identical to what it was before this task.

The code is `harness/release.py` (new) and three files changed: `harness/release_check.py`, `harness/__main__.py`
and this doc.

## Review round 1

| Finding | What changed |
|---|---|
| 1. BLOCKER: an early refusal hid unsafe answers | Eligibility is kept apart from the safety counts. Only an untrusted world stops the check early: a world hash that is not the anchor, or no fresh world. Otherwise every problem is collected, and unsafe answers are counted and reported from every readable run, even when the result is NOT ELIGIBLE (step 4). |
| 2. BLOCKER: unfinished logs were not checked | Every complete record of a run that never finished is checked as a hash chain: canonical form, record schema, order, links, hashes and run ID. Its first record must bind it to the run, run set, freeze commit and world. A malformed or mismatched record makes the set NOT ELIGIBLE (step 3). |
| 3. Generation record not fully checked | Every field of the record is compared with the replay, including rejected tries' error type and hash, the generator version, the Python version (major and minor), the record version and the exact set of fields. An all-rejected record must show all ten tries (the generation step). |
| 4. An unlisted run folder could escape | The run folders and the index must list exactly the same runs. `SHA256SUMS` must list every file once, with its hash. The `sets/` folder holds only this run set's file (step 3). |
| 5. End points only | Every commit from the freeze to the publish commit is checked, and the history must be linear (step 1). |
| 6. Sign-off not checked on the real release | The release gate's test `test_signoff.py::test_the_published_release_has_the_console_sign_off_it_needs` parses the committed release log for the sign-off a qualified frozen-world pass needs. It is xfail (strict) until `release/check-frozen.json` is committed, then an ordinary test (the release log). |
| 7. Log and items linked only by a file hash | Each logged answer of a completed run must be the record the run step makes from its items row, for exactly the same items (step 3). |
| 8. Push-before-generation is not a checked fact | Stated in Limits; the evidence goes in the release log (release steps 2 and 3). |

## The seed function

```
fresh_seed(commit, counter) = int(first 13 hex digits of SHA-256("<commit>:<counter>"), 16)
```

- **`commit`** is the freeze commit's full 40-character lowercase hash. A short hash or a tag name is refused, so
  one commit always gives one seed.
- **`counter`** is an integer from 0 to 9. Anything else is refused.
- **The text hashed** is UTF-8, with no line feed.
- **The size:** 13 hex digits are 52 bits, so the seed is an exact integer in JSON and in the world's
  `MANIFEST.json`.
- **Where it lives:** `harness/release.py` (`fresh_seed`), standard library only.

Test vectors (the tests check them):

| commit | counter | seed |
|---|---|---|
| `0000000000000000000000000000000000000000` | 0 | 982426940076343 |
| `0000000000000000000000000000000000000000` | 9 | 878779841415296 |
| `4bf3b82f8da96e2f4efbb81c7d65250d96f519b8` | 0 | 754401112843469 |
| `4bf3b82f8da96e2f4efbb81c7d65250d96f519b8` | 1 | 2342836009960206 |

## The generation step and its record

The owner runs `python -m harness fresh-world FREEZE WORLD_OUT RECORD` from a clean checkout of the freeze commit.
`WORLD_OUT` and `RECORD` must both lie outside the repository, so the checkout stays clean for the runs. The command:

1. Resolves `FREEZE` to its full hash and refuses unless it is `HEAD` and the tree is clean. It refuses on any
   Python other than 3.12, as the drift check does (`tools/check_world_drift.py`), so a different runtime cannot
   pass for a different world.
2. Extracts the freeze commit's tree with `git archive` into a temporary folder. It tries counter 0, then 1, and so
   on up to 9, each in its own isolated subprocess (`python -I -B`) that imports that tree's `worldgen` and calls
   `generate(fresh_seed(FREEZE, counter))`. So the generator that runs is the freeze's own, and the working tree's
   is never used.
   - **A rejection** is a `BuildError` and nothing else. It is recorded and the next counter is tried.
   - **Any other failure** is a fault in the code, not the generator's verdict. The command stops, writes no
     record and no world, and uses up no counter.
3. Writes the first accepted world to `WORLD_OUT` and the record to `RECORD`. The owner commits the record as
   `release/generation.json`.

```json
{"v": 1, "freeze_commit": "<40 hex>", "seed_function": "int(sha256(\"<commit>:<counter>\")[:13 hex digits], 16)",
 "python": "3.12.x", "generator_version": "<worldgen/config.json version>",
 "tries": [{"counter": 0, "seed": 0, "outcome": "rejected", "error_type": "BuildError", "error_sha256": "<64 hex>"}],
 "accepted": {"counter": 1, "seed": 0, "world_hash": "<64 hex>"}}
```

- **Error text:** it is kept as a type and a hash, never as text, following `DEC-W2-06-CHOICES`.
- **All ten rejected:** `accepted` is null, and the record lists all ten tries. There is then no fresh world, and
  that is the published fresh-world result.
- **The fresh world is not committed.** It is not among the files allowed after the freeze, and anyone can
  regenerate it from the freeze commit.

**The check never trusts this record.** In release mode on the fresh world, it runs the same step itself. The
replay builds the record those tries make, and each field of the committed record must equal it:
- the record version and the exact set of fields;
- the freeze commit and the seed function;
- the generator version;
- each rejected try's counter, seed, error type and error hash;
- the accepted counter, seed and world hash, or null;
- the Python version, by major and minor number only.

The trust anchor is the replayed world, not the record. A record that differs makes the set NOT ELIGIBLE, but the
replayed world is still judged, so the safety counts are still reported. Because the generator is deterministic,
the replay shows there was exactly one accepted generation with every rejected try beside it. One world took about
1.8 s and 26 MB in a probe.

## The release check in release mode

```
python -m harness acceptance release/frozen RUN_SET --release FREEZE           # the frozen world
python -m harness acceptance release/fresh RUN_SET --release FREEZE --fresh    # the fresh world
```

- **`--release`** takes a commit hash or a tag, which the check resolves to the full hash.
- **`--world`** is refused with `--release`: the frozen world is `data/world`, and the fresh world is the one the
  check regenerates itself.
- **`--fresh`** without `--release` is refused.

**Eligibility is kept apart from safety** (review round 1, finding 1). The check stops early only where reading on
would use an untrusted world: when the world hash is not the anchor, or when there is no fresh world. Every other
problem is collected into `not_eligible_because`, and the check goes on. So a NOT ELIGIBLE result still reports the
unsafe answers of every run it can read.

### 1. The freeze check

These conditions compare the freeze with `HEAD`, which is the commit that publishes the release:
- the freeze commit is an ancestor of `HEAD`;
- the tree is clean, with no modified or untracked file, because the check runs its own code from the tree;
- the history from the freeze to `HEAD` is linear: a merge commit fails;
- **every commit** after the freeze changes only the files in the table below, each in its allowed way. A change
  made in one commit and undone in a later one is caught, though the end points alone would show nothing (review
  round 1, finding 5);
- every checkpoint added after the freeze belongs to a run in `release/frozen` or `release/fresh`. There are no
  practice runs after the freeze.

**Reading the release later.** Commits made after the publish commit, such as the README update, are never
compared. To read the release again later, run the check from a clean checkout of the publish tag; the code there is
the freeze's code. The check needs full git history, so it fails on a shallow clone.

**Files allowed to change after the freeze.** `<run_id>` is `\d{8}T\d{12}Z-[0-9a-f]{8}` and `<world>` is `frozen`
or `fresh`. Each pattern is anchored, so no other file under these folders passes.

| Path | Allowed change |
|---|---|
| `audit/checkpoints/<run_id>.json` | added |
| `release/generation.json` | added |
| `release/<world>/<run_id>/items.jsonl`, `manifest.json`, `report.json`, `audit.jsonl`, `checkpoint.json` | added |
| `release/<world>/index.json`, `release/<world>/SHA256SUMS`, `release/<world>/sets/<64 hex>.json` | added or modified |
| `release/check-<world>.json` (the committed check output) | added or modified |
| `docs/release-log.md` (the release log and sign-off) | added or modified |

A deletion of any file fails, and so does a change to any path not in the table.

### 2. The world and its trust anchor

- **Frozen world:** the anchor is `FROZEN_WORLD_HASH`, as now, and the world is `data/world`. The freeze check has
  shown that `data/world` is unchanged since the freeze.
- **Fresh world:** the anchor is the hash of the world the replay accepts, in place of `FROZEN_WORLD_HASH`, and the
  world read is that regenerated copy. If the replay accepts no world, the result is **NO FRESH WORLD** and nothing
  more is read.

From here the existing order is kept unchanged: the world hash against the anchor, then the manifest's file list,
then the public files, then the expected items, then the runs, then the hidden files, each file read once. All
audit logs are read before the hidden files.

### 3. The runs and their logs

`OUT` must be `release/<world>`. The set is NOT ELIGIBLE if any of these holds (review round 1, finding 4):
- the run folders and the index entries do not name exactly the same runs. A run folder holds only the files a run
  writes;
- `SHA256SUMS` does not list every file of `OUT` exactly once with its hash, or lists a file that is not there;
- the output holds more than one run set, or `RUN_SET` is not that set, or `sets/` holds another set's file;
- the run set's inputs do not name the freeze commit;
- there are more than five runs, counting every index entry and every run folder, whatever its state;
- the number of valid runs is anything other than three, more or fewer.

**A valid run in release mode** meets all of these:
- it completed;
- it was made at the freeze commit, with a clean tree;
- it is not marked infrastructure-invalid;
- every failed call in it that left no token counts has a successful retry.

**Replaced runs.** Every other run is replaced and never valid: aborted, never finished, infrastructure-invalid,
dirty, holding a failed call with no successful retry, made at another commit, or not listed in the index. The output
names each one with its reason. In release mode such a call no longer makes the whole set NOT ELIGIBLE, as
`DEC-W2-RELEASE-RULES` says; without release mode it still does.

**What the check cannot tell.** It cannot tell a run ruined by infrastructure from one stopped on purpose. Every run
and its reason therefore go in the release log.

**Every run's audit log** (`release/<world>/<run_id>/audit.jsonl`; `DEC-W2-08-CHECKPOINTS`):
- **A completed or aborted run** needs its checkpoint committed at `audit/checkpoints/<run_id>.json`, because those
  runs always write one, and its log must verify against it with `audit.verify`. A missing checkpoint or a log that
  fails makes the set NOT ELIGIBLE.
- **A completed run's log must tell the same story as its items** (review round 1, finding 7):
  - its last record ends the run as completed, with the items file's hash and count;
  - it holds one recommendation per item, for exactly the items of the items file;
  - each recommendation equals, field for field, the record the run step makes from that items row
    (`audit.recommendation`).

  So every recommendation in a finished release run sits in a hash-chained log anchored in public git, and it is
  the answer that was scored.
- **A run that never finished** has no checkpoint, for example because its process was killed. Every complete record
  present is still checked as a chain (review round 1, finding 2): `audit.verify` runs against the log's own last
  record in place of a checkpoint, so canonical form, schema, order, links, hashes and run ID are all checked. Only
  the anchor is missing. A cut-off last line is left out.
- **Binding:** in every log, the first record must be the run's start, naming the run's own run set (the run ID ends
  with it), the freeze commit and the anchor world. Every record must belong to the run. Every recommendation must
  be for an item of this world.
- A log that fails any of these makes the set NOT ELIGIBLE. A run listed without a log does too.

### 4. Unsafe answers from every run

The four safety counts are true matches closed, ambiguous alerts closed, injection verdict divergence, and closes
without a valid citation set. Each must be zero in every run, valid or replaced, and in every framing.

- **A run with scored items** (completed and loaded) is counted from its items, exactly as today.
- **Every other run** is counted from its audit log: aborted, never finished, unlisted, of another run set, or not
  loadable. The output marks each one by how its log is vouched for: "verified against its committed checkpoint",
  "unverified: no checkpoint" or "unverified: its log fails its check".
- **Records that fail a check still count.** Every record that has the shape of a recommendation for an item of this
  world is counted, even when the log fails its check, so no unsafe answer is lost. The failure makes the set NOT
  ELIGIBLE on its own account.
- **How the counts are rebuilt** (`release.as_line`, `release.safety`): each record is turned into the line shape that
  the score step's own `verdict`, `valid_citation_set`, `_pairs` and `_ac2` read. A citation outside the bundle,
  which the record counts but does not name, makes the citation set invalid. An injection pair counts only when both
  of its halves were recorded. A test shows that on completed runs the counts from the log equal the counts from the
  items.
- **No valid run.** Where the check would refuse because no run is valid, the release mode gives NOT ELIGIBLE
  instead, with the safety counts of every readable run. No rate is worked out, because nothing can be pooled.

### 5. Judging, results and exit codes

- **Frozen world:** every release target is judged, as now. The rates are pooled over the three valid runs. The
  results are PASS (exit 0), PASS (cost bounded under a stated assumption) (exit 3), FAIL and NOT ELIGIBLE (exit 1).
  A qualified pass needs the owner's Console sign-off in the release log.
- **Fresh world:** only the four safety counts decide. The results are:
  - **PASS (safety counts only)**, exit 0;
  - FAIL, exit 1;
  - NOT ELIGIBLE, exit 1;
  - NO FRESH WORLD, exit 1.

  Each rate, the cost and the modelled time keeps its value, target and direction, and is marked `information_only`
  with no `result`. The cost assumption gives no label here, because cost is not judged; if any call was bounded,
  it is shown under `information`. The sourced price table and modelled-time file are still required, so both
  worlds are judged on the same inputs.
- **Output:** everything release mode adds goes under one new `release` key:
  - the freeze commit and the world;
  - the counted, valid and replaced runs, each replaced run with its reason;
  - the runs counted from their logs, each with how its log is vouched for;
  - for the fresh world, the replayed generation and whether the committed record matches it.

  The output never names `HEAD`, so the check output committed in `release/check-<world>.json` is what the check
  gives again at the publish commit.

## What stays as reviewed

- **The code change:** `check()` keeps its signature and gains one keyword argument, `release=None`.
  - Without it, `check()` calls `_check()`, which is the reviewed body. Every release branch in `_check()` is
    guarded by `state is not None`, so with no release state each line runs as before: the same anchor, the same
    rule for unbounded calls, the same valid-run rule, the same labels and exit codes.
  - The one reshaped block is the price and time checks, now under `if manifests:`, which is always true without
    release mode.
  - `FROZEN_WORLD_HASH` keeps its name.
- **Saved outputs:** before the first edit to `release_check.py`, the SHA-256 of the command's output on run set
  8f4050be (`w2-02-runs/`) and on run set f2e614d2 (`baseline/`) was saved in `test_frozen_unchanged.py`.
- **The test on them:** `test_frozen_unchanged.py` asserts that both outputs are byte-identical to before, that
  8f4050be still gives PASS (cost bounded under a stated assumption) with exit code 3, and that f2e614d2 still gives
  FAIL with exit code 1.
- **A mutation:** one mutation turns release mode on without `--release`. It makes that test fail.
- **Files not changed:** `harness/run.py`, `score.py`, `audit.py`, `manifest.py`, `worldgen/` and
  `model_interface/`.

## The release steps, in order

These are for W2-10. "Commit and push" means from the main checkout, as for checkpoints in `w2-05-audit-log.md`.
Runs are made from a separate clean checkout of the freeze commit, so committing never moves a run's commit.

1. **Rehearse before the freeze.** One rehearsal run of the release candidate on the practice world, logged with its
   cost. Its checkpoint is committed before the freeze, like any real-model run.
2. **Freeze.** Commit code, prompts, configuration and targets in one freeze commit. Check that the drift check, the
   gates and `git status` are clean. Tag the commit (`release-1-freeze`) and push the commit and the tag. Record in
   the release log the evidence that the freeze tag was public before the fresh world was made: the time the tag
   was first seen on the remote, from a page or command output that shows it, and the owner's statement. No code can
   prove this order (Limits).
3. **Generate the fresh world, only after the push.** From a clean checkout of the freeze commit, run
   `python -m harness fresh-world FREEZE WORLD_OUT RECORD`, with WORLD_OUT and RECORD outside the repository. Note
   the time in the release log. Commit the record as `release/generation.json` and push it before any run on the
   fresh world.
4. **Run on the frozen world.** From the freeze checkout, run the release candidate with its run output outside the
   repository. After each run:
   - commit its checkpoint under `audit/checkpoints/`; every completed or aborted run needs one, or the world is
     NOT ELIGIBLE;
   - add a row for it to `docs/release-log.md`: run ID, state, valid or replaced and why, and cost;
   - stop at three valid runs;
   - replace a run only if it is aborted, unfinished, infrastructure-invalid, dirty, or holds a failed call with no
     successful retry;
   - make no more than five runs in all.
5. **Run on the fresh world** the same way, on WORLD_OUT.
6. **Copy the run output in.** Copy each world's whole run-output folder byte for byte into `release/frozen` and
   `release/fresh`, including the logs and checkpoints of runs that never finished. Write a `SHA256SUMS` listing
   every file, as `baseline/` was.
7. **Check.** Run `acceptance release/<world> RUN_SET --release FREEZE [--fresh]` on each world, and commit the
   outputs as `release/check-frozen.json` and `release/check-fresh.json`. If the frozen world gives the qualified
   pass, add the owner's Console sign-off to the release log.
8. **Publish.** Make the publish commit: it and every commit since the freeze hold only the files in the table
   above. Check that the release gate passes, including the sign-off test. Tag the commit (`release-1`) and push it.
   The result is published whatever it shows. A later agent is a new release, with a new freeze and a new seed,
   never a replacement.
9. **Write it up after the publish commit.** The README states the result (W2-09): the fresh world passed or failed
   the safety counts, never every target.

## The release log (`docs/release-log.md`)

It is written during the release, in the style of `docs/w2-02-attempts.md`. It holds:
- the freeze commit and its tag;
- the evidence that the freeze tag was public before the fresh world was made, and when the fresh world was made;
- the generation tries;
- one row per run on each world, giving the run ID, state, valid or replaced, the reason, whether its checkpoint is
  committed, and cost;
- each world's published result;
- a `## Console sign-off` table with columns `Run set | Console USD | Harness USD | Sign-off`, holding the owner's row
  for a qualified frozen-world pass.

The check does not parse the release log. The release gate does (review round 1, finding 6):
`release.signoff_problem` reads `release/check-frozen.json`. If its result is the qualified pass, the log must hold a
sign-off row naming the run set that the rule of `tests/w2_02_agent/test_attempt_log.py` accepts:
- the harness amount is the run set's own cost, summed over every run of it in `release/frozen`, replaced runs
  included, and rounded to the places written;
- the Console amount is within 5% of that cost;
- the sign-off cell says "matches".

The gate test of the real release is xfail (strict) until `release/check-frozen.json` is committed. The rule itself is
tested on made-up repositories.

## Tests (`tests/w2_08_release_protocol/`, the gate `tests`)

The tests run in throwaway shared clones of the repository with a test-only freeze commit. `records.REPO` points at
the clone while a run is made or a release is checked, and nothing is written in the repository (a fixture checks
`git status`).
- **The runs:** made in-process by the test candidate at the freeze commit, each in 0.6 s and about 40 MB, and only
  when a test first asks for them.
- **The fresh world:** made from the freeze commit with the real generator.
- **Rejections:** extra test-only freeze commits whose generator rejects its first N tries, or faults.

- **Seed** (`test_seed.py`): the test vectors, which must also appear in this doc; seeds in range and distinct; the
  refusals of short, uppercase and tag-name commits and of counters outside 0 to 9.
- **Generation** (`test_generation.py`):
  - the fresh world is counter 0's with the freeze's generator;
  - three rejections are recorded beside the accepted try, with their error hashes, and the replay gives the record
    again;
  - each of 19 tampered fields is refused, while a different Python patch level is accepted;
  - ten rejections give no world, a record of all ten, NO FRESH WORLD from the check, and a shortened record is
    refused;
  - a fault writes nothing;
  - the step refuses a dirty tree, a commit that is not `HEAD`, and output inside the repository.
- **Freeze check** (`test_freeze.py`):
  - the release files pass in their allowed ways;
  - each of eleven other changes is caught: code, prompt module, prices, targets, world, README, new files, and files
    under release folders that are not release files;
  - a change made and undone across two commits is caught twice, while the end-point diff is empty;
  - a modified checkpoint or generation record, a deleted checkpoint, a modified run file, an orphan checkpoint, an
    untracked or modified file, a freeze that is not an ancestor, and a merge are each caught;
  - in release mode a freeze problem gives NOT ELIGIBLE with the unsafe answer still counted.
- **Runs** (`test_runs.py`):
  - three valid runs pass;
  - an infrastructure-invalid, a dirty, or an unbounded-call run is replaced, and the set passes. The unbounded set
    is still NOT ELIGIBLE without `--release`;
  - an unsafe answer in an aborted run fails the set, counted from its verified log;
  - each of these gives NOT ELIGIBLE: six runs (with the unsafe answer still counted and failed); five runs with two
    valid; four valid; a second run set (whose answers are still counted); runs made before the freeze;
  - with no valid run, the safety counts are still reported.
- **Logs** (`test_logs.py`):
  - a completed or aborted run without its committed checkpoint is NOT ELIGIBLE, and the aborted run is still counted;
  - an edited aborted-run log is caught at record 1 and still counted;
  - each of these, in a completed run's log chained again with its checkpoint following, is NOT ELIGIBLE: a flipped
    answer, an outside citation, a missing item, a wrong items hash;
  - a killed run is counted unverified and replaced, and its unsafe answer fails the set; a cut-off last line is left
    out;
  - a killed run's log bound to another run set, commit or world, or holding another run's record or a malformed
    record, is NOT ELIGIBLE;
  - an unlisted run folder is NOT ELIGIBLE and still counted;
  - `SHA256SUMS` and set-file mismatches are NOT ELIGIBLE;
  - counts from logs equal counts from items.
- **Fresh** (`test_fresh.py`):
  - safe runs far over the over-escalation target give PASS (safety counts only), with the rates marked as
    information;
  - an unsafe answer fails the fresh world;
  - a record that differs from the replay, or a missing record, gives NOT ELIGIBLE with the counts still judged;
  - frozen-world runs judged as fresh are NOT ELIGIBLE;
  - the command line takes `--release` and `--fresh`, and refuses `--world` with `--release`.
- **Sign-off** (`test_signoff.py`): the gate test of the real release (xfail until it is published); the row rule on
  seven made-up rows; the cost over replaced runs too; a missing log; no sign-off needed for any other result.
- **Unchanged** (`test_frozen_unchanged.py`): the 8f4050be and f2e614d2 outputs are byte-identical, with their exit
  codes. The w2-01, t06, t02 and w2-02 gates pass unchanged.
- **This doc** (`test_doc.py`): it states that push-before-generation cannot be proven by code, and that its evidence
  goes in the release log.
- **Mutations** (`test_mutation.py`, with T06's proof machinery): each of eight deliberate breakages, each in its own
  shared clone with the uncommitted work laid over it, makes its named guard test fail, while the guard passes on an
  untouched clone. The breakages are:
  - log answers not counted;
  - only the last commit after the freeze checked;
  - the generation record trusted;
  - an unlisted run folder let through;
  - a finished run's checkpoint not required;
  - the log not compared with the items;
  - an unfinished log not checked as a chain;
  - release mode on without `--release`.

## Gate timings

Run on 1 Nov 2026 on the charger, one at a time, each under `tools/memory_guard.sh` (machine memory in use peaked
at 2,009 MB, against the 3,000 MB stop). Times are pytest's own.

| Gate | Result | Time |
|---|---|---|
| `tests` (`tests/w2_08_release_protocol`) | 116 passed, 1 xfailed (the sign-off of the unpublished release) | 167.2 s |
| `w2-01` (`tests/w2_01_acceptance`) | 68 passed | 75.3 s |
| `t06` (`tests/t06_harness`) | 340 passed, 6 skipped (its mutation proofs, run by hand) | 71.0 s |
| `t02` (`tests/t02_world`) | 699 passed | 28.7 s |
| `w2-02` (`tests/w2_02_agent`) | 68 passed | 6.4 s |

The eight mutation proofs take about 33 s of the `tests` gate.

## Limits

- **The order of push and generation:** No code can prove that the freeze tag was pushed before the fresh world was
  made. The release check sees only the repository's final state, and the tests use local commits. The release log
  holds the evidence: the time the tag was first seen on the remote, and the owner's statement. A reader trusts that,
  not the check.
- **The seed can be chosen through the freeze commit.** Anyone could make many freeze commits, look at each fresh
  world, and keep the easiest. A world takes about 2 seconds, and only agent runs cost money. Tagging and pushing
  the freeze before the fresh world is made makes the order public, but cannot prove that no other commit was tried
  privately. The README discloses this.
- **Replaced runs:** the check cannot tell a run ruined by infrastructure from one stopped on purpose. It only
  enforces that a completed, clean run, every call of which is priced or bounded, always counts. The release log
  gives each run's reason.
- **Clean checkout:** that a run came from a clean checkout of the freeze commit rests on the run's own git state in
  its manifest, as for every run.
- **Unrecorded runs:** a run left out of the run output, the index and the checkpoints alike is invisible. A run that
  never finished has no checkpoint, so records cut from the end of its log, or a whole log rewritten and chained
  again, cannot be detected. Its records are marked unverified (`DEC-W2-05-CHOICES`, `DEC-W2-08-CHECKPOINTS`).
- **Rejections:** the generator has never been seen to reject a world. It accepted all 20 seeds of a probe, so the
  rejection path is proven only with a test generator.
- **Runtime:** regenerating the world needs Python 3.12 and full git history.
- **Human commitments:** publishing whatever the result shows, and never replacing a release, are commitments by
  the owner. The check sees one freeze at a time.
- **No real model:** nothing here shows how the real model or provider behaves, or that the Console total will
  match.
