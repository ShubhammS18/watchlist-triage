# Release runs (W2-10)

Status: design, 2 Nov 2026. Not yet reviewed: this design is round 1 of at most four (`DEC-W2-10-REVIEW-BUDGET`).
Requirements: FR-23, AC-19, and AC-1 to AC-6 and AC-12 on the release worlds. Rules: `DEC-W2-RELEASE-RULES`, as built
by `DEC-W2-08-CHOICES` and `DEC-W2-08-CHECKPOINTS`, and done and checked as `DEC-W2-10-CHOICES` says.

This task runs the release and publishes it. It adds three things, and no harness, agent or wrapper code:
- the gate tests (`tests/w2_10_release_runs/`), which check the published release from committed files only and
  never call a model;
- the release log (`docs/release-log.md`);
- the release steps, now run through the run wrapper.

The agent is attempt 2's. At HEAD (`16d1ec5`) its prompt hash is `1740d71e…cc16e` and its rule-code hash is
`1c964fd8…fc1de`, the same as in all three manifests of run set `8f4050be`. Since `dbb230e`, no file of the agent,
model interface, framings, config, targets, world or world generator has changed, except a docstring in
`triage_agent/record.py`. The harness has changed since (W2-03 to W2-08) and has not yet run a real model; the
rehearsal is its first real run.

## Supersedes

| Line | What it says | Now |
|---|---|---|
| `docs/w2-05-audit-log.md:132` | the separate checkout is `../watchlist-triage-at-<commit>` | for the release it is `~/release-1/checkout`, outside `~/projects` (`DEC-W2-10-CHOICES`) |
| `docs/w2-05-audit-log.md:134` | a run is started with `harness run-and-score` | release and rehearsal runs are started with `baseline_run run`, which calls it after its checks (`DEC-W2-10-CHOICES`) |
| `docs/w2-08-release-protocol.md:321-353` | the release steps | the steps below, which follow them and add the wrapper, the paths, the stop rules and what to do when a step fails |

## The run wrapper from the separate checkout

Every paid run goes through `python -m baseline_run run CONFIG OUT [--rerun-cause TEXT]`, as attempts 1 and 2 did. Its
checks are those of `baseline_run/wrapper.py`:
- a clean tree, untracked files included, with the output outside the repository;
- the recorded run settings;
- sourced modelled times and prices;
- the API key, by one free token-counting request.

It then prints an upper bound on the run's cost and asks for "yes". The run itself goes through `tools/timed_run.sh`,
which needs the charger in and the fixed benchmark at most 0.82 s. It runs under `tools/memory_guard.sh` at 3,000 MB
and 7,200 s. The wrapper sets those limits itself, so the guard's 110-second default does not apply.

**Checked on 2 Nov 2026, with no key and no model call:**
- **Where it ran:** a throwaway worktree at HEAD in the session scratchpad, with `.venv/bin/python -B` started from
  inside the worktree.
- **Which code it used:** the wrapper resolves `REPO` to the worktree, so it checks and launches the checkout's own
  code. There is no editable install in `.venv` that could pull in the main checkout.
- **Through the real command with the key unset:** `baseline_run run` passed checks a to e and refused at the key
  (exit 2, before any network call). This held for an outside config for the practice world and for an outside
  config for a second world outside the repository (seed 1, made for the check and deleted).
- **The checks called directly, with a made-up key value** that is never sent: the clean-tree, input, settings,
  time and price checks, and the harness's own `load_config`, passed for three configs. The cost bound was computed
  for each:

  | Config | World | Calls | Prompt bytes | Bound USD | Credit it asks for |
  |---|---|---|---|---|---|
  | outside, practice | `~/practice-worlds/seed-20261027` | 888 | 1,707,735 | 0.3981 | 0.5972 |
  | outside, second world | seed 1, outside the repository | 885 | 1,700,393 | 0.3966 | 0.5949 |
  | the checkout's `config/run-triage.json` | the checkout's `data/world` | 888 | 1,708,931 | 0.3982 | 0.5973 |

  The checkout stayed clean, and the worktree was removed.
