# Release runs (W2-10)

**Pre-release design.** This is the design and gate-test record as it stood before the release ran. The published
release is `docs/release-log.md` at the tag `release-1` (18 Nov 2026); review round 4 checked it there. Read the status,
steps and limits below as written before the runs, not as the published task's status.

Status: design and gate tests revised after review round 3 (17 Nov 2026), the last review before the freeze. Round 1 of
at most four (`DEC-W2-10-REVIEW-BUDGET`) reviewed the design and found four blockers and five smaller issues; the owner
accepted all nine (see "Review round 1"). Round 2 reviewed the gate tests and the dry run, found round-1 findings 4, 7
and 8 not resolved and five new findings, and the owner accepted all of them (see "Review round 2"). Round 3 found one
blocker and three smaller issues, fixed without another round as the budget says (`DEC-W2-10-ROUND3`, see "Review round
3"). Requirements: FR-23, AC-19, and AC-1 to AC-6 and AC-12 on the release worlds. Rules: `DEC-W2-RELEASE-RULES`, as
built by `DEC-W2-08-CHOICES` and `DEC-W2-08-CHECKPOINTS`, and done and checked as `DEC-W2-10-CHOICES`,
`DEC-W2-10-STOPS`, `DEC-W2-10-LOST-INDEX` and `DEC-W2-10-ROUND3` say.

This task runs the release and publishes it. It adds three things, and no harness, agent or wrapper code:
- the gate tests (`tests/w2_10_release_runs/`), which check the published release from committed files only and
  never call a model;
- the release log (`docs/release-log.md`) and the committed rehearsal evidence (`rehearsal/`);
- the release steps, now run through the run wrapper.

The agent is attempt 2's. At HEAD (`16d1ec5`) its prompt hash is `1740d71e…cc16e` and its rule-code hash is
`1c964fd8…fc1de`, the same as in all three manifests of run set `8f4050be`. Since `dbb230e`, no file of the agent,
model interface, framings, config, targets, world or world generator has changed, except a docstring in
`triage_agent/record.py`. The harness has changed since (W2-03 to W2-08) and has not yet run a real model; the
rehearsal is its first real run.

## Review round 1

The four blockers:

| Finding | What changed |
|---|---|
| 1. The check was run in the main checkout with its output redirected into the tree, so the file it wrote made the tree dirty and the check refuse | Each world's check is run from a clean checkout of the commit holding the run output, with its output written outside the repository. It is run twice, the two outputs are compared with `cmp`, and only then are the agreed bytes copied in (step 7). The dry run's builder makes both outputs before writing either; when it first wrote one before making the other, the gate's G5 caught the difference. |
| 2. The publish commit could be empty, so `git commit` would fail when no sign-off is needed | The publish commit always writes the release log's Results rows and running total, which need the committed check outputs, and the sign-off row only for a qualified pass. The steps check that something is staged, tag locally, run the gate tests, and only then push (step 9). |
| 3. The stop rules were not enforced | The gate's G12 enforces all three from committed data. It orders every run, rehearsal included, by its run ID, which starts with its start time. If a run cost over USD 0.30, or its refusals passed 2%, or the spend so far passed USD 2.00, then no run may come after it. A run's cost is the larger of its harness cost and its Console spend. The dry run has a failing case for each. |
| 4. The rehearsal evidence was not verifiable | The rehearsal's whole run output is committed before the freeze in `rehearsal/` with its `SHA256SUMS`, through the existing copy step, and each finished run's checkpoint under `audit/checkpoints/`. The gate's G8 requires a completed, clean rehearsal on the practice world. Its agent and run settings must be the release runs' own, it must be made at a commit before the freeze with no code change in between, and its log must verify against a checkpoint the freeze holds. |

The five smaller issues:

| Finding | What changed |
|---|---|
| 5. `git ls-remote --tags` shows an annotated tag's own object, not the commit | The log holds the peeled line from `git ls-remote origin 'refs/tags/release-1-freeze^{}'`, which is `<freeze commit>` TAB `refs/tags/release-1-freeze^{}`. G11 requires it. |
| 6. No exact steps when all ten tries are rejected | "No fresh world" below. The dry run publishes such a release and the gate passes it. |
| 7. No recovery for a missing or damaged index | Index snapshots during each run, a check after any crash, and the restore rule ("After a crash"). |
| 8. Placeholders in the commands | Every command is now a real one. Run IDs, run sets and the freeze commit are read from the files that hold them. |
| 9. The freeze commit was not shown being made | Step 2 now makes it. |

## Review round 2

| Finding | What changed |
|---|---|
| Round-1 #4 and N1 (blocker). G8 trusted the rehearsal's manifest, did not need its scored files, and was not bound to any agent when there was no release run | G8 now needs every file of the completed rehearsal and its set report, and checks them as one run: the run ID, run set, run-set inputs and index entry agree; the items file is the one the manifest names; the report and set report are the manifest's; the log, verified against its checkpoint, starts with the manifest's run and ends with those items. Its agent and settings must be the ones the freeze's own `config/run-triage.json` gives with the freeze's own code, whether or not there are release runs. Three wrong releases: a required file deleted, a manifest field falsified, both with `SHA256SUMS` made again, and other settings with no release run. |
| Round-1 #7. A crash could leave a run folder with no index and no snapshot covering it, and no path to publish | `DEC-W2-10-LOST-INDEX`: that world is published as it is, as NOT ELIGIBLE, and the gate accepts it when it is consistent ("After a crash", G6). An index that is not JSON makes the check refuse, so it stays outside the repository byte for byte, with its SHA-256 in the log (owner, 13 Nov 2026). The dry run publishes one. |
| Round-1 #8. The steps read the index after a wrapper refusal, and the fresh and re-run commands were described, not given | `after_run` branches on the wrapper's exit code: after a refusal (exit 2) it copies and commits nothing. Otherwise it needs a new index entry. There are separate commands for a first run, a fresh-world run and a re-run, for each world. |
| N2 (blocker). A crash-cut items file made the gate raise | G12 reads only whole records, by a stated rule. A run whose manifest does not say completed may end in one cut-off line, which is not counted. Any other line that is not an item record is a named G12 problem. The lost-index release has a cut-off items file and passes. A break adds a bad line. |
| N3. G8 could read rehearsal files through links | G8 reads nothing under `rehearsal/` while there is a link or a non-regular file there, on disk or at the freeze or the publish commit. A wrong release commits a link. |
| N4. The FAIL, NO FRESH WORLD and broken-freeze cases skipped G5 | Each reproduces both outputs with the documented command and passes them to the gate. An edited output on the FAIL release fails G5. |
| N5. A valid row's Reason, and extra Results rows, were not checked | A valid row's Reason must be empty, and the Results table must have exactly one row for each world and none for anything else. Three breaks. |

## Review round 3

| Finding | What changed |
|---|---|
| R3-1 (blocker). A killed run's last item, whole but without its newline, was not counted, so a refusal there could escape the 2% stop rule | G12 counts every whole record, as the wrapper's `splitlines()` does. A last line without its newline counts if it is a whole item record, and is left out only if it is cut off. A break gives a killed run one whole refusal with no newline, with runs after it, and fails G12. A quick check covers the rule's cases. |
| R3-2. The "Left out" hashes of a lost-index world were optional | `copy_as_is` prints one line per file it leaves out, `` - Left out: `PATH`, SHA-256 `HASH` ``. The owner pastes it under that world's table, and G6 requires a well-formed line for the index of any world committed with run folders and no index. The bytes stay outside git with the owner (`DEC-W2-10-ROUND3`). So the hash can be checked only against the owner's copy, and the README says so. A quick check runs the documented `copy_as_is`, and the lost-index release fails G6 without the line. |
| R3-3. G8 did not compare the rehearsal row's State and Run set cells | Both must be the index's and the manifest's. A break for each. |
| R3-4. The gate's time was close to the 100-second aim | The dry run moved behind a by-hand switch, `W2_10_DRY_RUN=1` (`DEC-W2-10-ROUND3`). The owner runs it once just before the freeze and commits its output as evidence (step 2). The gate keeps the real-release test and the quick checks (`test_quick.py`), the switch test among them. See "Gate timing". |

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
   Close other programs and try again. The limit stays as it is (`DEC-W2-10-STOPS`).
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

Set these once per shell:

```
REPO=~/projects/watchlist-triage; REL=~/release-1; CO=$REL/checkout; PY=$REPO/.venv/bin/python
runs_in() { $PY -c "import json,sys,os; p=sys.argv[1]+'/index.json'; print(len(json.load(open(p))['runs']) if os.path.exists(p) else 0)" "$1"; }
new_run() { $PY -c "import json,sys; r=json.load(open(sys.argv[1]+'/index.json'))['runs']; print(r[-1]['run_id'] if len(r) > int(sys.argv[2]) else '')" "$1" "$2"; }
run_set() { $PY -c "import json,sys,os; p=sys.argv[1]; r=json.load(open(p))['runs'] if os.path.exists(p) else []; print(r[0]['run_set'] if r else '0'*64)" "$1/index.json"; }
same_runs() { $PY -c "import json,sys,pathlib; o=pathlib.Path(sys.argv[1]); i={e['run_id'] for e in json.loads(o.joinpath('index.json').read_text())['runs']}; d={p.name for p in o.iterdir() if p.is_dir() and p.name!='sets'}; print('index and folders agree' if i==d else f'MISMATCH: folders only {sorted(d-i)}, index only {sorted(i-d)}'); sys.exit(i!=d)" "$1"; }
checkpoint() { if [ -f "$1/$2/checkpoint.json" ]; then cp "$1/$2/checkpoint.json" "$REPO/audit/checkpoints/$2.json" && echo "checkpoint $2 copied"; else echo "run $2 wrote no checkpoint"; return 1; fi; }
after_run() {  # after_run EXIT OUT RUNS-BEFORE WORLD: what the wrapper's exit and the index say, then the checkpoint
  if [ "$1" = 2 ]; then echo "REFUSED: no run started. Nothing is copied, committed or logged. Fix what it names (a missing re-run cause: use the re-run command) and paste the command again."; return 0; fi
  RUN=$(new_run "$2" "$3") && [ -n "$RUN" ] || { echo "STOP: exit $1 and no new index entry: see After a crash"; return 1; }
  echo "run $RUN, exit $1"
  [ -f "$2/$RUN/checkpoint.json" ] && $PY -m harness verify-log "$2/$RUN/audit.jsonl" "$2/$RUN/checkpoint.json"
  [ "$4" = rehearsal ] && return 0  # the rehearsal's checkpoints are committed with its evidence
  cd $REPO && mkdir -p audit/checkpoints && checkpoint "$2" "$RUN" && git add "audit/checkpoints/$RUN.json" && git commit -m "Release 1: checkpoint $RUN ($4)" && git push
}
copy_as_is() {  # copy_as_is OUT WORLD: a world whose index is lost, copied in as it is (DEC-W2-10-LOST-INDEX)
  o=$1; d=$REPO/release/$2; [ ! -e $d ] || { echo "STOP: $d exists"; return 1; }
  mkdir -p $d && for r in $o/*/; do cp -r $r $d/; done
  left() { printf -- '- Left out: `%s`, SHA-256 `%s`\n' "$1" "$(sha256sum < $o/$1 | cut -d' ' -f1)"; }
  if $PY -c "import json,sys; json.load(open(sys.argv[1]))" $o/index.json 2>/dev/null; then cp $o/index.json $d/; elif [ -e $o/index.json ]; then left index.json; fi
  [ ! -e $o/index.json.tmp ] || left index.json.tmp
  (cd $d && find . -type f ! -name SHA256SUMS -printf '%P\n' | LC_ALL=C sort | xargs -d '\n' sha256sum > SHA256SUMS) && (cd $o && sha256sum --quiet -c $d/SHA256SUMS) && echo "copied as it is; paste every 'Left out' line above under the world's table in the log"
}
rehearsal_row() {  # rehearsal_row RUN CONSOLE_BEFORE CONSOLE_AFTER PEAK_MB NOTE: the run's row for the release log
  $PY - "$REL/out-rehearsal" "$@" <<'PYEOF'
import json, sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
out, run, before, after, peak, note = Path(sys.argv[1]), *sys.argv[2:7]
entry = next(e for e in json.loads(out.joinpath("index.json").read_text())["runs"] if e["run_id"] == run)
manifest, report = out.joinpath(run, "manifest.json"), out.joinpath(run, "report.json")
commit = json.loads(manifest.read_text())["git"]["commit"][:12] if manifest.exists() else "none"
if report.exists():
    o = json.loads(report.read_text())["figures"]["overall"]
    e = o["over_escalation"]
    figures = (f"true matches closed {o['missed_true_matches']}, ambiguous closed {o['ambiguous_closed']}, "
               f"over-escalation {e['numerator']}/{e['denominator']}")
else:
    figures = "no report"
known = (entry.get("cost") or {}).get("known_cost")
harness = (Decimal(known["numerator"]) / Decimal(known["denominator"])).quantize(Decimal("0.0001"), ROUND_HALF_UP) \
    if known else "none"
spend = Decimal(before) - Decimal(after)
print(f"| {date.today():%-d %b %Y} | `{run}` | `{commit}` | `{entry['run_set'][:8]}` | {entry['state']} | {figures} | "
      f"{harness} | {before} | {after} | {spend} | {peak} | {note} |")
PYEOF
}
```

`index.json` lists runs in the order their entries were last written, so `new_run` names the run just made, and only
if the index has more entries than before the run.

**Before every paid run:**
1. Plug the charger in and close VS Code and other heavy programs.
2. Load the key without echo: `read -rs WT_ANTHROPIC_API_KEY; export WT_ANTHROPIC_API_KEY`.
3. Note the Console balance.

**During every paid run,** once the wrapper has started the harness (about a minute in), snapshot the index:
`mkdir -p $REL/index-snapshots && cp OUT/index.json $REL/index-snapshots/$(date -u +%Y%m%dT%H%M%SZ)-WORLD.json`,
with the run's output folder for OUT and its world for WORLD. The harness writes the index only when a run starts
and when it ends, so this copy is exactly what it wrote at the start ("After a crash").

**Every paid run** is one of the commands below. Each counts the index entries first, then ends with `after_run`
(review round 1, finding 8):
- **Exit 2:** the wrapper refused and started nothing. `after_run` says so and stops. There is nothing to copy,
  commit or log.
- **Any other exit:** it needs a new index entry, or it says STOP. It verifies the run's log if the run wrote a
  checkpoint. For a release run it copies, commits and pushes that checkpoint. A killed run writes none.
- **A refused count:** if `runs_in` cannot read the index, the run is never started and `after_run` says STOP. Go to
  "After a crash".

**After every paid run:**
1. Wait about 10 minutes, then note the balance again.
2. Write the run's row in the release log, with `$RUN` as `after_run` printed it.

**Stop rules:** stop before the next run and talk if any of these happens. The gate checks all three (G12).
- a run costs over USD 0.30 (`DEC-W2-10-CHOICES`);
- W2-10's Console spend passes USD 2.00 (`DEC-W2-10-CHOICES`);
- the wrapper prints its refusal checkpoint after a run, meaning more than 2% of the run's items were refused
  (`DEC-W2-10-STOPS`).

### 1. Rehearsal, and its evidence, before the freeze (owner)

The rehearsal uses the `w2-10-rehearsal` key and the practice world. It is made at the commit holding the reviewed
gate tests. Between that commit and the freeze, only tests, docs, records and evidence may change (G8).

```
cd $REPO && git status --short          # empty
mkdir -p $REL && git worktree add --detach $REL/rehearsal-checkout HEAD
cat > $REL/run-practice.json <<EOF
{"agent": "triage", "world": "$HOME/practice-worlds/seed-20261027",
 "model_config": "$REL/rehearsal-checkout/config/model.json", "workers": 4, "pacer_per_minute": 120,
 "infra_invalid_threshold": "0.02", "price_table": "$REL/rehearsal-checkout/config/prices.json",
 "modelled_time": "$REL/rehearsal-checkout/config/modelled_time.json"}
EOF
```

The rehearsal, a first run:

```
cd $REL/rehearsal-checkout && N=$(runs_in $REL/out-rehearsal) && $PY -m baseline_run run $REL/run-practice.json $REL/out-rehearsal; after_run $? $REL/out-rehearsal "$N" rehearsal
```

A re-run into the same folder: type what went wrong with the run it replaces, then Enter.

```
read -r CAUSE; cd $REL/rehearsal-checkout && N=$(runs_in $REL/out-rehearsal) && $PY -m baseline_run run $REL/run-practice.json $REL/out-rehearsal --rerun-cause "$CAUSE"; after_run $? $REL/out-rehearsal "$N" rehearsal
```

Once it has a completed, clean run, start the release log with its header and the Rehearsal table ("The release
log" below), and add one row for every rehearsal run, killed or re-run ones included, with
`rehearsal_row RUN CONSOLE_BEFORE CONSOLE_AFTER PEAK_MB NOTE >> docs/release-log.md`. It takes the date, run set,
state, commit, key figures and harness cost from the run's own files, and Spend USD as before minus after. Then commit
the evidence:

```
cd $REPO && same_runs $REL/out-rehearsal
$PY -c "import sys; from pathlib import Path; from baseline_run.copy_step import copy_baseline; copy_baseline(sys.argv[1], Path('rehearsal'))" $REL/out-rehearsal
mkdir -p audit/checkpoints && for d in $REL/out-rehearsal/*/; do r=$(basename $d); [ "$r" = sets ] || checkpoint $REL/out-rehearsal $r; done
git add rehearsal audit/checkpoints docs/release-log.md && git commit -m "W2-10: rehearsal evidence" && git push
git worktree remove $REL/rehearsal-checkout
```

**If it goes wrong:**
- **A guard kill or WSL crash:** follow "After a crash". Then run again into the same folder with `--rerun-cause`.
  The killed try is a rehearsal row, with its Console cost.
- **An aborted or infrastructure-invalid run, or gross figures** (any true match closed, or over-escalation far
  above the 0.06% of the last practice run): a finding. Fix it before the freeze, and rehearse again after the fix:
  a code change after the rehearsal fails G8. Never freeze over it.

### 2. The freeze commit, its tag and push (owner)

By now every file the release pins is committed:
- code, prompts, configuration and targets;
- the reviewed gate tests;
- the rehearsal evidence;
- the by-hand dry run's output, `docs/w2-10-dry-run.txt` (below);
- every W2-10 Genesis record;
- any last change to `docs/w2-02-attempts.md`.

The freeze commit adds one thing, the opening of the release log's "Freeze and push" section, and freezes that tree.

**The dry run, by hand, just before the freeze** (`DEC-W2-10-ROUND3`). It is the gate's rules tried on made-up
releases, and is not in the gate. Run it after every other pinned file is committed, so that it tries the gate code
the freeze will hold. Its output is written outside the repository, since the tests check that nothing is written
inside it, and only then copied in:

```
cd $REPO && git status --short          # empty
W2_10_DRY_RUN=1 MEMORY_GUARD_MAX_SECONDS=200 tools/timed_run.sh .venv/bin/python -m pytest tests/w2_10_release_runs -q -rs -p no:cacheprovider > $REL/dry-run.txt 2>&1; echo "exit $?"
tail -3 $REL/dry-run.txt                # every test passed, the real release xfailed, none skipped
(git rev-parse HEAD; date -u +%FT%TZ; cat $REL/dry-run.txt) > docs/w2-10-dry-run.txt
git add docs/w2-10-dry-run.txt && git commit -m "W2-10: dry run before the freeze" && git push
```

- **If any test fails:** stop. A failing dry run is a gate bug, or a fault in the made-up release, found before
  anything is frozen. Fix it, commit, and run it again.
- **Why only then:** the dry run takes about 80 s, which would bring the gate near its 100-second aim once the
  real-release test runs too ("Gate timing").

```
cd $REPO && git status --short          # empty
$PY tools/check_world_drift.py          # clean
.venv/bin/python -m pytest tests/w2_10_release_runs -q -p no:cacheprovider   # passes, with the real release xfailed
printf '\n## Freeze and push\n\nThe freeze commit is the commit that adds this heading.\n' >> docs/release-log.md
git add docs/release-log.md && git commit -m "W2-10: freeze"
git show --stat --format=%H HEAD        # only docs/release-log.md
git tag -a release-1-freeze -m "W2-10 freeze" && git push origin main release-1-freeze
FREEZE=$(git rev-parse 'release-1-freeze^{commit}')
date -u +%FT%TZ; git ls-remote origin 'refs/tags/release-1-freeze^{}'   # paste both into the log
```

- **The peeled line:** the second command prints `$FREEZE` TAB `refs/tags/release-1-freeze^{}`. That line goes in the
  section exactly as printed, in a code block (G11). Add the URL of the tag's GitHub page and your statement that the
  tag was public before the fresh world was made. Then add the line ``- Freeze commit: `$FREEZE`, tag
  `release-1-freeze` `` near the top of the log (G1).
- **If it goes wrong:**
  - **A failing check or a dirty tree:** fix it in a new commit before tagging.
  - **A rejected push:** never force-push a freeze. Fetch and look.
  - **A mistake found after the push but before generation:** make a new freeze tagged `release-1-freeze-2`, with
    the reason in the log, and use the new tag wherever `release-1-freeze` appears below. No world was made from the
    first freeze. The gate reads the freeze commit from the generation record, so it still works
    (`DEC-W2-10-STOPS`; tested).

### 3. Generate the fresh world (owner, only after the push)

```
git -C $REPO worktree add --detach $CO $FREEZE
cd $CO && git status --short && $PY -m harness fresh-world $FREEZE $REL/world-fresh $REL/generation.json; date -u +%FT%TZ
cd $REPO && mkdir -p release && cp $REL/generation.json release/generation.json
git add release/generation.json docs/release-log.md && git commit -m "Release 1: generation record" && git push
```

**If it goes wrong:**
- **A refusal** (not HEAD, a dirty tree, not Python 3.12, output inside the repository): makes nothing. Fix the
  cause and run it again.
- **A fault other than `BuildError`:** a bug in frozen code. Stop. It needs a new freeze.
- **All ten tries rejected:** see "No fresh world".
- **A WSL crash mid-generation:** the step is deterministic and writes its record last. Delete
  `$REL/world-fresh` and `$REL/generation.json`, run it again, and log both tries.

### 4 and 5. Three runs on each world (owner)

The release runs use the `w2-10-release` key, from `$CO` only.
- **Frozen world:** the checkout's own `config/run-triage.json`, output to `$REL/out-frozen`.
- **Fresh world:** only after `release/generation.json` is pushed, with the outside config below, output to
  `$REL/out-fresh`.

```
cat > $REL/run-fresh.json <<EOF
{"agent": "triage", "world": "$REL/world-fresh", "model_config": "$CO/config/model.json", "workers": 4,
 "pacer_per_minute": 120, "infra_invalid_threshold": "0.02", "price_table": "$CO/config/prices.json",
 "modelled_time": "$CO/config/modelled_time.json"}
EOF
```

Each command is one run, then its checkpoint. For a re-run, type what went wrong with the run it replaces, then
Enter.

```
# frozen world, a first run or any run that replaces nothing
cd $CO && N=$(runs_in $REL/out-frozen) && $PY -m baseline_run run config/run-triage.json $REL/out-frozen; after_run $? $REL/out-frozen "$N" frozen
# frozen world, a re-run
read -r CAUSE; cd $CO && N=$(runs_in $REL/out-frozen) && $PY -m baseline_run run config/run-triage.json $REL/out-frozen --rerun-cause "$CAUSE"; after_run $? $REL/out-frozen "$N" frozen
# fresh world, a first run or any run that replaces nothing
cd $CO && N=$(runs_in $REL/out-fresh) && $PY -m baseline_run run $REL/run-fresh.json $REL/out-fresh; after_run $? $REL/out-fresh "$N" fresh
# fresh world, a re-run
read -r CAUSE; cd $CO && N=$(runs_in $REL/out-fresh) && $PY -m baseline_run run $REL/run-fresh.json $REL/out-fresh --rerun-cause "$CAUSE"; after_run $? $REL/out-fresh "$N" fresh
```

The run's log row is committed with the next commit that stages `docs/release-log.md`.

For each world:
- Stop at three valid runs, and never make more than five runs.
- Replace a run only if it is aborted, unfinished, infrastructure-invalid, dirty, or holds a failed call with no
  successful retry. Never replace a completed, clean, priced run, whatever it shows. A replacement passes
  `--rerun-cause "WHAT WENT WRONG"` to the wrapper, which asks for it.
- After fresh run 1, compare its cost with the stop rule before run 2. The fresh world's call count is first known
  from the wrapper's bound.

**If it goes wrong:**
- **An aborted or infrastructure-invalid run:** commit its checkpoint, because aborted runs write one. Wait until the
  cause has cleared, then run again with `--rerun-cause`.
- **A WSL crash or guard kill:** see "After a crash".
- **A dirty run:** something wrote into `$CO`. Write nothing there.

### After a crash

A WSL crash or a guard kill leaves the run unfinished. Before anything else:

1. `git -C $CO status --short` must be empty, and `git -C $CO rev-parse HEAD` must be the freeze.
2. `same_runs $REL/out-frozen` (or `out-fresh`, or `out-rehearsal`) must say the index and folders agree.
3. Leave the killed run's folder and its `started` entry as they are. It has no checkpoint. It is replaced as never
   finished and counted from its log. Its row gives its Console spend, with Harness USD `none`.

**If the index is missing, empty, not JSON, or `same_runs` reports a mismatch:**
- Never write an index by hand, and never start another run into that folder: the harness would write a new index
  that drops the earlier runs.
- **Restore the latest snapshot whose runs cover every folder:**
  `cp $REL/index-snapshots/<that snapshot> OUT/index.json`, then `same_runs OUT` again.
  - The snapshot is the exact index the harness wrote at that run's start, so the killed run is listed as
    `started`.
  - If the crash hit the end-of-run write, the run may have a manifest saying completed. It is still replaced as
    never finished. Say so in its row.
- **A leftover `index.json.tmp`** (a crash during a write) stays in `OUT`. The copy step copies only the index, `sets/`
  and the listed run folders, so it is not committed. Note it in the log in the form `copy_as_is` prints,
  `` - Left out: `index.json.tmp`, SHA-256 `HASH` ``, with the hash from `sha256sum`.
- **A run folder that is empty** (a crash between creating the folder and writing its index entry; the index is
  written before any call) made no call. Remove it with `rmdir`, which removes only an empty folder, and note it in
  the log under that world's table, not as a run row.
- **If no snapshot covers the folders** (`DEC-W2-10-LOST-INDEX`), on the frozen or fresh world, the attempt is
  published as it is, not repaired:
  - Start no other run into that folder, and none on that world. Its result will be NOT ELIGIBLE.
  - In step 6, copy that world with `copy_as_is $REL/out-WORLD WORLD` instead of the copy step. It copies every run
    folder and `sets/` byte for byte, and `index.json` only if it is JSON. Then it lists and verifies them.
  - **What stays out:** an index that is not JSON stays in `$REL` byte for byte, and so does any `index.json.tmp`.
    The check refuses an index that is not JSON, and a `.tmp` file is not a file the release may add, so it would
    break the freeze for both worlds (owner, 13 Nov 2026). `copy_as_is` prints one
    `` - Left out: `PATH`, SHA-256 `HASH` `` line for each. Paste every one under that world's table in the log; G6
    requires the index's (`DEC-W2-10-ROUND3`). Keep the left-out bytes: the hash can be checked only against the
    owner's copy, and the README says so.
  - **The log:** each run folder gets a row with its Console spend. A run the index does not list has State,
    Re-run cause and Harness USD `none`.
  - **The check:** in step 7, `run_set` gives 64 zeros for a world with no index. The check says NOT ELIGIBLE and
    names each run folder the index does not list. The gate accepts that when it is published consistently (G6;
    tested).
- **If no snapshot covers the rehearsal's folders:** stop and talk. Nothing from that folder can be committed as
  rehearsal evidence without writing records by hand.

### 6. Copy the run output in (Claude, when asked)

```
cd $REPO && for w in frozen fresh; do [ -d $REL/out-$w ] || continue; same_runs $REL/out-$w && $PY -c "import sys; from pathlib import Path; from baseline_run.copy_step import copy_baseline; copy_baseline(sys.argv[1], Path('release', sys.argv[2]))" $REL/out-$w $w; done
git add release && git commit -m "Release 1: run output" && git push
```

The copy step copies byte for byte, writes `SHA256SUMS` in `baseline/`'s format, and verifies both sides. A world
whose index was lost is copied with `copy_as_is` instead ("After a crash"); `same_runs` would refuse it.

### 7. The check on both worlds, from a clean checkout (Claude or the owner)

The check is never run in the main checkout. Its output is written outside the repository, made twice and compared,
and only the agreed bytes are copied in (review round 1, finding 1).

```
cd $REPO && git status --short          # empty: the run output and every checkpoint are committed
git worktree add --detach $REL/check-checkout HEAD && cd $REL/check-checkout
FREEZE=$($PY -c "import json; print(json.load(open('release/generation.json'))['freeze_commit'])")
for n in 1 2; do
  $PY -m harness acceptance release/frozen $(run_set release/frozen) --release $FREEZE > $REL/check-frozen.$n.json
  $PY -m harness acceptance release/fresh $(run_set release/fresh) --release $FREEZE --fresh > $REL/check-fresh.$n.json
done
cmp $REL/check-frozen.1.json $REL/check-frozen.2.json && cmp $REL/check-fresh.1.json $REL/check-fresh.2.json && echo agreed
cd $REPO && cp $REL/check-frozen.1.json release/check-frozen.json && cp $REL/check-fresh.1.json release/check-fresh.json
git add release/check-frozen.json release/check-fresh.json && git commit -m "Release 1: check outputs" && git push
git worktree remove $REL/check-checkout
```

- `run_set` gives 64 zeros when there is no `release/fresh` folder ("No fresh world").
- Exit codes 0, 3 (the qualified pass) and 1 are all results.
- The committed output stays what the check gives at the publish commit, because it never names `HEAD` and later
  commits change only release files. G5 checks it.
- **If it goes wrong:**
  - **The two outputs differ:** stop and talk. The check is meant to be deterministic.
  - **NOT ELIGIBLE for a bookkeeping reason** (a checkpoint not committed, a copy mismatch): fix the bookkeeping in
    an allowed file, commit and push, and run this step again from a new checkout.
  - **Any other result is the result.**

### 8 and 9. Sign-off, the publish commit and its tag (owner)

The publish commit always changes the release log, so it is never empty (review round 1, finding 2). It writes:
- the Results rows, copied from the two committed check outputs;
- the running total;
- the sign-off row, only if `release/check-frozen.json` is the qualified pass. Its Console USD covers the priced runs
  only, and a killed run's spend stays in its own row (`DEC-W2-10-CHOICES`).

```
cd $REPO && git add docs/release-log.md
git diff --cached --quiet && echo "STOP: nothing staged; the Results rows and running total are not written"
git commit -m "Release 1: publish" && git tag -a release-1 -m "Release 1"
.venv/bin/python -m pytest tests/w2_08_release_protocol/test_signoff.py tests/w2_10_release_runs/test_published.py -q -p no:cacheprovider
git push origin main release-1          # only if both passed
```

- **If a test fails before the push:** delete the local tag (`git tag -d release-1`), fix the allowed file, then
  commit and tag again. After the push, a tag is never moved.
- **After the push:** the Genesis gates, review round 4, the approval and completion. Revoke both keys.

### No fresh world

If `fresh-world` prints `no fresh world: all 10 tries were rejected`, that is the published fresh-world result:
1. Commit `release/generation.json` as in step 3. It lists all ten tries and `"accepted": null`.
2. Make no fresh-world runs, and do not create `$REL/out-fresh` or `release/fresh/`.
3. Steps 4 and 6 for the frozen world only.
4. In step 7, `run_set release/fresh` gives 64 zeros. The check replays the ten rejections and says NO FRESH WORLD,
   exit 1.
5. In the log:
   - the Fresh world table keeps its header with no rows, and the line "No fresh world: all ten tries were rejected";
   - its Results row is `| fresh | `00000000` | `release/check-fresh.json` | NO FRESH WORLD |`.
6. The publish commit and tag as in step 9. The gate passes a NO FRESH WORLD that is published consistently (tested).

## The release log (`docs/release-log.md`)

It is written during the release, in the style of `docs/w2-02-attempts.md`. The gate parses the headings and tables
below, so their names and columns are fixed. Amounts are USD decimals. Spend USD is Console before minus Console
after (G6, G8).

```
# Release 1 log

Task W2-10-release-runs. Rules: DEC-W2-RELEASE-RULES, DEC-W2-08-CHOICES, DEC-W2-08-CHECKPOINTS, DEC-W2-10-CHOICES,
DEC-W2-10-STOPS, DEC-W2-10-LOST-INDEX, DEC-W2-10-ROUND3.

- Freeze commit: `<the 40-hex freeze commit>`, tag `release-1-freeze`
- Starting point: wave-2 spend USD 0.95 (docs/w2-02-attempts.md); Console balance USD 4.56 (owner, 2 Nov 2026)
- Keys: w2-10-rehearsal (rehearsal), w2-10-release (release runs); both revoked after the publish
- Stop rules: a run over USD 0.30, W2-10 over USD 2.00, or the wrapper's refusal checkpoint stops the release before
  the next run

## Rehearsal
| Date | Run ID | Agent commit | Run set | State | Key figures | Harness USD | Console before | Console after | Spend USD | Peak memory MB | Note |

## Freeze and push
(the `date -u` output and the peeled `git ls-remote` line in a code block, the tag's GitHub URL, and the owner's
statement that the tag was public before the fresh world was made)

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

How each column is filled:
- **Run ID:** in backticks.
- **State:** the index's, or `none` for a run the index does not list.
- **Valid or replaced** and **Reason:** the check output's `release.runs`. The Reason is empty for a valid run.
- **Re-run cause:** the index's, or `none`.
- **Checkpoint committed:** `yes` or `no`.
- **Harness USD:** the run's known cost from its index entry, rounded to the places written, or `none` for a run
  with no cost, such as a killed run or one the index does not list.
- **Agent commit** (rehearsal): the run's commit, in full or its first 7 or 12 characters.
- **Results:** exactly one row for each world, and no other row. Each has the run set's first eight characters in
  backticks, `` `release/check-<world>.json` ``, and the result exactly as the output gives it.

## The gate tests (`tests/w2_10_release_runs/`, the gate `tests`)

They read committed files and git only. They call no model and make no network request.

| File | What it holds |
|---|---|
| `release_gate.py` | The rules G1 to G12, as `problems(repo, reproduced)`, and `reproduce`, which runs the documented check command in a checkout with that checkout's own code. |
| `test_published.py` | The real release. A temporary clone with full history and the tags, checked out at `release-1`, so commits after the publish cannot break it (`DEC-W2-10-CHOICES`). The check is reproduced there on both worlds, and every rule is applied. It is xfail (strict) until the tag `release-1` exists. |
| `test_quick.py` | The quick checks, in the gate: the dry run's switch (in a fresh test process without `W2_10_DRY_RUN=1`, every dry-run test is skipped with its reason), the items-file rule of G12, the documented `copy_as_is` with the "Left out" rule of G6, and that every dry-run case names a rule. They build no release and take about a second. |
| `test_dry_run.py`, `made_up.py`, `conftest.py` | The dry run on made-up releases (below), reusing W2-08's test candidate agent and helpers (`tests/w2_08_release_protocol/release_common.py`) and its test generator. One test-only behaviour is added: model refusals. A session fixture checks that nothing is written in the repository. It runs only with `W2_10_DRY_RUN=1`, by hand just before the freeze, and its output is committed as evidence (step 2, `DEC-W2-10-ROUND3`). |

**The rules:**

| | Check | Read from |
|---|---|---|
| G1 | **The freeze commit exists.** It is read from `release/generation.json`, not from a tag name (`DEC-W2-10-STOPS`). It must be a commit before the publish commit, and both check outputs and the log's freeze line must name it. | the record, git, the outputs, the log |
| G2 | **A broken freeze is reported, not hidden.** If `release.freeze_problems` finds any change the freeze forbids, both published results must be NOT ELIGIBLE and name each problem (`DEC-W2-10-STOPS`). | git history, the outputs |
| G3 | **The seed is the function's:** every try's seed equals `release.fresh_seed(freeze, counter)`, with counters running 0, 1, … with no gap. | the record |
| G4 | **One accepted generation:** the fresh-world output shows the committed record equal to the check's own replay. Ten rejections with NO FRESH WORLD pass. | the fresh output |
| G5 | **The committed check output is what the check gives:** byte-identical to the documented command run at the publish commit. | the reproduced outputs |
| G6 | **Every run is in the log, within five per world.** The log rows name every run of the index and every run folder, at most five. If the index and the run folders do not name the same runs (an index lost in a crash), that world must be published as NOT ELIGIBLE (`DEC-W2-10-LOST-INDEX`). The runs are of the published run set, and a NO FRESH WORLD has no fresh runs and the zero run set. Each row's state, re-run cause and Harness USD are the index's (`none` for a run it does not list). Its valid or replaced and reason are the check's, a valid run's Reason being empty. Its checkpoint cell is right, and its Spend USD is the Console difference. **Left out:** every `` - Left out: `PATH`, SHA-256 `HASH` `` line in a world's section is of that form, for `index.json` or `index.json.tmp`, once, and a world committed with run folders and no `index.json` has the index's line (`DEC-W2-10-ROUND3`). | the log, `release/<world>`, the outputs, the tree |
| G7 | **Order in the history:** no release-world checkpoint at or before the freeze. `release/generation.json` added after the freeze, in an ancestor of every commit that adds a fresh-world checkpoint. | git history |
| G8 | **A completed rehearsal of the frozen agent on the practice world came first.** Nothing is read under `rehearsal/` while it holds a link or a non-regular file, on disk or at the freeze or the publish commit. `rehearsal/` and its `SHA256SUMS` are committed by the freeze. The rows, index and folders name the same runs, each row's State and Run set are its index's and its manifest's (review round 3, R3-3), and each finished run's log verifies against a checkpoint the freeze holds. At least one rehearsal is completed, clean, not infrastructure-invalid and on the practice world (`e2cbcb69…`). It was made at a commit before the freeze from which only `tests/w2_10_release_runs/`, `docs/`, `.genesis/`, `audit/checkpoints/` and `rehearsal/` changed. **Its files hold together as one run:** every file a completed run writes is there, with its set report; the run ID, run set, run-set inputs and index entry agree; the prompt and rule-code hashes bind; the items file is the manifest's; the report and the set report are the manifest's; and the log starts with the manifest's run and ends with those items. **Its agent:** every run-set input but commit and world equals what the freeze's own `config/run-triage.json` gives with the freeze's own code, and the release runs' inputs, so it is bound with no release run too. | `rehearsal/`, the log, git, the freeze's configuration |
| G9 | **Published and consistent:** the tag `release-1` is the commit checked, both outputs are committed, the Results table has exactly one row for each world that equals its output and no other row, and the running total is 0.95 plus every Spend USD, by section. | the log, the outputs, git |
| G10 | **The sign-off:** `release.signoff_problem` is None, as in W2-08's sign-off test, here at the tag. | the log, the outputs, the index |
| G11 | **Push evidence:** the "Freeze and push" section holds the peeled line `<freeze>` TAB `refs/tags/<tag>^{}`, and that tag names the freeze commit. It cannot show the order (Limits). | the log, git |
| G12 | **The stop rules:** every run, rehearsal included, is ordered by its run ID. No run may come after one that cost over USD 0.30 (the larger of its harness cost and its Spend USD), or whose refusals passed 2% (from its items, as the wrapper counts them), or by which the spend passed USD 2.00. **Items files:** every whole record counts, as the wrapper's `splitlines()` counts it. A run whose manifest does not say completed may end without its newline, a crash while the harness wrote the file: that last line counts if it is a whole item record (review round 3, R3-1), and is not counted only if it is cut off. Any other line that is not an item record is a problem, since the refusal share cannot be read (review round 2, finding N2). | the log, the run output |

None of these asks whether the release passed. A published FAIL, NOT ELIGIBLE (a broken freeze included) or NO FRESH
WORLD passes the gate when it is consistent.

**The dry run** (`test_dry_run.py`, by hand with `W2_10_DRY_RUN=1`). Each made-up release is built the way the steps above build the real one:
1. a shared clone of the repository, with the test candidate's settings committed as its `config/run-triage.json`,
   so the freeze configures the made-up release candidate;
2. a rehearsal on the practice world, made from seed 20261027 by the repository's own generator into a temporary
   folder, and its evidence committed through the copy step. The clone fetches no tags, and first removes the
   published release's files (`release/`, `rehearsal/`, `audit/checkpoints/`, `docs/release-log.md`) in a commit of
   its own, so the made-up release starts from a clean tree with none of the real release in it (17 and 18 Nov
   2026);
3. a freeze commit and annotated tag;
4. `make_fresh_world` and the generation record;
5. runs from a separate worktree at the freeze, made by W2-08's test candidate with the stub provider;
6. checkpoints, the copy step, both check outputs made before either is written, the log, and the publish commit
   and tag.

The tests:
- **One whole release** (three valid frozen runs beside one killed and one aborted, three valid fresh runs) passes
  every rule, and its committed outputs equal the documented command's.
- **Twenty-one breaks** of that release, each made in a commit on top of it, each fail their named rule:
  - a run missing from the log, and a row for a run that is not there (G6);
  - a replaced run called valid, a valid run with a reason, a wrong harness amount, and Spend USD that is not the
    Console difference (G6);
  - a wrong running total, a wrong result, a Results row for a world that is not a release world, and two Results
    rows for one world (G9);
  - the tag-object line in place of the peeled line (G11);
  - an edited check output (G5);
  - a seed not from the function (G3);
  - a code change after the freeze published without NOT ELIGIBLE (G2);
  - the publish tag not on the commit checked (G9);
  - a run over USD 0.30 with a run after it, spend over USD 2.00 with a run after it, a line of an items file
    that is not an item record, and a killed run's last item, a refusal, whole without its newline, with runs after
    it (G12);
  - a rehearsal row whose State, and one whose Run set, is not its index's (G8).
- **Eleven wrong releases,** each built with one fault, each fail their named rule:
  - rehearsal evidence committed after the freeze, a rehearsal on the frozen world, code changed between the
    rehearsal and the freeze, and only an aborted rehearsal (G8);
  - with no release run at all, so the rehearsal is bound by the freeze's configuration alone (G8):
    - a rehearsal with other run settings;
    - a required rehearsal file deleted, with `SHA256SUMS` made again to match;
    - a rehearsal manifest field falsified to the configured setting, with `SHA256SUMS` made again to match;
    - a rehearsal file committed as a symbolic link to the same bytes;
  - fresh-world checkpoints committed before the generation record (G7);
  - refusals over 2% with a run after them (G12);
  - six runs on one world (G6).

  A control built the same short way shows that none of those rules fails on a right release, so each variant's
  problem is its own.
- **These pass, each published consistently,** with both outputs reproduced by the documented command (G5):
  - a published FAIL (an unsafe fresh-world answer); the same release with an edited check output then fails G5;
  - a published NO FRESH WORLD (a test generator rejecting all ten tries);
  - a broken freeze published as NOT ELIGIBLE;
  - a frozen world whose index a crash cut off, with a run whose items file a crash cut mid-line, copied in with the
    documented `copy_as_is` and published as NOT ELIGIBLE (`DEC-W2-10-LOST-INDEX`, review round 2, finding N2); the
    same release without the index's "Left out" line in the log then fails G6;
  - a second freeze tagged `release-1-freeze-2`.

## Gate timing

Genesis stops a gate at 120 s; the aim is under 100 s.

After review round 2 the suite is 36 passed and 1 xfailed (the real release). Its first full run with the round-2
tests took 118 s, over the aim. Three things were cut, and no check was dropped:
- **Short builds:** the wrong releases with no fresh-world run and no check output no longer generate a fresh world
  (about 2 s each), since they check none of G3, G4 and G5. Their generation record only names the freeze. The four
  G8 cases that need no release run make none, and skip the worktree.
- **One build for two results:** NO FRESH WORLD and the lost index share one build. The FAIL release has one
  frozen-world run, not three.
- The gate also remembers the refusal share of each items file by its SHA-256, since the dry run asks about each one
  many times.

The slowest parts now: the whole base release, about 18 s; the FAIL release with both outputs reproduced, 12.5 s;
the broken freeze, 10.3 s; the NO FRESH WORLD and lost-index build, 6.4 s; each wrong release, at most 4.9 s.

Three runs of the gate command through `tools/timed_run.sh` on 13 Nov 2026, charger in and fixed benchmark checked,
one at a time. Time is pytest's own. Wall is the whole `timed_run.sh` command, its checks included:

| Run | Result | Time | Wall | Benchmark | Memory in use, before and peak |
|---|---|---|---|---|---|
| 1 | 36 passed, 1 xfailed | 95.27 s | 105.3 s | 0.745 s | 1,586 MB, 1,811 MB |
| 2 | 36 passed, 1 xfailed | 87.05 s | 94.3 s | 0.745 s | 1,595 MB, 1,721 MB |
| 3 | 36 passed, 1 xfailed | 91.73 s | 101.9 s | 0.755 s | 1,505 MB, 1,700 MB |

The machine was slower that day than on 2 Nov, with other heavy programs open: the unchanged W2-08 suite took
119.61 s, against 77.05 s in review round 2.

**Re-timed on 17 Nov 2026,** with other heavy programs closed. VS Code stayed open, since the project runs in it.
The charger was in and the fixed benchmark checked, through `tools/timed_run.sh`, one at a time, with
`MEMORY_GUARD_MAX_SECONDS=200` so that the guard's 110-second default could not stop a slow gate:

| Gate | Run | Result | Time | Wall | Benchmark | Memory in use, before and peak |
|---|---|---|---|---|---|---|
| `tests` (W2-10) | 1 | 36 passed, 1 xfailed | 81.96 s | 83.5 s | 0.848 s | 1,586 MB, 1,669 MB |
| `tests` (W2-10) | 2 | 36 passed, 1 xfailed | 80.56 s | 81.7 s | 0.800 s | 1,510 MB, 1,629 MB |
| `tests` (W2-10) | 3 | 36 passed, 1 xfailed | 85.10 s | 86.4 s | 0.797 s | 1,476 MB, 1,599 MB |
| `w2-08` | 1 | 129 passed, 1 skipped, 1 xfailed | 74.07 s | 75.3 s | 0.791 s | 1,451 MB, 1,617 MB |
| `w2-01` | 1 | 68 passed | 69.47 s | 70.7 s | 0.790 s | 1,446 MB, 1,682 MB |
| `w2-02` | 1 | 68 passed | 6.23 s | 7.6 s | 0.822 s | 1,442 MB, 1,553 MB |
| `secrets` | 1 | passed | | 0.3 s | | |

**The real-release test, estimated.** After the publish, `test_published.py` stops being xfailed and does its own
work: a clone, the check on both worlds, and every rule. That was timed on a made-up release of the largest real
size: five runs on each world (three valid, one killed, one aborted) and a rehearsal. The same steps ran on it with
the documented command, twice, through `tools/timed_run.sh`:

| Part | Try 1 | Try 2 |
|---|---|---|
| clone and checkout of the tag | 0.29 s | 0.30 s |
| the check, frozen world | 1.52 s | 1.52 s |
| the check, fresh world (with the generation replay) | 3.42 s | 3.49 s |
| every rule (`problems`) | 0.49 s | 0.45 s |
| **the real-release test's own work** | **5.73 s** | **5.76 s** |

The gate found no problem on that release. Real runs hold the same items as made-up ones, but a real model's logs
may be somewhat larger, so take about 6 s.

**Then the dry run stayed in the gate:** the slowest W2-10 run, 85.10 s, plus about 6 s was about 91 s, under the
100-second aim. Review round 3 measured 93.22 s wall for the same suite, about 99 s with the real-release test, and
the 13 Nov wall of 105.3 s would give about 111 s.

**Review round 3 (R3-4, `DEC-W2-10-ROUND3`): the dry run moved behind a by-hand switch.** It runs only with
`W2_10_DRY_RUN=1`, once just before the freeze, and its output is committed as evidence (step 2). The gate `tests`
keeps the real-release test and the quick checks (`test_quick.py`). Timed on 17 Nov 2026 after the change, charger in
and benchmark checked, through `tools/timed_run.sh` with `MEMORY_GUARD_MAX_SECONDS=200`, one at a time:

| Run | Command | Result | Time | Wall | Benchmark | Memory in use, before and peak |
|---|---|---|---|---|---|---|
| 1 | the gate `tests` | 4 passed, 39 skipped, 1 xfailed | 0.38 s | 1.6 s | 0.794 s | 1,402 MB, 1,447 MB |
| 2 | the gate `tests` | 4 passed, 39 skipped, 1 xfailed | 0.71 s | 1.9 s | 0.797 s | 1,436 MB, 1,469 MB |
| 3 | the gate `tests` | 4 passed, 39 skipped, 1 xfailed | 0.42 s | 1.6 s | 0.798 s | 1,427 MB, 1,463 MB |
| by hand | `W2_10_DRY_RUN=1`, the dry run included | 43 passed, 1 xfailed | 81.73 s | 83.1 s | 0.798 s | 1,409 MB, 1,615 MB |

The 39 skipped are the dry run's tests, each with its reason. After the publish, the real-release test stops being
xfailed and does its own work, estimated above at about 6 s, so the gate should take about 7 to 8 s then: far under
the aim, and no longer near it on a slower day. That time is measured three times after the publish. The by-hand dry
run, about 82 s, stays under Genesis's 120-second stop for a gate, though it is no longer a gate.

## Limits

These are the W2-08 limits, still in force:
- **Push before generation:** no code can prove the freeze tag was public before the fresh world was made. The
  release log holds the evidence and the owner's statement (G11 checks only that it is there).
- **The seed can be chosen** through the freeze commit by trying freezes privately. The README discloses this.
- **The order of runs:** the gate orders runs by the start time in their run IDs, and commits by the history. A
  checkpoint shows when a run was committed, not when it ran.
- **Unrecorded runs:** a run left out of the output, the index, the checkpoints and the log alike is invisible, and
  so is its spend to every rule but the Console's.
- **The Console:** the gate checks the log's arithmetic, the sign-off rule and the stop rules on the figures written,
  not the Console itself. Those are the owner's. A killed run's cost rests on the Console alone.
- **Publication:** the gate checks the commit and the tag, not that they were pushed. The push is the owner's step.
- **The rehearsal's agent:** G8 compares the rehearsal's run-set inputs, but commit and world, with what the freeze's
  own `config/run-triage.json` gives, worked out with the freeze's code, and with every release run's. It binds the
  agent and settings the freeze configures, not that the owner ran that agent: a run's files written by hand to
  agree with each other and with a checkpoint would pass, as the W2-08 limits say of any committed run.
- **The rehearsal's figures:** the practice world is not committed. So G8 cannot work out the report's figures or
  the log's input hashes again. It checks that the files agree with each other and with the committed checkpoint.
- **A lost index:** a world published as it is under `DEC-W2-10-LOST-INDEX` shows its runs only from their folders
  and logs. The bytes left out stay outside git with the owner, so the "Left out" hashes in the log can be checked
  only against the owner's copy (`DEC-W2-10-ROUND3`); the README says so. A rehearsal whose index is lost is not
  covered: that is "stop and talk".
- **The dry run is by hand:** the gate itself does not try its rules on made-up releases. That is shown by the
  by-hand run committed just before the freeze, made with the gate code the freeze holds; the quick checks in the
  gate show the dry run is skipped without its switch, not that it would still pass.
- **The dry run's agent:** the made-up runs use W2-08's model-free test candidate, so the dry run shows the rules,
  not the triage agent. The real release's agent is bound by its prompt and rule-code hashes (section 1 of the
  pre-flight, and G8).
- **No real model:** nothing here shows how the real model or provider will behave.

## Open points, settled (`DEC-W2-10-STOPS`, 2 Nov 2026)

| Point | Settled |
|---|---|
| O1. A freeze problem cannot be undone, so a gate that failed on it could never be passed; a second freeze changes the tag names | A broken freeze is reported, not failed: the check says NOT ELIGIBLE, that is published, and the gate checks that it is consistent (G2). The gate reads the freeze commit from the generation record (G1). |
| O2. The wrapper's benchmark limit of 0.82 s may refuse on a slow day | It stays as it is: a refusal starts nothing and costs nothing. |
| O3. The wrapper's refusal checkpoint is not among the stop rules | It is now a stop rule (G12). |