- **Not exercised:** the launch itself, `timed_run.sh` then `memory_guard.sh` then `harness run-and-score`, because
  that is a paid run. It uses the checkout's own `tools/`, which are the same scripts attempts 1 and 2 used. The
  rehearsal is its first use from a separate checkout.

**Three things about the wrapper that matter here:**
1. **Its bound counts one token per prompt byte**, so it is about USD 0.40 a run, above the 0.30 stop rule. The stop
   rule applies to what a run actually costs (about 0.10 so far), not to this bound.
2. **The benchmark limit is fixed at 0.82 s**, and the wrapper's setting overrides the environment. The W2-08
   timings on the charger had benchmarks of 0.788 to 0.850 s. So the wrapper can refuse on a slow day; on battery
   on 2 Nov 2026 the benchmark took 1.417 s. A refusal starts nothing: no index entry, no cost, and no run used up.
   Close other programs and try again. See open point O2.
3. **It asks for `--rerun-cause` after an aborted, unfinished or infrastructure-invalid run** in the same output
   folder, and records the cause in the index and the manifest. The release log copies it.

## The release steps

**Who does what:**
- **The owner:** every paid run, both API keys, the Console readings and sign-off, every tag and push, and the
  freeze commit.
- **Claude, when asked:** copies run output in (it may read `~/release-1`, `DEC-W2-10-CHOICES`), runs the release
  check, and drafts release-log rows and commits for the owner to approve.
- **Nobody** makes a Genesis write between the freeze and the publish commit. Read-only commands (`brief`,
  `context`, `query`) leave the tree clean and may be used.

```
REPO=~/projects/watchlist-triage   REL=~/release-1   CO=$REL/checkout   PY=$REPO/.venv/bin/python
```

**Before every paid run:**
1. Plug the charger in and close VS Code and other heavy programs.
2. Load the key without echo: `read -rs WT_ANTHROPIC_API_KEY; export WT_ANTHROPIC_API_KEY`.
3. Note the Console balance.

**After every paid run:**
1. Wait about 10 minutes, then note the balance again.
2. Run `$PY -m harness verify-log OUT/<run_id>/audit.jsonl OUT/<run_id>/checkpoint.json`.
3. Write the run's row in the release log.

**Stop rules** (`DEC-W2-10-CHOICES`): if a run costs over USD 0.30, or W2-10's Console spend passes USD 2.00, stop
before the next run and talk.

### 1. Rehearsal, before the freeze (owner)

The rehearsal uses the `w2-10-rehearsal` key and the practice world.

```
git -C $REPO worktree add --detach $REL/rehearsal-checkout HEAD
# $REL/run-practice.json: run-triage.json's settings, with absolute paths to the practice world and to
#   $REL/rehearsal-checkout/config/{model,prices,modelled_time}.json
cd $REL/rehearsal-checkout && $PY -m baseline_run run $REL/run-practice.json $REL/out-rehearsal
cd $REPO && mkdir -p audit/checkpoints && cp $REL/out-rehearsal/<run_id>/checkpoint.json audit/checkpoints/<run_id>.json
git add audit/checkpoints/<run_id>.json docs/release-log.md && git commit -m "W2-10: rehearsal checkpoint <run_id>" && git push
git worktree remove $REL/rehearsal-checkout
```

**If it goes wrong:**
- **A guard kill or WSL crash:** costs only money. Log the try with its Console cost, and run again into a new
  output folder.
- **An aborted or infrastructure-invalid run, or gross figures** (any true match closed, or over-escalation far
  above the 0.06% of the last practice run): a finding. Fix it before the freeze. Never freeze over it.

### 2. Freeze, tag and push (owner)

By the freeze commit, the repository must hold:
- the rehearsal checkpoint;
- the reviewed gate tests, which xfail strictly until the release is published;
- the release log with its rehearsal rows;
- every W2-10 Genesis record;
- any last change to `docs/w2-02-attempts.md`, which may not change after the freeze.

The freeze changes no code: `git diff --name-only <rehearsal commit> <freeze>` lists only `tests/w2_10_release_runs/`,
`docs/`, `.genesis/` and `audit/checkpoints/` (gate check G8).

Checks: `git status` clean, the drift check (`$PY tools/check_world_drift.py`) clean, and every gate passing or
xfailing as expected.

```
git tag -a release-1-freeze -m "W2-10 freeze" && git push origin main release-1-freeze
date -u +%FT%TZ; git ls-remote --tags origin release-1-freeze    # both outputs into the log, with the owner's statement
```

**If it goes wrong:**
- **A failing gate or a dirty tree:** fix it in a new commit before tagging.
- **A rejected push:** never force-push a freeze. Fetch and look.
- **A mistake found after the push but before generation:** a new freeze tagged `release-1-freeze-2`, with the
  reason in the log. No world was made from the first freeze. The gate's tag names would then change too (open
  point O1).

### 3. Generate the fresh world (owner, only after the push)

```
git -C $REPO worktree add --detach $CO $(git -C $REPO rev-parse release-1-freeze^{commit})
cd $CO && $PY -m harness fresh-world release-1-freeze $REL/world-fresh $REL/generation.json; date -u +%FT%TZ
cd $REPO && mkdir -p release && cp $REL/generation.json release/generation.json
git add release/generation.json docs/release-log.md && git commit -m "Release 1: generation record" && git push
```

**If it goes wrong:**
- **A refusal** (not HEAD, a dirty tree, not Python 3.12, output inside the repository): makes nothing. Fix the
  cause and run it again.
- **A fault other than `BuildError`:** a bug in frozen code. Stop. It needs a new freeze.
- **All ten tries rejected:** that is the published result, NO FRESH WORLD. Commit the record, and make no
  fresh-world runs.
- **A WSL crash mid-generation:** the step is deterministic and writes its record last. Delete the partial outputs
  outside the repository, run it again, and log both.

### 4 and 5. Three runs on each world (owner)

The release runs use the `w2-10-release` key, from `$CO` only.
- **Frozen world:** the checkout's own `config/run-triage.json`, output to `$REL/out-frozen`.
- **Fresh world:** only after `release/generation.json` is pushed, with `$REL/run-fresh.json` (the same settings,
  with absolute paths to `$REL/world-fresh` and to `$CO/config/…`), output to `$REL/out-fresh`.

```
cd $CO && $PY -m baseline_run run config/run-triage.json $REL/out-frozen [--rerun-cause "TEXT"]
cd $REPO && cp $REL/out-frozen/<run_id>/checkpoint.json audit/checkpoints/<run_id>.json
git add audit/checkpoints/<run_id>.json docs/release-log.md && git commit -m "Release 1: checkpoint <run_id> (frozen)" && git push
```

For each world:
- Stop at three valid runs, and never make more than five runs.
- Replace a run only if it is aborted, unfinished, infrastructure-invalid, dirty, or holds a failed call with no
  successful retry. Never replace a completed, clean, priced run, whatever it shows.
- After fresh run 1, compare its cost with the stop rule before run 2. The fresh world's call count is first known
  from the wrapper's bound.

**If it goes wrong:**
- **An aborted or infrastructure-invalid run:** commit its checkpoint, because aborted runs write one. Wait until the
  cause has cleared, then run again with `--rerun-cause`.
- **A WSL crash or guard kill:** the run never finished.
  - Leave its folder and its `started` index entry exactly as they are. It has no checkpoint.
  - Log it as replaced, with its Console spend as its cost, in its own row (`DEC-W2-10-CHOICES`).
  - After the restart, `git -C $CO status --short` must be empty and `git -C $CO rev-parse HEAD` must be the freeze.
    Then run again with `--rerun-cause`.
  - After a second crash on one world, stop and find the cause first: five runs leave room for only two replaced.
- **A dirty run:** something wrote into `$CO`. Write nothing there.

### 6 to 9. Copy, check, sign off, publish

1. **Copy (Claude, when asked).** For each world, copy byte for byte with the existing copy step, which lists every
   file in `SHA256SUMS` in `baseline/`'s format and verifies both sides:

   ```
   $PY -c "from pathlib import Path; from baseline_run.copy_step import copy_baseline; copy_baseline('$REL/out-frozen', Path('release/frozen'))"
   ```

   Before copying, check that the output folder holds no run folder the index does not list. If one exists, stop
   and talk: the copy step leaves unlisted folders out, and the check needs everything. Commit and push.
2. **Check (Claude or the owner).** Run the check on each world, and run each check twice, comparing the two outputs
   with `cmp`. Commit both outputs and push.

   ```
   $PY -m harness acceptance release/frozen <set> --release release-1-freeze > release/check-frozen.json
   $PY -m harness acceptance release/fresh <set> --release release-1-freeze --fresh > release/check-fresh.json
   ```

   If the result is NOT ELIGIBLE for a bookkeeping reason, such as a checkpoint not committed or a copy mismatch,
   fix the bookkeeping in an allowed file and check again. Any other result is the result.
3. **Sign-off (owner).** If `check-frozen.json` is the qualified pass, add the sign-off row (see the release log).
4. **Publish (owner).** Before the tag, the tree must be clean, the release log complete, and these must pass, run
   directly with pytest, not through Genesis:
   - the W2-08 sign-off test;
   - `tests/w2_10_release_runs` against the publish commit (open point O1).

   ```
   git commit -m "Release 1: publish"
   git tag -a release-1 -m "Release 1" && git push origin main release-1
   ```

   Only then the Genesis gates, the review round 4, the approval and completion. Revoke both keys.

## The release log (`docs/release-log.md`)

It is written during the release, in the style of `docs/w2-02-attempts.md`. The gate parses the headings and tables
below, so their names and columns are fixed. Amounts are USD decimals.

```
# Release 1 log

Task W2-10-release-runs. Rules: DEC-W2-RELEASE-RULES, DEC-W2-08-CHOICES, DEC-W2-08-CHECKPOINTS, DEC-W2-10-CHOICES.

- Freeze commit: `<40 hex>`, tag `release-1-freeze`
- Starting point: wave-2 spend USD 0.95 (docs/w2-02-attempts.md); Console balance USD 4.56 (owner, 2 Nov 2026)
- Keys: w2-10-rehearsal (rehearsal), w2-10-release (release runs); both revoked after the publish
- Stop rules: a run over USD 0.30, or W2-10 over USD 2.00, stops the release before the next run

## Rehearsal
| Date | Run ID | Agent commit | Run set | State | Key figures | Harness USD | Console before | Console after | Spend USD | Peak memory MB | Note |

## Freeze and push
(the `date -u` and `git ls-remote` output, a link or screenshot reference showing the tag on the remote, and the
owner's statement that the tag was public before the fresh world was made)

## Generation
- Run at (UTC): ...
| Counter | Seed | Outcome | Error type | World hash |

## Frozen world
| # | Run ID | State | Valid or replaced | Reason | Re-run cause | Checkpoint committed | Harness USD | Console before | Console after | Spend USD | Note |

## Fresh world
(the same columns)

## Results
| World | Run set | Check output | Result |

## Console sign-off
| Run set | Console USD | Harness USD | Sign-off |

## Running total
Wave-2 spend: USD <total> (before this log 0.95 + rehearsal <a> + frozen <b> + fresh <c>)
```

- **Harness USD** is the run's own known cost from its index entry, rounded to the places written. For a run with no
  cost, such as a killed run, it is `none`. **Spend USD** is the Console's after minus before.
- **Console sign-off:** only a qualified frozen-world pass needs a row. Its Console USD covers the priced runs only,
  so a killed run's spend stays in its own row (`DEC-W2-10-CHOICES`). That matches the rule already in
  `release.signoff_problem`, which sums the cost of every run in the index that has one.

## The gate tests (`tests/w2_10_release_runs/`, the gate `tests`)

They read committed files and git only. They call no model and make no network request.
- **The real release** (`test_published.py`) is xfail (strict) until the tag `release-1` exists.
- **The dry run** (`test_rules.py`) applies the same checks to made-up releases, built in shared clones with W2-08's
  helpers (`tests/w2_08_release_protocol/release_common.py`: the test candidate agent, `new_clone`, `make_runs`,
  `publish`), which are reused, not copied. The W2-08 fixture that checks `git status` applies too.

**How the real release is checked.** A session fixture clones the repository into a temporary folder, with full
history and the tags, and checks out `release-1`. Every check below runs in that clone, with the clone's own code,
which is the freeze's. So commits after the publish (Genesis evidence, completion, W2-09's README) cannot break the
gate (`DEC-W2-10-CHOICES`). The checks:

| | Check | Read from |
|---|---|---|
| G1 | **The freeze commit exists.** `release-1-freeze` is an ancestor of `release-1`. The freeze commit named by `release/generation.json`, by both check outputs (`release.freeze_commit`) and by the log's freeze line is that commit. | tags, the record, the outputs, the log |
| G2 | **Nothing the freeze pins changed after it:** `release.freeze_problems(clone, freeze)` is empty, for every commit up to `release-1` | git history |
| G3 | **The seed is the function's:** every try's seed equals `release.fresh_seed(freeze, counter)`, with counters running 0, 1, … with no gap | the record |
| G4 | **One accepted generation:** the committed record equals the check's own replay (`DEC-W2-10-CHOICES`), as G5's fresh output shows. Ten rejected tries with the result NO FRESH WORLD pass too. | the reproduced fresh output |
| G5 | **The committed check output is what the check gives:** `python -m harness acceptance release/<world> <set> --release <freeze> [--fresh]` is run in the clone, and its standard output is byte-identical to `release/check-<world>.json` | the run output, the world, the replay |
| G6 | **Every run is in the log, within five per world.** The run IDs in the index, in the run folders and in the world's log table are the same set, with at most five. Each row's valid or replaced status and reason match the reproduced output's `release.runs`. Its checkpoint cell is "yes" exactly when `audit/checkpoints/<run_id>.json` is in the tree. Its Harness USD is the index cost rounded to the places written, or `none`. Its Spend USD is a decimal. | the log, `release/<world>`, the tree |
| G7 | **Order in the history:** every rehearsal checkpoint was added at or before the freeze, and no release-world checkpoint was. `release/generation.json` was added after the freeze, in an ancestor of every commit that adds a fresh-world checkpoint. | git history |
| G8 | **The rehearsal came first, with the same code:** at least one rehearsal row. Every completed or aborted rehearsal has its checkpoint in the freeze's tree. Every rehearsal row's agent commit is an ancestor of the freeze, and the diff from it to the freeze touches only `tests/w2_10_release_runs/`, `docs/`, `.genesis/` and `audit/checkpoints/`. | the log, git |
| G9 | **Published and consistent:** both check outputs are committed at `release-1`. The log's Results rows equal their results. The running total equals 0.95 plus every Spend USD in the log. | the log, the outputs |
| G10 | **The sign-off:** `release.signoff_problem(clone)` is None, as in W2-08's sign-off test, here at the tag | the log, the outputs, the index |
| G11 | **Push evidence present:** the "Freeze and push" section holds the freeze hash and `refs/tags/release-1-freeze`. It cannot show the order (Limits). | the log |

None of these asks whether the release passed: a published FAIL, NOT ELIGIBLE or NO FRESH WORLD passes the gate.

**The dry run** (`test_rules.py`, review rounds 2 and 3) does these:
- **Builds one made-up release** in a clone: a test freeze tagged `release-1-freeze`, a rehearsal checkpoint before
  it, a generation record, three valid frozen runs beside one killed and one aborted run, three valid fresh runs, a
  log written to the format above, both check outputs and a `release-1` tag. It passes G1 to G11.
- **Breaks it, one way at a time.** Each break fails its named check:
  - a missing log row and a sixth run (G6);
  - a log row calling a replaced run valid (G6);
  - a wrong harness amount (G6);
  - a seed not from the function (G3);
  - an edited check output (G5);
  - a code change after the freeze (G2);
  - a rehearsal checkpoint added after the freeze (G7, G8);
  - the generation record committed after a fresh-world checkpoint (G7);
  - a wrong running total (G9);
  - a missing push section (G11).
- **Passes a made-up FAIL and a made-up NO FRESH WORLD,** each published consistently.

**Timing.** Genesis stops a gate at 120 s; the aim is under 100 s.
- **What is known:**
  - the reviewed check took 1.85 s and 60 MB on attempt 2's three runs;
  - a fresh replay takes about 2 s per try;
  - W2-08's whole suite, which builds made-up releases the same way, takes about 76 s.
- **The estimate:** 10 to 40 s for G5 on both worlds, plus the dry run. Each made-up release is built once per
  session and reused, as W2-08's replays are.
- **How it will be measured:** the gate command through `tools/timed_run.sh`, three times, in the xfail state before
  the freeze. Then three more times after the publish, when G5 runs on the real release. The result, time,
  benchmark, and memory before and at peak are recorded each time.
- **If it is over:** the made-up releases are shared further. The G checks themselves stay.

## Open points for the owner, before round 1

- **O1. The gate can fail with no way to fix it.**
  - **A freeze problem:** the outcome makes "nothing the freeze pins changed after it" a gate check (G2). A freeze
    problem cannot be undone, because undoing it is a change too. Such a release would be published as NOT ELIGIBLE
    and could never complete the task. Should it then be closed as a new release (a new freeze and seed, as
    `DEC-W2-RELEASE-RULES` says for a later agent), or should G2 report and not fail?
  - **A second freeze** (`release-1-freeze-2`, step 2) changes the tag names the gate reads. Should the gate take
    the freeze tag from the log's freeze line?
- **O2. The wrapper's 0.82 s benchmark limit is fixed in code** (`baseline_run/wrapper.py`, `ENV`). Recent
  benchmarks on the charger were 0.788 to 0.850 s, so it may refuse. A refusal costs nothing, but a change could
  only be made before the freeze, as code under `DEC-T07-WRAPPER-CHECKS`.
- **O3. The wrapper's refusal checkpoint.** After a run, the wrapper prints a "refusal checkpoint" when more than 2%
  of items were refused (`DEC-T07-REFUSALS`). Should that also stop the release before the next run? It is not
  among `DEC-W2-10-CHOICES`'s stop rules.

## Limits

These are the W2-08 limits, still in force:
- **Push before generation:** no code can prove the freeze tag was public before the fresh world was made. The
  release log holds the evidence and the owner's statement (G11 checks only that it is there).
- **The seed can be chosen** through the freeze commit by trying freezes privately. The README discloses this.
- **The order of runs:** the gate checks the order of commits, not of runs. A checkpoint shows when a run was
  committed, not when it ran.
- **Unrecorded runs:** a run left out of the output, the index, the checkpoints and the log alike is invisible.
- **The Console:** the gate checks the log's arithmetic and the sign-off rule, not the Console figures. Those are
  the owner's. A killed run's cost rests on the Console alone.
- **Publication:** the gate checks the commit and the tag, not that they were pushed. The push is the owner's step.
- **No real model:** nothing here shows how the real model or provider will behave.
