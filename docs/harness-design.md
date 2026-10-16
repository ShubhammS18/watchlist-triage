# Harness design for T06-harness

Status: written as the design at the T06 pre-flight on 2026-10-12 and kept up to date while building. The
harness (`harness/`) and its tests (`tests/t06_harness/`) are built; T06 is in independent review. Results named
below were run as stated; anything else describes the code as built.

Requirements: FR-20, FR-22, FR-24, NFR-1, NFR-3, NFR-6, AC-7, AC-24, AC-25. Decision records: 47
`DEC-T06-*` records in Genesis, 20 of them active and 27 superseded, kept as history. The eighteen original
records, listed below, all owner decisions of 2026-10-12 and 2026-10-13, were recorded on 2026-10-13. Sixteen were
recorded on 2026-10-14: fifteen that supersede earlier records, from "Decision changes during the build", and one
new record, `DEC-T06-FIGURES`, since superseded by `DEC-T06-FIGURES-2`. Eight were recorded on 2026-10-15:
`DEC-T06-TWINS-2`, `DEC-T06-GATE-TIME-4`, `DEC-T06-MANIFEST-4`, `DEC-T06-MANIFEST-5`, `DEC-T06-MANIFEST-6`,
`DEC-T06-GATE-TIME-5`, `DEC-T06-MANIFEST-7` and `DEC-T06-MANIFEST-8`. Five were recorded on 2026-10-16:
`DEC-T06-GATE-TIME-6`, `DEC-T06-MANIFEST-9`, `DEC-T06-GATE-TIME-7`, `DEC-T06-PARALLEL-3` and
`DEC-T06-REVIEW-R12`, the last a new record of the independent review.

## What it is

`harness` is the evaluation harness. It shows an agent every alert of a world in three framings, several times
over, and scores what comes back against the hidden truth. It writes a manifest, the per-item outputs and a
report for every run-and-score run, and an index of every run it ever started.

It has two steps that are kept apart:

- **The run step** loads the alerts and the control twins, frames them, hands each one to the agent, and writes
  the outputs and the manifest. It never imports `worldgen.truth` and never opens `data/world/hidden/`.
- **The score step** reads the outputs of a finished run and the hidden truth, and computes every figure of the
  Metrics section of `SPEC.md`.

The harness is provider-neutral. It holds no provider code, no SDK and no key. It has only ever been planned
against a test-only fake model. The real provider adapter is built in T07 (`DEC-T06-NO-ADAPTER`).

## Requirements covered, and not

Covered by T06:

| Requirement | What T06 does for it |
|---|---|
| FR-20 | Every Metrics-section figure, by run, by framing and by primary family |
| FR-22 | Modelled review time for manual clearing and for agent-assisted review, from a parameter file shown with every result |
| FR-24 | The always-escalate and always-close reference agents, scored by the same code as any agent |
| NFR-1 | Missed true matches are a count of their own and are never part of a rate |
| NFR-3 | The run manifest, at least 3 repeated runs, and the spread across runs |
| NFR-6 | Cost from reported token counts and a dated price table; latency per alert-framing item including retries |
| AC-7 | A check that always-close fails AC-1 and always-escalate fails AC-6 |
| AC-24 | A report per run with every figure, the manifest and the modelled-time parameters. An evaluation run is `run-and-score`; a bare `run` has no report, by design |
| AC-25 | The mechanism only: the parameter file is read from a committed path and its hash and the commit go into the manifest. The commit before the first baseline run is T07's |

Touched by T06 without owning them:

- **FR-8 and AC-13.** Not T06's. The model-fault half is T05, the pipeline half is wave 2. T06 owns only how a
  SYSTEM_FAILURE is scored: never as CLOSE, always as ESCALATE, with its share reported separately. The harness
  also gives `recommend` the sink that receives T05's log records.
- **FR-9.** T04's. T06 adds two things the T04 and T05 documents hand to it: the agent gets one harness-selected
  bundle per call, and a run-time test that the agent opens no file. See `DEC-T06-NO-FILES` for what is claimed.
- **AC-2.** T05's. The harness re-checks every CLOSE of a run and reports the count (`DEC-T06-CITATIONS`).
- **AC-12.** Wave 2. T06 computes the injection divergence figure that AC-12 will be judged on.

Not covered: every target under AC-16, the real provider, real prices, real modelled-time values, the audit log,
evaluation and operational modes, and human review.

## Words

- **Item.** One alert in one framing in one run. The spec calls it an alert-framing item. Its ID is the alert ID
  and the framing, for example `ALT-0001/2`.
- **Main item.** An item of one of the 600 alerts. Every rate and latency figure, and the cost headline, is over
  main items; the second cost figure, the total cost over all items, includes the twin items too.
- **Twin item.** An item of one of the 15 control twins. Twin items feed the injection measure and the second cost
  figure, the total cost over all items; the AC-2 re-check of their closes and their own calls and cost are shown
  apart. They are outside every accuracy and latency figure and outside the cost headline.
- **Run.** One pass over all 615 alerts in all three framings: 1,800 main items and 45 twin items.
- **Run set.** The runs that share the same run-set inputs: the agent name, the commit, the world hash, the
  prompt hash, the model configuration, the worker count, the pacer setting, the infrastructure-invalid
  threshold, the price table and the modelled-time parameter file. Changing any one of them starts a new run set. This entry is the
  one place the list lives; every other mention of run-set inputs in this document points here.
- **Attempt.** One model call. An item has one attempt, or more when a timeout or provider error is retried.
- **Completed run.** A run whose every item returned a result and whose outputs were written.
- **Aborted run.** A run the harness stopped. It is never scored.
- **Transient failure.** An item whose result is a failure of kind `timeout` or `provider_error`: the two errors
  T05 retries, still failing on the last attempt allowed.
- **Infrastructure-invalid run.** A completed run whose share of transient failures is above the threshold. It
  is scored and published, and it does not count toward the three runs or the spread.
- **Dirty run.** A run made on a dirty tree, as `DEC-T06-MANIFEST` defines it. The commit cannot identify its
  code.
- **Valid run.** A run that is completed, not infrastructure-invalid and not dirty. Only valid runs count toward
  the three runs and the spread.
- **Real run.** A run whose configured provider is anything other than the stub.
- **Hand-off.** The moment the harness calls the agent for one item.

## How a run flows

1. **Start.** The harness reads the run configuration: the model configuration, the worker count, the pacer
   setting, the infrastructure-invalid threshold, the price table and the modelled-time parameter file. A real
   run without a parameter file is refused.
2. **World check, agent side.** It checks that the manifest's `world_hash` equals the hash of the manifest's own
   file list, and that every file outside `hidden/` matches its listed hash. A mismatch aborts the run.
3. **Load.** The 600 alerts come from `worldgen.loader`, the 15 twins from `worldgen.harness_twins`.
4. **Frame.** Each alert and twin is framed three ways with `framings.frame`.
5. **Hand-off.** With one worker the main thread makes the calls itself, one after another, with no pool: the
   sequential path. With more, it gives items to a pool of that many worker threads, and hands an item off
   only when a worker is free. If the pacer is on, it waits before each hand-off so that hand-offs are evenly
   spaced, 60 seconds divided by the setting apart. Each call is for one item, with its own sink list and its
   own token wrapper around the shared model. For the baseline agent the call is
   `baseline_agent.recommend.recommend`, which starts one guarded child process for that one bundle. The time
   an item waits for a worker or for the pacer is recorded as its queue time and is no part of its wall-clock
   time.
6. **Collect.** The main thread collects each result with the item's wall-clock time, the token counts of every
   attempt and the log records from the sink. Nothing is shared between workers.
7. **Write.** When every item is back, the items are sorted by item ID and written to `items.jsonl`. The manifest
   is written beside it with the hash of that file. The run is added to the run-set index.
8. **Score.** The score step checks the `hidden/` files against the manifest, loads the truth through
   `worldgen.truth`, sorts the items again, computes the figures and writes the report.

**An evaluation run in the sense of AC-24 is `python -m harness run-and-score CONFIG OUT`:** steps 1 to 7, then
step 8 for `OUT` against the run's own world, in that order. The scoring code is loaded only after the run has
returned, so the run step still never imports `worldgen.truth`; a test shows it. A bare `python -m harness run`
stops after step 7 and **has no report, by design**: its report is written later by `python -m harness score`
or by `run-and-score`.

An exception out of the agent call or the sink, or a world-hash mismatch, is a harness fault: once it has been
collected no new item is handed off, the run is marked aborted and it is never scored (`DEC-T06-FAULTS`). See
"Limits" for the items that may still run.

**The hidden-file check on its own.** The check of step 8, that the four `hidden/` files match the hashes in the
world manifest, is also a small command of its own. It hashes the files' bytes, prints the result and does
nothing else: it does not import `worldgen.truth` and it starts no run. It is run by hand before any paid run,
so a changed hidden file is found before the calls are made and not only at scoring. The run step itself still
never opens `hidden/`.

### Files of one run

All output of one invocation goes under one run-output folder. In T06 that folder is a required argument with
no default, and a path inside the repository is refused. So every run of T06, the tests and the 5,535-call run
alike, writes outside the repository, such as under `/tmp`, and `runs/` stays empty throughout T06. T07 adds
the default, `runs/` at the repository root, and lifts the refusal, because that is where the baseline is
written and committed. The paths in the table below show that later layout.

| File | Holds |
|---|---|
| `runs/index.json` | every run ever started: its ID, run set, state (started, completed or aborted; infrastructure-invalid is a separate mark on a completed run, not a state), abort or re-run cause, whether its set is superseded, and its calls and known cost. An aborted run's calls and known cost are recorded too, so the total spent across all attempts can be added up |
| `runs/<run id>/manifest.json` | the manifest, below |
| `runs/<run id>/items.jsonl` | one line per item, sorted by item ID: the result, wall-clock time, queue time, the evidence IDs that were sent, token counts per attempt. The `reason` text may hold synthetic customer values (FR-15) |
| `runs/<run id>/report.json` | the figures, the manifest and the modelled-time parameters. Besides the manifest it holds the figures (numbers and identifiers), fixed notes the harness writes to explain them, and cost statements such as "at least X USD": no reason text from the agent and no evidence values |

T06 commits no run output.

### The manifest

The NFR-3 list: world hash, generator version, rubric version, the model identifier asked for and every
provider-reported `model_id` seen with its count, the prompt text and its hash, the decoding parameters, the retry
policy (retries, `timeout_s`, which errors are retried, no backoff), the review policies used, the modelled-time
parameters, and the per-framing outputs by the hash of `items.jsonl`.

Added by `DEC-T06-MANIFEST`: the git commit and a dirty flag, the configuration hash, the framing code hash, the
Python version, the worker count, the pacer setting, the infrastructure-invalid threshold with the run's share
of transient failures and whether the run is marked, start and end times, the run's duration and total queue time, item counts (main, twin, total), the
agent name, the aborted flag with its reason, the hashes of the price-table and modelled-time files, the dated
price table itself, and the re-run cause if there is one.

Never recorded: any environment variable, in the manifest or in any report (`DEC-T06-NO-ENV`).

## The figures

All figures are computed over main items, as the Metrics section defines them, except the second cost figure,
the total cost over all items, which includes the twins. The spec's base population is
the alert-framing item, "one alert in one framing in one run", so the headline of a run set is pooled over its
valid runs, and FR-20 then breaks it down by run, by framing and by primary family. The breakdowns are three
separate ones: overall, by framing, and by family, not framing by family. Where the spec leaves a choice, this
is what the harness does:

- **The pooled headline.** For a run set, every figure is given summed over its valid runs: numerators,
  denominators and counts are sums over those runs, and the report labels them so. Each run's own value stands
  beside it. Pooled latency is the median and 95th percentile over all main items of the valid runs.
- **A rate is stored as a numerator and a denominator,** never as a float. A rate with nothing to divide by is
  flagged as not applicable.
- **Over-escalation and its failure share.** The failure count is given over the CLEAR_FALSE_POSITIVE items, so
  that genuine and failure escalations add up to the over-escalation rate, and also over the escalations alone.
  The spec says "the failure share" without naming what it is a share of.

- **A SYSTEM_FAILURE** is an ESCALATE in every figure and is never a CLOSE. It is left out of the citation rates,
  as the spec says. Its count is shown by failure kind.
- **Citation existence rate** is worked out by the harness from the cited IDs and the IDs it sent. It is shown
  with raw counts beside it: results marked `citation_invalid` by the agent, failures of kind
  `missing_citations` and `invalid_citation`, and the results where the harness and the agent's flag disagree,
  which is expected to be 0.
- **The AC-2 re-check** covers every CLOSE, on main and on twin items, shown separately.
- **Citation precision** uses the same population as citation accuracy: non-failure CLOSE recommendations on
  CLEAR_FALSE_POSITIVE main items. It counts the distinct IDs a result cites, so an ID cited twice counts once.
  The report says so beside the figure.
- **Verdict consistency** is given overall and by family. It has no per-framing value, because the framings are
  what it compares. Pooled, it is consistent alert-runs over all alert-runs, as the spec words it.
- **Injection divergence.** An alert is compared with its twin within the same framing and the same run, never
  across framings or runs: 45 pairs per run. A pair diverges when the verdicts differ, with a failure counted as ESCALATE, or
  when the cited IDs of the alert, minus the injected item's ID, are not the same set as the twin's. That count
  is the headline. It is split by cause, one cause per pair, taken in this order so that the split adds up to
  the headline: one side failed (transient for a timeout or provider error, model-caused for any other
  failure), the verdicts differ, the citations differ. It is also given by label.
- **Latency** is the harness's wall-clock time for one item, from hand-off until the checked result returns,
  retries included. Queue wait and pacer wait are left out. The agent's own `latency_s` is shown beside it as
  model-call time. Total run time is a separate figure.
- **Percentiles** are by nearest rank, the median included.
- **Spread.** Every figure in every breakdown cell is shown for each run, with the minimum and maximum across the
  valid runs of the run set. An infrastructure-invalid run's own figures are shown, outside the spread.
- **Results that cite an injected item.** A count, per run and framing, of non-failure results on injection
  alerts whose cited IDs include the injected item's own ID. It is reported for information. It carries no
  AC-12 judgement; that is wave 2.
- **Cost.** The spec says: "Cost per alert: the total model cost of a run divided by its number of
  alert-framing items." (`SPEC.md:136`). The headline is read as main cost over main items: a run's 1,800 main
  items, since the spec puts twins outside the 600 alerts. A second figure takes the words literally: the total
  cost of the run, twins included, over all its 1,845 items (`per_item_all_items`). Twin calls and twin cost are
  shown on their own lines, with a total. Cost per alert is also given by framing and by primary family, over
  main items, as FR-20 asks of every figure.
- **Modelled review time** is also given by framing, and by primary family. For a family, N and the count of
  alerts whose correct action is escalate are those of the family's own alerts.
- **Family figures.** TRUE_MATCH figures are grouped by primary family. Secondary memberships are listed
  separately and never added into a total. Figures for the other labels are grouped by the family the truth
  gives them, with one group for alerts that have none.

## The decisions

Each row says what was decided, why, what was given up and the limit that remains.

### `DEC-T06-NO-ADAPTER`: no provider code in T06

- **Decided.** T06 is provider-neutral. It fixes only the shapes it needs from any model: the token counts and
  `model_id` of `model_interface.Result`, the price table, and the pacer setting. The real adapter is built in
  T07 before the paid run, tested in `tests/t07_baseline` with fake responses. A T07 decision record links it to
  the real half of FR-16 and to NFR-3, NFR-4 and NFR-6. The plan is not reopened.
- **Why.** The adapter is built where it is first needed (T07), and the plan is not changed by untested Genesis
  commands.
- **Gave up.** A task of its own for the adapter, with its own gate and review.
- **Limit.** Nothing in T06 shows that a real provider works through the interface, reports token counts, or
  keeps to `timeout_s`. See "Conflicts found at the pre-flight" for what T07's plan text does not say.

### `DEC-T06-GATE-TIME`: what the gate runs

- **Decided.** The gate scores the full world, three framings and three runs, with agents called in the test
  process. The real child process is used on 36 items as built (one alert per fake outcome, in all framings; "about 30" at the pre-flight) and on every fault path it can
  reach. One test requires the in-process and the real-child results to be identical on those items, with
  timings removed. Mutation proofs rerun their guard files only. The target is under 45 seconds (superseded:
  see "Decision changes during the build"). Outside the
  gate, one full run set of 5,535 calls goes through the real child before the independent review, writing to
  a folder outside the repository, and its result is recorded in this document. It is a rehearsal on the
  uncommitted tree, dirty by design and not a baseline; see "Test plan".
- **Why.** Measured on 2026-10-12: one stubbed call through the real child takes 0.071 seconds, so one run of
  1,845 calls is about 131 seconds and three are about 6.5 minutes. Genesis kills the gate's test command after 120
  seconds by default.
- **Gave up.** The whole world through the real child on every gate run.
- **Limit.** The in-process path exists in the tests only. No setting lets a run skip the guarded child. The
  three failure kinds the parent builds (`child_timeout`, `child_crash`, `internal_error`) have no in-process
  form, so they are tested through the real child with no comparison. `truncated_evidence` cannot be produced
  through `recommend` at all, because `build_payload` always writes a correct item count; the harness tests score
  a hand-made result of that kind, and the fault itself stays covered by the T05 tests.

### `DEC-T06-NO-FILES`: the agent reads no files

- **Decided.** Three things. The T05 static check stays. A test-only wrapper module records every file-open
  event in the child after start-up, on the gate's real-child sample, with a positive control that must be
  caught. The run step never imports `worldgen.truth`, and a test shows that `hidden/` is not opened before all
  outputs of a run are written.
- **Why.** No reviewed T04 or T05 code is changed.
- **Gave up.** A refusing hook in `model_interface/child.py` on every real item.
- **Limit.** The claim is "tested on a sample, not enforced per item". The child can still read any file the
  user can read. An operating-system sandbox is wave 2.

### `DEC-T06-FAULTS`: harness faults, item failures and re-runs

- **Decided.** A harness fault aborts the run: it is marked aborted, never scored, and the count of aborted runs
  is published. The index records each aborted run's calls and known cost, so the total spent across all
  attempts is visible. Item failures are scored as the spec says. A run with a high failure share is published
  as it is, with the breakdown by kind. Any re-run records a written cause in its manifest; for an aborted run
  that is the abort reason. With the same run-set inputs (see "Words"), every valid run counts toward the three and the spread and
  none is dropped. A valid run is completed, not infrastructure-invalid and not dirty (see "Words"); the two
  exclusions are rules fixed before the run, in `DEC-T06-INFRA-INVALID` and `DEC-T06-MANIFEST`. With any run-set input changed a new run set starts and the old
  one stays listed as superseded with its cause. Only a run set with at least 3 valid runs can be a baseline.
- **Why.** Choosing which runs to keep after seeing them would be cherry-picking.
- **Gave up.** Continuing a run past a harness fault, and discarding a bad run.
- **Limit.** An aborted run's cost is an "at least" figure: calls still in flight when it stopped may have been
  billed without their token counts being seen.

### `DEC-T06-INFRA-INVALID`: runs spoiled by the infrastructure

- **Decided.** A completed run whose share of transient failures is above a threshold is marked
  infrastructure-invalid. It is scored, published and listed in the index like any other run, and it never
  counts toward the three runs or the spread. Transient means `timeout` and `provider_error`, as T05 classifies
  them. Failures the model causes, such as `malformed_output`, `missing_citations`, `invalid_citation` and
  `model_refusal`, always count and never make a run invalid. T06 builds the mechanism. The threshold is set in
  T07 before the paid run and is recorded in the manifest. The tests use a fixture value.
- **Why.** A provider outage can give a run that is all failures and has zero missed true matches. Counting it
  would put an outage into the baseline's spread; dropping it by hand would be cherry-picking. A rule fixed
  before the run is neither.
- **Gave up.** Counting every completed run, whatever happened to it.
- **Limit.** The share is taken over all items of the run, main and twin, and "above" means strictly greater;
  both accepted by the owner on 2026-10-12. `child_timeout` is not on the list, so a child killed
  at its wall-clock limit counts as an ordinary failure. A provider that fails by answering with rubbish instead
  of an error is counted as model-caused. A model that is simply too slow for `timeout_s` looks transient, so
  the rule can hide a real weakness of a model; the guards are that the run is
  still published, and that a model too slow on every run blocks any baseline. The
  threshold is one of the run-set inputs (see "Words"), so changing it starts a new run set. A model that is always too
  slow makes every run invalid, so no baseline can be published until `timeout_s` is changed; it is in the model configuration, a run-set input (see "Words"), so that is a new
  run set. Excluding a run makes the safety figures stricter, because its failures were all escalations, but it
  makes latency and cost look friendlier, because its slow and failed calls leave the spread. That is why an
  invalid run is published with all its figures.

### `DEC-T06-CITATIONS`: citation figures and AC-2

- **Decided.** The existence rate is the spec's, with the raw counts beside it. The harness checks every CLOSE
  again against the bundle it sent, without trusting the agent's flag, and reports "n of n". A bad CLOSE does not
  abort the run: it is scored as the CLOSE it is, counted as an AC-2 violation, and the acceptance check fails.
  It is never corrected. AC-2 stays T05's requirement.
- **Why.** T05 proves AC-2 in code; only the harness sees real outputs.
- **Gave up.** Adding AC-2 to a task through a plan reopen.
- **Limit.** By construction the existence rate is 1 minus the share of results marked `citation_invalid`,
  because a result with no citations is a failure and is left out. The spec tension stays with
  `DEC-T05-CITATIONS` for the wave-2 reopen. Nothing checks that a cited item supports the reason.

### `DEC-T06-LATENCY`: what latency means

- **Decided.** As under "The figures".
- **Why.** One definition for every outcome and for the reference agents. The agent's `latency_s` mixes two
  clocks: the child's for most results and the parent's for failures the parent builds.
- **Gave up.** A headline figure free of the child's start-up time, about 70 milliseconds per call here.
- **Limit.** With several workers, a provider's rate limits and this machine's load are inside the figure.

### `DEC-T06-SPREAD`: spread and percentiles

- **Decided.** As under "The figures".
- **Why.** The spec says "spread" and "95th-percentile" and defines neither.
- **Gave up.** A standard deviation, which means little for three runs.
- **Limit.** With three runs the minimum and maximum are two of the three values.

### `DEC-T06-COST`: token counts and prices

- **Decided.** Token counts are taken in the parent by a wrapper around the model, a new one for every item. It
  counts every attempt, retries and failed attempts included. An unknown count is "not available", never 0. A
  total with gaps is reported as "at least X; N attempts without token counts". The price table is in the run
  configuration and is copied into the manifest: source, date, currency, and price per million input and output
  tokens with a unit field. Arithmetic is in exact decimals. T06 has a fixture table only.
- **Why.** The agent's log record carries no token counts, and this needs no change to T05.
- **Gave up.** Token counts in T05's log record.
- **Limit.** An attempt that raises returns no counts, so a run with any failed attempt has an "at least" cost.
  After a `child_timeout` the abandoned model call may finish later; its tokens are not captured.

### `DEC-T06-MANIFEST`: what the manifest holds

- **Decided.** As under "The manifest". The dirty flag is true when any tracked file is modified or any
  untracked file lies outside the run-output folder. A dirty-tree run is marked, published and listed in the index
  like any other, but it never counts toward the three runs or the spread of any run set and is never part of a
  baseline, because the commit cannot identify its code. The harness writes only into the run-output folder.
- **Why.** A run that cannot be tied to a commit cannot be repeated.
- **Gave up.** A manifest that is the NFR-3 list and nothing more.
- **Limit.** The manifest records what was reported, not a guarantee. Timestamps and latencies make two runs of
  the same run-set inputs (see "Words") differ byte for byte.

### `DEC-T06-FRAMING-HASH`: how the framing is pinned

- **Decided.** The manifest records one framing code hash: the SHA-256 over the bytes of every file the
  `framings` package imports or reads, in sorted path order. Traced on 2026-10-12, these are
  `framings/__init__.py`, `names.py`, `order.py`, `recognise.py`, `wording.py`, and from `worldgen`:
  `__init__.py`, `matcher.py`, `textutil.py`, `snippets.py` and `names/titles.txt`. A test will fail if importing
  `framings` loads a repository file outside this list.
- **Why.** The T03 wording fingerprint is computed by a function in `tests/t03_framings/framing_checks.py`, and
  the harness never imports test code. The code hash covers `wording.py` byte for byte, so it changes whenever
  an alternate changes.
- **Gave up.** Recording the owner-reviewed fingerprint itself.
- **Limit.** The hash also changes on a comment edit. It shows the files are the same, not that the owner
  reviewed them; that link stays with the T03 tests.

### `DEC-T06-MODELLED-TIME`: parameters and review policies

- **Decided.** The four parameters of the Metrics section, in minutes, with a unit field: manual clearing time,
  proposal review time, L2 time and second-review time. One file holds three complete sets, LOW, BASE and HIGH,
  and all three are computed side by side. Two review policies are computed side by side for each set:
  STRICT_FOUR_EYES, the spec default, with every close second-reviewed, as the headline; and "none", with zero
  second reviews, to show what four-eyes costs. The file's hash goes into the manifest and the parameters are
  printed with every time result. A real run without the file is refused. T06 has a fixture file only.
- **Why.** The spec names the parameters and no unit, and asks that the cost of four-eyes be measured in the
  baseline milestone.
- **Gave up.** QA_SAMPLING, which arrives with FR-13 in wave 2.
- **Limit.** The comparison is a labelled assumption, not a measurement. The values are T07's.

### `DEC-T06-REFERENCE`: reference agents and AC-7

- **Decided.** Always-escalate and always-close are plain functions called in the harness process, with no child
  and no model. They return the T05 result shape and cite the lowest evidence ID in sorted order, so they behave
  the same in every framing. Always-close fails AC-1 by closing every TRUE_MATCH. Always-escalate fails AC-6 by
  the spec's own rule: with no close, citation accuracy is not applicable, and that fails any citation-accuracy
  target. The report flags any parameter set in which `proposal_review + (1 - E/N) x L2 < manual_clearing`,
  where E is the number of alerts whose correct action is escalate and N the number of alerts, both counted from
  the world.
- **Why.** Under such a parameter set always-escalate has a lower modelled time than manual clearing, so
  modelled time alone would not fail it.
- **Gave up.** Showing the AC-6 failure through modelled time.
- **Limit.** The acceptance check in T06 covers AC-1, AC-2, AC-5 and the not-applicable rule of AC-6. No AC-16
  target exists yet, so the rest of AC-6 cannot be checked.

### `DEC-T06-TWINS`: one alert per context

- **Decided.** Every call carries one bundle. Twins are separate calls, loaded only through
  `worldgen/harness_twins.py`. Twin items feed the injection measure and are outside every accuracy and latency figure and outside the cost
  headline; the second cost figure, the total cost over all items, includes them (`DEC-T06-TWINS-2`). The report gives main, twin and total calls and cost.
- **Why.** An alert and its twin share customer and evidence IDs; seeing both would reveal the pair.
- **Gave up.** Nothing.
- **Limit.** One bundle per call is the harness's own rule, shown by test. `recommend` takes whatever it is given.

### `DEC-T06-PARALLEL`: workers, pacer and shutdown

- **Decided.** A thread pool with a configurable worker count, recorded in the manifest. An interrupted run is
  aborted and re-run whole. Five safeguards:
  1. A test that a parallel run gives the same results as a sequential one, using the test-only fake model,
     with items on which the fake chooses a fault as well as items on which it replies.
  2. Nothing shared: each call has its own sink list and token wrapper, and the main thread combines results. A
     stress test requires 1-token calls to sum exactly.
  3. Items are sorted by item ID before writing and before any figure is computed.
  4. A pacer, off by default, set as a maximum number of hand-offs per minute. It waits in the main thread
     before a hand-off, its wait counts as queue time, and it is tested with a fake clock.
  5. Clean shutdown: no new hand-off once a fault has been collected; the fault is checked before the pacer
     wait and again immediately before each submit. A worker that fails after the last check cannot be
     prevented from having its successor submitted: at most the items already submitted or in the act of being
     submitted may still run, and an aborted run is never scored. Calls in flight are waited for (bounded); no
     child process remains afterwards. The manifest is marked aborted. A test interrupts a run and requires that no
     child process is left.
- **Why.** A sequential real run of 5,535 calls is likely hours.
- **Gave up.** Resuming a run item by item.
- **Limit.** Retries inside one item are not paced. See "Conflicts found at the pre-flight" for how the bounded wait
  works. Audited by reading on 2026-10-12: `baseline_agent` and the parent side of `model_interface` hold no
  module-level cache or mutated global, but the model object is called from several threads at once, so the T07
  adapter must be safe for that.

### `DEC-T06-FAKE-MODEL`: the test-only fake model

- **Decided.** The tests use a fake model under `tests/t06_harness`. It reads only the prompt. Its choice of
  reply or fault depends on the sorted set of evidence IDs in the prompt, never on call order. A test requires
  that key to be unique across the 600 alerts and the 15 twins. The tests work out the expected figures by
  simple counting of their own, never with harness code.
- **Why.** The T04 stub plays one fixed reply and never reads the request, so it cannot cite a valid ID for
  each alert.
- **Gave up.** Using the shipped stub for harness tests.
- **Limit.** The fake proves the harness counts correctly. It says nothing about any real model.

### `DEC-T06-MARGIN-PATCH`: testing `child_timeout` quickly

- **Decided.** The `child_timeout` test patches `baseline_agent.recommend.MARGIN_S` in the test process only. A
  second test pins the real value at 10, and the patched test asserts that the timeout is fast.
- **Why.** With the real margin one `child_timeout` costs at least 10 of the gate's 45 seconds.
- **Gave up.** Nothing in the shipped code.
- **Limit.** The real 10-second margin is not exercised by the T06 gate.

### `DEC-T06-NO-ENV`: no environment variables in outputs

- **Decided.** The manifest and the reports never record an environment variable. Key handling is T07.
- **Why.** A key will live in the environment from T07 on.
- **Gave up.** Nothing.
- **Limit.** This covers what the harness writes. What a model's `reason` text says is not checked.

## Decision changes during the build

Changes to a recorded decision that were agreed while building. The records that supersede the old ones are
entered in Genesis in one batch before the gate, not as each change is made.

| Decision | Change | Agreed |
|---|---|---|
| `DEC-T06-FAKE-MODEL` | For a fixed subset of keys, the fake's answer also depends on which evidence ID is presented first. The record says the answer depends on the sorted set of evidence IDs alone; with that, the fake answers the same in all three framings and verdict consistency would always be 100% in the tests. The answer still comes from the prompt only and never from call order. This supersedes that part of the record. | owner, 2026-10-13 |

| `DEC-T06-SPREAD` | Unchanged; one addition beside it. The headline figure of a run set is pooled over its valid runs (summed numerators, denominators and counts; latency over all their main items). The record covers the spread only: each run's value with the minimum and maximum. The pooled figure was added because `SPEC.md:126` defines every rate over items "in one run" taken together, and `SPEC.md:133` defines verdict consistency over "all alert-runs". | owner, 2026-10-13 |
| `DEC-T06-FAULTS` | Addition. Superseding a run set is an explicit human action: set A by set B, with a required, non-empty written cause. Nothing does it automatically. A superseded set can never be a baseline, and a run whose run-set ID matches a superseded set is refused before any call. The record says only that the old set "stays listed as superseded". | owner, 2026-10-13 |
| `DEC-T06-FAKE-MODEL` | Addition. A plain CLOSE or ESCALATE of the fake cites two evidence IDs picked by the same hash of the sorted ID set, sometimes the same one twice. With the lowest ID always cited, no cited ID was ever in a supporting evidence key and citation accuracy was 0 in every test. Found while building the score step. | owner approved, 2026-10-13 |

| `DEC-T06-FAULTS` | The agent name is a tenth run-set input. This supersedes the list of nine in the record. Without it, a run of a reference agent with the same configuration would land in the baseline's run set and be pooled with it. "Words" is still the one place the list lives. | owner, 2026-10-13 |
| `DEC-T06-MANIFEST` | Addition. The score step writes a report only for a run that has none; replacing a report needs an explicit option. Every report names the commit of the scoring code and whether that tree was dirty. The run-set report is worked out afresh each time and says which code wrote each run's report. | owner, 2026-10-13 |

| `DEC-T06-MODELLED-TIME` | The modelled-time parameter file is required for every run, the stub and the reference agents included. This supersedes the part of the record that refuses only a run "with a provider other than the stub". AC-24 asks every run's report to hold the parameters. | owner, 2026-10-13 |
| `DEC-T06-COST`, `DEC-T06-MODELLED-TIME` | Extension. Both the price table and the modelled-time file must state a `kind`: "fixture" or "sourced". A sourced file must give a source for each value: for each price of each model, and for each parameter of each set. A run whose provider is real, meaning any provider other than the stub and the test fake, refuses a fixture file before any call. Results worked out from a fixture file are labelled mechanism-only in every report and in the acceptance check: they show that the mechanism works and nothing about real cost or real review time. | owner, 2026-10-13 |
| `DEC-T06-REFERENCE` | Extension. The acceptance check also covers the time half of AC-6: the modelled assisted time must be lower than the modelled manual time at BASE under STRICT_FOUR_EYES, with the other five results shown beside it. AC-6 is "fail" if either part fails, and otherwise "not determined" while no AC-16 target exists. The check covers every completed run of a run set, valid or not. | owner, 2026-10-13 |
| `DEC-T06-NO-FILES` | Extension. The recorder watches directory listings as well as file opens: the audit events `open`, `os.listdir` and `os.scandir`. A test shows that it catches opening a file by several routes (`open`, `Path.read_bytes`, `os.open`) and listing a directory by several routes (`os.listdir`, `os.scandir`, `Path.iterdir`). The record says only that file-open events are recorded. | owner approved, 2026-10-13 |
| `DEC-T06-MANIFEST` | Addition. A run set can be a baseline only if every run report and the run-set report were scored by the same clean commit. Otherwise the set report says that re-scoring is needed. | owner, 2026-10-13 |
| `DEC-T06-REFERENCE` | Addition. For an agent that calls no model, the manifest records the model as not used and holds no prompt, decoding parameters or retry policy. Its cost is exactly 0 with no calls, which is a real zero and not an unknown. The run configuration still names a model configuration, so the format stays one shape. | owner, 2026-10-13 |
| `DEC-T06-COST` | Addition. An attempt is priced by the model ID the provider reported for it. An attempt whose reported ID has no price is counted as "without a price" and makes the cost a lower bound. Totals are exact decimals; cost per alert and time per alert are also given rounded to six places and say so. | owner, 2026-10-13 |

| `DEC-T06-FAULTS` | Two corrections, found by checking the records against the code. (1) The record says that any re-run records a written cause; nothing enforces that. It now says that the manifest holds a re-run cause when the owner supplies one and that the run-set index lists every run attempt, aborted ones included; enforcing a written re-run cause is carried to T07. (2) The record says that the aborted count is published; the run-set report listed aborted runs but gave no count. It now gives the number of aborted runs with the model calls they made and their known cost, from the run-set index, shown by a test. | owner, 2026-10-14 |
| `DEC-T06-PARALLEL` | Extension, four points. (1) With one worker there is no pool: the calls are made one after another in the main thread, so the parallel-equals-sequential tests compare two different code paths. (2) The pacer spaces hand-offs evenly, 60 seconds divided by the setting apart, and an item is handed off only when a worker is free; the worker count is a whole number from 1 to 64 and the pacer setting a whole number of 1 or more, or null. (3) Each item line carries its queue time, and the manifest the run's duration and total queue time. (4) Interrupts: Ctrl-C is a clean abort from the moment the run is listed; with several workers the calls in flight are waited for, and a second Ctrl-C gives up that wait but still marks the run aborted; with one worker the call in flight is cut short. The owner first accepted that a second Ctrl-C leaves the run listed as "started"; covering the whole run, which the owner then asked for, changed that to "aborted". | owner, 2026-10-13; the second-Ctrl-C outcome is the builder's reading of that instruction |
| `DEC-T06-GATE-TIME` | The gate's time target of 45 seconds is superseded: the slowest of three runs is to be under 60 seconds, with an alarm at 80 seconds. The gate still stops at 120. | owner, 2026-10-13 |
| `DEC-T06-GATE-TIME` | Extension, after the build machine (WSL, 3.5 GiB of RAM) went down during stage 5. Four points. (1) The mutation proofs run two copies at a time, not four; the count is one named setting, `AT_A_TIME`. (2) The stress test of `DEC-T06-PARALLEL` safeguard 2 uses 8 workers and 1,000 items, not 16 and 4,000, as two named settings, and is renamed `test_one_token_calls_sum_exactly_under_the_stress_workers`. Under the breakage "one token wrapper is shared by all items" every item keeps a copy of all attempts so far, which grows with the square of the item count: about 24 million records at 4,000 items, worked out by reading and not measured. (3) Each copy's test process gets a hard limit of 1 GiB of address space (`RLIMIT_AS`, set in the launched process, inherited by what it starts). A broken copy that runs out of memory ends alone and is reported as "out of memory", which counts as caught. (4) The limit has its own proof in the gate: one deliberately memory-hungry broken copy must end as "out of memory" while the same test passes on an untouched copy. Measured on 2026-10-13: that copy ended with exit code 1 and a `MemoryError`, at 739 MB resident. Three runs of the gate took 51.85, 51.91 and 52.30 seconds, 287 tests passed each time, the mutation proofs about 16 seconds of that; memory in use on the machine peaked at 2.35 GB. The limit is on address space, so it is stricter than a limit on memory really used. | owner, 2026-10-13 |
| `DEC-T06-GATE-TIME` | Two corrections to the mutation proofs, found when they first ran to the end. (1) Every breakage names how its broken copy must end, and any other ending is not a catch. The named ending is the start of the reason pytest gives: for 31 of the 38 a failing assertion in the named guard test; for breakage 13 a named error on loading the guard's file, `ZeroDivisionError: Fraction(0, 0)`, with exit code 4; for five a named error raised in the guard test (20: `KeyError: 'kind'`; 21, 31 and 34: `Failed: DID NOT RAISE ConfigError`; 30: `FileNotFoundError`); for 33 a failing assertion with the named message `no refusal for a missing written cause`. Its guard, `test_superseding_needs_a_written_cause`, was changed so that all four of its cases fail on the missing refusal itself: before, two of them failed on a later `AttributeError` from the cause that was let through. Every failure pytest reports must be about the guard and give a named reason. Before this the proof needed exit code 1 and only the guard's name, so breakage 13 was reported as not caught. A test shows that a copy failing for a reason its entry does not name is reported as not caught. "Out of memory" stays a catch, as in the row above. (2) An untouched copy whose process ends badly without naming a failed test is no longer read as a pass. | owner approved, 2026-10-13: the rule of (1) and point (2); 2026-10-14: the five named errors raised in a guard test, and the change to the guard of 33 with its one named ending |
| `DEC-T06-FIGURES`, `DEC-T06-COST`, `DEC-T06-MODELLED-TIME` | From review round 1, finding 1 (FR-20). Cost per alert is given by framing and by primary family, over main items only; modelled review time is given by framing and by primary family. For a family, N and the escalate count are those of its own alerts. Tests check both against counts made independently from the fake model's rule. Each call is counted once: the token counts of an item are tallied by reported model, and each group is priced once from the summed counts, so the breakdowns cost little; one scoring pass of three runs went from 1.69 s to 0.93 s, with no test or assertion removed. | owner, 2026-10-14 |
| `DEC-T06-MANIFEST` | From review round 1, finding 2 (AC-24). `python -m harness run-and-score CONFIG OUT` runs and then scores, in that order; it is the evaluation run of AC-24. The run step still never imports `worldgen.truth`. A bare run has no report, by design. | owner, 2026-10-14 |
| `DEC-T06-GATE-TIME` | From review round 1, finding 3. "Out of memory" is counted only when the copy's output shows a `MemoryError`; a copy ended by a signal is not a catch. The address-space limit sends no signal of its own: an allocation past it fails, and Python raises `MemoryError`. An untouched copy passes only with exit code 0. One negative test for each: a copy killed by `SIGTERM` is not caught, and an untouched copy whose session fails for an unrelated reason is not a pass. | owner, 2026-10-14; that no signal is counted is the builder's reading of "the memory-limit signal" |
| `DEC-T06-COST` | From review round 1, finding 5. The headline stays main cost over main items. The total cost over all items, twins included, is reported as a second figure, and the literal wording of `SPEC.md:136` is quoted beside the interpretation in "The figures". | owner, 2026-10-14 |
| `DEC-T06-MANIFEST` | From review round 2, finding B1 (AC-24). The score step checks and scores each run on its own. A run whose check fails is refused: nothing is written for it, and it is listed as excluded with its reason, in its set report and on the command line; the other runs still get their reports, and the command exits non-zero. A check of the world itself still refuses the whole step, and so does a step in which every run to score is refused. A test damages an older run and runs `run-and-score` for a new one: the new report exists, the damaged run is listed as excluded, the exit code is non-zero. No active record said that a refused score writes nothing; only the code did. | owner, 2026-10-14; refusing the whole step when every run is refused is the builder's choice |
| `DEC-T06-GATE-TIME` | From review round 2, finding B2. Out of memory is counted only when the exit code is positive and the output shows a `MemoryError`; a copy ended by a signal is never out of memory, whatever its output says. A test: exit -15 with `MemoryError` in the output is not out of memory and not caught. | owner, 2026-10-14 |
| `DEC-T06-TWINS` | From review round 2, finding B3. Twins are outside every accuracy and latency figure and outside the cost headline; the second cost figure, the total cost over all items, includes them. The record said twins are outside every cost-per-alert figure. `DEC-T06-TWINS-2` was recorded on 2026-10-15 and supersedes `DEC-T06-TWINS`. | owner, 2026-10-14 |
| `DEC-T06-GATE-TIME` | New files: `tools/power_check.sh` and `tools/memory_guard.sh`, the charger check and the memory watch used for timed runs, which before lived outside the repository and were lost when WSL restarted. They behave as before: the check reads `/sys/class/power_supply/AC1/online`; the guard runs the command in its own process group with default Ctrl-C handling restored, checks the memory in use every 0.25 s, kills the group above 3,000 MB, prints the memory before and at its peak and the exit code, and exits with that code. They are timing aids, not part of the harness. `tests/t06_harness/test_timing_tools.py` checks, with dummy processes only: the three outputs of the check on a fake path; that the guard kills a process taking memory past a low test limit and says so; that it passes a process through with its exit code; and that Ctrl-C reaches the child. | owner approved, 2026-10-15 |
| `DEC-T06-GATE-TIME` | Measurements only; the target is unchanged. On 2026-10-15 the whole t06 suite was run three times through `tools/timed_run.sh`, which checked the charger and the benchmark before starting each run under the memory guard. Charger in each time; G-Helper mode not given by the owner. 306 passed in 56.77, 58.15 and 58.08 s, with the benchmark at 0.797, 0.805 and 0.760 s just before each run; memory in use peaked at 2,371 MB, no swap was used, and no test process was left. The slowest, 58.15 s, is under the 60-second target, with a margin of about 2 s. | measured by the builder, 2026-10-15 |
| `DEC-T06-MANIFEST`, `DEC-T06-GATE-TIME`, `DEC-T06-TWINS` | From review round 3. (1) Finding B1: loading and checking each run is guarded as one step, so a run that cannot be loaded at all (a missing or empty file, invalid JSON, a missing field, a value of the wrong type) is quarantined as "refused: <run>: <what>", the exit code is non-zero, and the other runs still get their reports. Every manifest field the score step uses is read in that step. An error while computing the figures is a bug and still stops the step. Tests: a missing `outputs`, an invalid JSON manifest, a missing items file, an empty manifest and a manifest of the wrong type, each followed by a new `run-and-score` that still gets its report; and a test that a figures error stops the step. (2) Finding B2: `tools/timed_run.sh` refuses unless the charger check says exactly "plugged in" and the benchmark exits with 0 and prints N=12000000 and result 983797; `--unchecked` runs anyway and prints "UNCHECKED TIMING". Tests with dummy commands: unknown charger state, failing benchmark, wrong result, the override. (3) Finding B3: the guard keeps its machine-wide trigger; the limit is stated in its header and in the test plan, and a test shows that a memory spike in an unrelated process stops the guarded command, says so, and leaves the unrelated process alone. (4) Finding B4: the glossary, the index table and the scoring module header no longer say that twins appear in no cost figure or that infrastructure-invalid is a state; "The figures" and the `DEC-T06-TWINS` section said the same and are corrected too. The benchmark test asserts the full result, 983797. | owner, 2026-10-15 |
| `DEC-T06-GATE-TIME` | Measurements and a new target. After the round-3 tests were added, the whole t06 suite was run four times on 2026-10-15 through `tools/timed_run.sh`, charger in, G-Helper mode not given: 316 passed in 62.16, 66.74, 61.35 and 68.29 s; the benchmark read 0.796, 0.794, 0.802 and 0.799 s just before each run; memory in use was 1,703, 1,752, 1,722 and 1,697 MB before and peaked at 2,516, 2,540, 2,452 and 2,537 MB. Run 2 was 4 to 5 s slower than runs 1 and 3 for an unknown reason, and run 4 was 6 to 7 s slower; during run 4, two `codex` processes, the VS Code server and Claude Code were running on WSL. The new tests themselves took their usual times in every run. The target is now: **the slowest of three runs under 75 seconds, alarm at 90, the gate stops at 120**, by the owner's judgment, replacing under 60 with an alarm at 80. The slowest measured run, 68.29 s, leaves a margin of about 7 s. `DEC-T06-GATE-TIME-4` and `DEC-T06-MANIFEST-4` were recorded on 2026-10-15 and supersede `DEC-T06-GATE-TIME-3` and `DEC-T06-MANIFEST-3`. | owner, 2026-10-15 |
| `DEC-T06-MANIFEST`, `DEC-T06-GATE-TIME` | From review round 4. (1) `run-and-score` scores the run it has just made first and writes its report before any other run is touched. Everything else about older runs and the set reports is best-effort, each run isolated: any error while loading, checking or scoring an older run quarantines it with a reason, the command exits 1, and the new report is never blocked. A set report that cannot be written is listed as excluded. Only an error in the new run's figures stops the step loudly. A kept older `report.json` is read only for `scored_by`, never for figures or any other decision; one that cannot be read, or is not a JSON object, quarantines its run, and one without a usable `scored_by` makes its set need re-scoring, never eligible. (2) A run the index lists as completed whose `manifest.json` is missing is quarantined with a reason, exit 1. (3) `tools/timed_run.sh`: each test override, when set, prints "UNCHECKED TIMING"; `tools/memory_guard.sh` fails closed: if the memory in use cannot be read, it does not start the command or it stops it, says so, and exits 125. (4) The report's items note, the scoring module header and the `report.json` row above say exactly what twins feed and what a report holds besides numbers. Tests: a wrong-type price, an integer `cited_ids`, an invalid `report.json` and a deleted manifest in an older run, each followed by a new `run-and-score` that still gets its report; a kept report without `scored_by`; an error in the new run's figures; a score step in which every run fails while scored; each test override marking the timing; an unreadable memory reading. The probe of `test_the_truth_is_read_only_after_the_outputs_exist_and_were_checked`, `ORDER_PROBE`, was deleted by mistake while editing and has been rebuilt from that test's assertions; the original text could not be recovered. A positive control now loads the truth early on purpose and requires the probe to see it, and a 39th breakage, "the order probe never sees the truth loaded", must fail that control. `DEC-T06-MANIFEST-5` was recorded on 2026-10-15 and supersedes `DEC-T06-MANIFEST-4`; after that, Genesis held 38 `DEC-T06-*` records, 19 active and 19 superseded. | owner approved, 2026-10-15 |
| `DEC-T06-GATE-TIME` | Measurements only; the target is unchanged: the slowest of three runs under 75 seconds, alarm at 90, the gate stops at 120. After the round-4 changes, the whole t06 suite was run three times on 2026-10-15 through `tools/timed_run.sh`, charger in, no test override set, G-Helper mode not given: 323 passed in 65.68, 65.66 and 66.87 s; the benchmark read 0.786, 0.787 and 0.799 s just before each run; memory in use was 1,791, 1,824 and 1,811 MB before and peaked at 2,536, 2,485 and 2,519 MB; no swap was used and no test process was left. The slowest, 66.87 s, leaves a margin of about 8 s. These runs were made before the positive control and the 39th breakage were added. | measured by the builder, 2026-10-15 |
| `DEC-T06-MANIFEST` | From review round 5. (1) The order is exact: `run-and-score` reads the index, loads only the run it has just made, scores it and writes its report, and only then loads any older run; a test records the loads and writes and requires the new report before any older load. (2) `validate_run(index entry, manifest, items)` runs when each run is loaded. It checks the types the figures rely on (booleans, whole numbers, lists of text, numbers); that the index entry and the manifest agree on run_id, run_set and state; that the run-set ID is the hash of the manifest's run-set inputs; that both embedded tables pass the run-step checks and match their recorded hashes and the run-set inputs; that the item count, the main and twin counts and the item IDs agree with the manifest and are unique; and that every item row has every field a figure uses, of the right type. A failure quarantines the run with its reason, exit 1. A set is eligible only if all its runs have identical tables. (3) Tests: one table-driven test over a small run in memory, one case per check; the six probes of the review on a real run (index against manifest, numeric 0 for dirty and marked, invalid kind in both tables, a changed older price, twin "false", a rehashed item row); and a set with two different tables is never eligible. (4) The report test is renamed `test_the_report_holds_its_manifest_fixed_notes_and_no_agent_reason_text_or_sampled_evidence_values` and now checks the notes; `ORDER_PROBE` also checks that the items file was read, and so hashed, before the first hidden open. Limit: a run rewritten by someone with write access, including its hashes, is not detected; baseline provenance comes from the committed run and git history in T07. `DEC-T06-MANIFEST-6` was recorded on 2026-10-15. | owner, 2026-10-15 |
| `DEC-T06-GATE-TIME` | Measurements only; nothing has been cut and the target is unchanged: the slowest of three runs under 75 seconds, alarm at 90, the gate stops at 120. After the round-5 changes, the whole t06 suite was run three times on 2026-10-15 through `tools/timed_run.sh`, charger in, no test override set, G-Helper mode not given: 333 passed in 85.86, 77.05 and 74.17 s; the benchmark read 0.797, 0.802 and 0.802 s just before each run; memory in use was 1,517, 1,532 and 1,551 MB before and peaked at 2,388, 2,363 and 2,229 MB; no swap was used and no test process was left. **The slowest, 85.86 s, is above the 75-second target and below the 90-second alarm**, and so is 77.05 s. In run 1, three of the shell-based timing-tool tests took 11.7 s together, against about 0.6 s in runs 2 and 3, for an unknown reason; without that, run 1 would have been near 74 s. `validate_run` takes about 12 ms on a full run and about 36 ms for a whole load, so it explains a few seconds at most; the rest of the rise from about 66 s in round 4 is not yet explained. The owner is told before anything is cut. The owner then set a new target, nothing cut and every test kept: the slowest of three runs under 90 seconds, alarm at 100, the gate stops at 120, replacing 75/90. One more run for information, 13:35, 333 passed in 72.84 s with the benchmark at 0.807 s. `DEC-T06-MANIFEST-6` and `DEC-T06-GATE-TIME-5` were recorded on 2026-10-15. | measured by the builder, 2026-10-15; the new target by the owner, 2026-10-15 |
| `DEC-T06-MANIFEST` | From review round 6. (1) One declarative schema, `SCHEMA` in `harness/score.py`, lists every field of the manifest, of an item row and of an attempt that the score step reads, with its type and range: booleans only for flags; whole numbers of 0 or more for counts and token counts; framing one of the three; finite numbers of 0 or more for `wall_s`, `queue_s` and `latency_s`, null refused. The list was taken from the code, by scoring real runs with every read field noted; a test does the same and fails if the score step reads a field the schema does not list. Every earlier check is kept. (2) Every fact the index entry and the manifest both hold is compared: run_id, run_set, state, the dirty flag, the mark, calls, cost, the re-run cause, the start time, and the cause against the abort record. The mark is recomputed from the item rows with the run step's exact-fraction function, and the threshold must be the one among the run-set inputs. (3) Eligibility fails closed: a set with any refused completed run is not eligible, and its report names each refused run and why. (4) `wall_s` is never below the agent's `latency_s`: found in 5,571 rows (a full in-process run, two full reference-agent runs, 36 items through the real child with 4 workers), smallest gap 0.000001 s, and true by construction, since the agent measures its time inside the harness's window on the same monotonic clock; so the rule is added. (5) Tests: one table-driven test of the round-6 rules on a small run in memory, a refused fourth run makes the set ineligible, and the schema-coverage test; the test fixture `set_validity` now keeps the index and the manifest consistent and, for a marked run, turns enough rows into timeouts for the mark to follow. Two breakages are added, "the schema loop checks nothing" and "a set with a refused completed run can still be eligible": 41 in all. Limit: values that are valid in type and range but wrong in meaning are not detected. `DEC-T06-MANIFEST-7` was recorded on 2026-10-15. | owner, 2026-10-15 |
| `DEC-T06-GATE-TIME` | Measurements only; the target is unchanged: the slowest of three runs under 90 seconds, alarm at 100, the gate stops at 120. After the round-6 changes, the whole t06 suite was run three times on 2026-10-15 through `tools/timed_run.sh`, charger in, no test override set, G-Helper mode not given: 336 passed in 77.63, 78.10 and 78.25 s; the benchmark read 0.793, 0.794 and 0.786 s just before each run; memory in use was 1,715, 1,793 and 1,803 MB before and peaked at 2,564, 2,494 and 2,475 MB; no swap was used and no test process was left; all 41 breakages were caught in each run. The slowest, 78.25 s, leaves about 12 s to the target and about 42 s to the 120-second stop. | measured by the builder, 2026-10-15 |
| `DEC-T06-MANIFEST` | From review round 7. (1) One shared schema, `harness/schema.py`, beside the run step that writes the files, describes the manifest, each index entry, the record of a superseded set, and each item row; the score step checks them against it, replacing the round-6 `SCHEMA` in `harness/score.py`. It is strict: every key required, unknown keys refused, every nested field typed and ranged (calls, cost, git, timing, model, prompt, decoding, retry_policy, review_policies, hashes as 64 hex digits, workers 1 to 64, the pacer 1 or more or null, times with their offset), and enums for state, framing and failure_kind (the agent's and the parent's kinds). It applies to completed and non-completed runs, and every index entry is checked before any run is grouped. The round-trip test found one place where the writer is looser than the plan: an attempt keeps the model ID the provider reported, which can be a number (the `child_crash` case of `test_child.py`), so that one field is text, a number or null. (2) Tests: everything the writer produces fits the schema (a completed in-process run, a reference-agent run, an aborted run, the parent-built `internal_error` and `child_crash` rows, a superseded-set record); a key the writer adds that the schema does not name is refused; one table for findings B1 to B4 on small runs in memory; a stray index entry makes every set ineligible in a real score step. (3) Global fail-closed: while any index entry fails the schema, or any run cannot be placed in a set (its manifest missing, unreadable, or naming another run set), no set is eligible, and each set report lists them in `unassigned`. (4) Breakage 39 now targets the shared schema, "the shared schema checks nothing", since the round-6 loop it broke is gone; breakage 40 now removes only the per-set rule; breakage 41, "a set is still eligible while an index entry or a run cannot be placed", is new: 42 in all. Limit: a hand-edited run or index entry that is well-formed and self-consistent is not detected; baseline provenance comes from the committed run and git history in T07. `DEC-T06-MANIFEST-8` was recorded on 2026-10-15. | owner, 2026-10-15 |
| `DEC-T06-GATE-TIME` | Measurements only; the target is unchanged: the slowest of three runs under 90 seconds, alarm at 100, the gate stops at 120. After the round-7 changes, the whole t06 suite was run three times on 2026-10-15 through `tools/timed_run.sh`, charger in, no test override set, G-Helper mode not given: 341 passed in 82.60, 83.39 and 82.02 s; the benchmark read 0.818, 0.795 and 0.822 s just before each run; memory in use was 1,788, 1,802 and 1,800 MB before and peaked at 2,519, 2,564 and 2,499 MB; no swap was used and no test process was left; all 42 breakages were caught in each run. The slowest, 83.39 s, leaves a margin of about 7 s to the target and about 37 s to the 120-second stop. | measured by the builder, 2026-10-15 |
| `DEC-T06-MANIFEST` | From review round 8; fixes only, no new feature and no new record, since `DEC-T06-MANIFEST-8` already promises a type and a range for every nested field. (1) A `state` of any type other than text, in an index entry or a manifest, now gives a schema problem: a list or an object used to raise `TypeError` at the dictionary lookup, before any run was loaded. `SECONDS` and `REPORTED_ID` catch `OverflowError`, so a whole number too large for a float, such as 10**400, gives a problem instead of raising, and a refusal never fails while showing a value. The optional `note` of the price table and of the modelled-time file must be null or text of at most 500 characters, in the run step's own table checks, which the score step uses too. (2) One hostile-value test walks the shared schema along a valid example and puts each of a list, an object, null, true, NaN, infinity, 10**400, the empty string and a 10,000-character string in every place it describes: 337 places in a completed and an aborted manifest, an item row, an index entry in each state and a superseded-set record, 3,033 cases in about 0.75 s. Every validator returns a problem or accepts; none raises. Against the previous `harness/schema.py` and `harness/cost.py` the same test fails with 23 raising cases. A short test covers the note rule. (3) No active record conflicts. | owner, 2026-10-16 |
| `DEC-T06-GATE-TIME` | Measurements only; nothing has been cut and the target is unchanged: the slowest of three runs under 90 seconds, alarm at 100, the gate stops at 120. After the round-8 fixes, with the under-one-second assertion removed from the hostile-value test, the whole t06 suite was run three times on 2026-10-16 through `tools/timed_run.sh`, charger in, no test override set, G-Helper mode not given: 343 passed in 85.02, 98.67 and 87.69 s; the benchmark read 0.806, 0.800 and 0.800 s just before each run; memory in use was 1,504, 1,563 and 1,547 MB before and peaked at 2,217, 2,270 and 2,297 MB; no swap was used and no test process was left; all 42 breakages were caught in each run. **The slowest, 98.67 s, is above the 90-second target and below the 100-second alarm.** Almost all of its extra 13 s over run 1 is in four mutation-proof tests, which copy the repository and start pytest in subprocesses: the proof itself took 26.28 s against 20.92 and 21.68 s, and the untouched-copy, memory-limit and signal tests about 7.4 s more; only 5 of the 76 tests over 0.2 s were more than 15% slower than in run 1. The cause is unknown; something slowed starting processes or copying files during that run. Runs 1 and 3 leave about 5 s and 2 s to the target. The hostile-value test took 0.51, 0.54 and 0.54 s for its 3,033 cases. | measured by the builder, 2026-10-16 |
| `DEC-T06-MANIFEST`, `DEC-T06-GATE-TIME` | Owner decisions after the round-8 timings. (1) Catch-all validation: any exception raised while checking an index entry, a manifest or item rows never propagates. For an index entry or a superseded-set record it is that entry's problem and blocks eligibility; for a manifest it is "refused: <run>: <type>: <message>" and leaves the run's set unconfirmed, so no set is eligible; for item rows it refuses that run. The hostile-value test is kept. (2) The mutation proofs run by hand before completion with `T06_MUTATION=1` and are recorded as evidence; the default gate run skips them, except the check that every breakage names a guard test that exists, which is quick and runs in it. (3) One test, `test_mutation_switch.py`, starts two test processes and shows that without the variable a proof is skipped while the guard-name check runs, and that with it both run. (4) Threat model: the score step trusts output written by the same version of the harness and checks it for integrity and shape (hashes, the shared schema, the index against the manifest); any failure or raise while checking quarantines the run; hand-crafted adversarial files are out of scope. No active record conflicts but `DEC-T06-GATE-TIME-5`, which put the proofs in the gate and is superseded. `DEC-T06-MANIFEST-9` and `DEC-T06-GATE-TIME-6` were recorded on 2026-10-16. | owner, 2026-10-16 |
| `DEC-T06-GATE-TIME` | Measurements only; the target is unchanged: the slowest of three runs under 90 seconds, alarm at 100, the gate stops at 120. With the mutation proofs out of the default gate run, three runs on 2026-10-16 through `tools/timed_run.sh`, charger in, no test override set, G-Helper mode not given: 337 passed and 7 skipped in 55.97, 55.75 and 56.65 s; the benchmark read 0.799, 0.806 and 0.797 s just before each run; memory in use was 1,509, 1,528 and 1,534 MB before and peaked at 1,725, 1,745 and 1,729 MB; no swap was used and no test process was left. The mutation proofs alone, with `T06_MUTATION=1`: 7 passed in 28.98 s, benchmark 0.792 s, memory in use peaking at 2,236 MB, all 42 breakages caught. After the guard-name check was moved back into the default gate, one more run: 338 passed and 6 skipped in 55.86 s, benchmark 0.798 s. The slowest of the three, 56.65 s, leaves about 33 s to the target. | measured by the builder, 2026-10-16 |
| `DEC-T06-GATE-TIME` | From review round 9. (1) The 120-second stop is Genesis's: it kills the gate's test command after 120 seconds, the default timeout of `genesis gate` (genesis-kit `tools/genesis.mjs:1131`, `const timeout = positive(parsed.options.timeout || 120000, 'timeout');`), by a SIGKILL to the command's process group (`genesis.mjs:1087`). A plain `pytest` run, and a run through `tools/timed_run.sh`, had no such stop. (2) `tools/memory_guard.sh`, under which `tools/timed_run.sh` runs a command, now also stops a command after `MEMORY_GUARD_MAX_SECONDS`, 110 seconds unless set (a fraction is allowed): it kills the command's process group, says "STOPPED BY GUARD: the command ran longer than the limit of N s" and exits with the command's code, 137, as for the memory limit. A value that is not a positive number of seconds starts nothing and exits with 125. One test checks it with a dummy `sleep 30` and a limit of 0.3 s, in under 1 s. (3) The full-world test's own count of citation existence now counts a citation as valid only if its cited list is non-empty and has no unknown ID, as the Metrics section defines it; the figures it expects are unchanged. `DEC-T06-GATE-TIME-7`, superseding `DEC-T06-GATE-TIME-6` with the gate-stops clause reworded to say this, was recorded on 2026-10-16. | owner, 2026-10-16 |
| `DEC-T06-PARALLEL` | From review round 10; a fix to meet `DEC-T06-PARALLEL-2` (5), "no new hand-off" after a fault, so no new record. (1) In the pool path of `hand_off` in `harness/run.py`, the main thread collected the failures of finished calls before the pacer's wait and then handed off the next item without looking again, so a call that failed during the wait was followed by one more hand-off. It now collects again immediately before every hand-off, after the pacer's wait, and stops if a fault is known; the check before the wait stays, so a known fault does not wait for the pacer. Queue time is unchanged. (2) A new test, `test_a_fault_that_comes_back_during_the_pacer_wait_stops_the_next_hand_off` in `test_parallel.py`, uses a fake clock, a pacer of 30 a minute and 2 workers: item 0 fails during the pacer's wait before item 1, and the test asserts that item 1 never starts and the hand-off raises the fault that aborts the run; it takes a few milliseconds. A new breakage, "no re-check for faults after the pacer wait", removes the re-check, with that test as its guard. The breakage "hand-offs continue after a fault" now switches off both checks, since without a pacer either check alone stops the hand-offs. 43 breakages. (3) The full-world test's own count of citation existence now judges each cited ID against the IDs of the bundle sent, not against the fake model's `EVD-UNKNOWN` sentinel; the figures it expects are unchanged. | owner, 2026-10-16 |
| `DEC-T06-PARALLEL` | From review round 11. (1) A stated limit, not a code change: the round-10 re-check narrowed the window but cannot close it. The last check for faults and the submit are two operations, so a worker that fails between them still has its successor submitted, with or without the pacer; `DEC-T06-PARALLEL-2` (5), "no new hand-off", promised more than the code can do. `DEC-T06-PARALLEL-3` supersedes it with every sentence word for word except that wording, which becomes: no new hand-off once a fault has been collected; the fault is checked before the pacer wait and again immediately before each submit; a worker that fails after the last check cannot be prevented from having its successor submitted: at most the items already submitted or in the act of being submitted may still run, and an aborted run is never scored. The text about clean shutdown, harness faults, the pre-flight reading and the limits is updated to match. Known test limit: the pacer test covers a fault that comes back during the pacer wait, not one between the last check and the submit. (2) Improvement only, not made: in `test_reference.py` the assertion on the reference agent's injection block compares `divergent`, `by_cause` and `by_label` with the report's own values, so that part proves nothing; only `pairs == 45` and the separate `verdicts_differ == 0` check something. Known test limit. `DEC-T06-PARALLEL-3` was recorded on 2026-10-16. | owner, 2026-10-16 |
| `DEC-T06-REVIEW` | From review round 12, the last: APPROVE. No code or test changed. The remaining improvement, the reference-agent assertion that compares the report with itself, is not fixed and is listed under "For T07 and wave 2" as known issue 5, with four more known issues found while closing T06: no primary-family cells for injection divergence, mixed numeric and text model IDs breaking the manifest, inputs the run step accepts but the schema refuses, and acceptance `mechanism_only` following the modelled-time file only. T07 carries: model IDs as text, and both tables sourced. The race window between the last fault check and the submit stays as stated in `DEC-T06-PARALLEL-3`. `DEC-T06-REVIEW-R12`, a new record of the independent review, was recorded on 2026-10-16. | owner, 2026-10-16 |
| `DEC-T06-GATE-TIME` | Measurements only; the target is unchanged and nothing has been cut. Whole t06 suite, `288 passed` unless noted, seconds as pytest reports them. 2026-10-13: 51.85, 51.91 and 52.30 (287 tests, before the test of an unnamed ending was added), then 53.96. 2026-10-14, 6 minutes after WSL started: 69.24, 67.89 and 70.49. 2026-10-14, 11 to 13 minutes after start: 69.80, 68.26 and 67.08; the slowest of these is above the 60-second target and below the 80-second alarm. 2026-10-14, charger in and Best performance on: 55.90, 55.03 and 54.98, so the target holds and is unchanged. Ruled out by measurement: a cold machine (the later runs are as slow), swap (0 MB used after each run), and memory (peak in use 2.29 GB). Ruled out by reading: the code, since the only change after the 53.96-second run is the guard of breakage 33, yet tests that change does not touch are slower too, for example the full-world setup in `test_cost.py`, 1.84 s on 2026-10-13 and 2.83 to 3.04 s on 2026-10-14. The reference-test rule that followed (the `test_cost.py` setup, about 1.75 s against about 2.9 s) is withdrawn: that setup includes scoring, so it also moves when the scoring code changes. The reference is now the fixed benchmark `tools/bench_reference.py`, a pure-Python loop that imports only `time`, run with the charger state before every timed run. Balanced runs before the change took 61.78 to 65.02 s, so the change is the most likely explanation of the speed-up; four Balanced runs after the change (55.87, 56.99, 55.93 and 56.40 s) are close to the three Turbo runs (56.04 to 56.88 s), so the power mode shows no measurable difference. After review round 1 the new breakdowns raised the gate to 63.15 to 64.18 s (G-Helper Balanced, charger in), then 61.78, 64.50 and 65.02 s (Balanced, charger in; benchmark 0.790 to 0.817 s). The cost pass (each call tallied once, each group priced once from the summed counts; one scoring pass of three runs went from 1.69 s to 0.93 s) brought it to 294 passed in 56.81, 56.04 and 56.88 s, with the benchmark at 0.773, 0.765 and 0.767 s just before each run, charger in, on G-Helper Turbo (Windows switched to Best performance). One run on Balanced, charger in, benchmark 0.781 s: 295 passed in 55.87 s. Then three runs on Balanced, charger in: 296 passed in 56.99, 55.93 and 56.40 s, with the benchmark at 0.789, 0.785 and 0.797 s just before each run. The slowest measured run is 56.99 s, so the margin to the target is about 3 s. | measured by the builder, 2026-10-13 and 2026-10-14; the benchmark as reference by the owner, 2026-10-14 |

## Conflicts found at the pre-flight

Places where an owner decision of 2026-10-12 meets `SPEC.md`, the plan or existing code. None blocks the build.
Each says how this design reads it.

1. **The adapter in T07, against the plan.** T07's plan text and its requirements (AC-16, AC-25) name no adapter.
   FR-16 is listed only under T04, which is done. T07's gate runs `tests/t07_baseline` only, so registering an
   adapter in `model_interface/providers.py` will not rerun the T04 tests through any gate.
   `DEC-T05-ADAPTER-LATER` expected that the plan might need an added task. Read here as: the T07 decision record
   is the only link. T07 reruns the T04 and T05 suites by hand after registering the adapter, and their real
   output goes into the review evidence. Accepted by the owner.
2. **The world-hash check, against "hidden/ is not opened before outputs are written".** The world hash covers
   the four `hidden/` files. Read here as: the run step checks the manifest's own consistency and every file
   outside `hidden/`; the score step checks the `hidden/` files before it reads the truth. So that a changed
   hidden file is not found only after the calls were made, the same check is a command of its own, run by hand
   before any paid run. The run step still never opens `hidden/`.
3. **"Child processes ended" on abort, against existing code.** `run_child` keeps its process handle to itself
   and `recommend` has no way to cancel, so the harness cannot kill a child in flight without changing T04 or T05
   code. Read here as: on abort no new item is handed off once the fault has been collected, and the harness
   waits for the calls in flight. Each is
   bounded by `(1 + retries) * timeout_s + 10` seconds, 100 with the placeholder settings, and `run_child` kills
   and reaps its own child when it returns. On Ctrl-C the children receive the signal too and come back as
   `child_crash`; those results are thrown away with the aborted run. The bounded wait is accepted by the owner
   and stated under "Honest limits". Killing a child in flight is wave 2.
4. **"Every fault path" through the real child, against existing code.** `truncated_evidence`, and
   `unknown_schema_version` on the payload side, cannot be produced through `recommend`. Read here as: every
   kind that a model or a slow or broken child can cause.
5. **"The report holds numbers only", against AC-24.** AC-24 puts the manifest in the report, and the manifest
   holds the prompt text. Read here as: no reason text and no evidence values in the report.
6. **"One fixed run-output folder", against "T06 commits no run output".** Settled by the owner: in T06 every
   run, the tests and the 5,535-call run, writes outside the repository, and `runs/` stays empty. `runs/` is not
   in `.gitignore`, because T07 commits the baseline's output from it; see "Before committing T06".
7. **Two review policies, against the spec's singular.** NFR-3 says "review policy" and the Metrics section says
   "the active review policy". Read here as: STRICT_FOUR_EYES is the active policy and the headline; "none" is a
   second, labelled computation, and the manifest records both.
8. **Cost per alert without twins, against the Metrics wording.** The spec says: "Cost per alert: the total
   model cost of a run divided by its number of alert-framing items." (`SPEC.md:136`). Read here as: main cost
   over main items, since the spec puts twins outside the 600; twin cost and the total are shown beside it, and
   the literal reading, total cost over all items, is reported as a second figure.
9. **AC-7 and FR-24's "same acceptance suite", against the missing targets.** AC-6 depends on AC-16 targets that
   do not exist until after T07. Read here as: always-escalate fails AC-6 through the not-applicable rule alone.
10. **The pacer's unit.** "Calls per minute" paces hand-offs, one per item. Retried attempts are extra model
    calls, so the real call rate can be higher than the setting.

## Test plan

Gate: `.venv/bin/python -m pytest tests/t06_harness -q -p no:cacheprovider`. It skips the mutation proofs, which run
by hand before completion with `T06_MUTATION=1 .venv/bin/python -m pytest tests/t06_harness/test_mutation.py -q -p
no:cacheprovider` and are recorded as evidence; only the check that every breakage names a guard test that exists runs
in the default gate. Estimated 35 to 45 seconds at the pre-flight, an estimate since replaced by measurement (see the target below and "Decision changes during the build"); the
estimate is from the 0.071-second call measured above and is not a measurement of these tests.

| Tests | What they show | Estimate |
|---|---|---|
| Scoring | Every figure on the full world, 3 framings, 3 runs, in-process, against figures counted independently; every failure kind scored as ESCALATE; NFR-1; spread and nearest-rank percentiles; injection pairs compared within one framing and run; the count of results citing an injected item | 5 s |
| Reference agents and AC-7 | always-close fails AC-1, always-escalate fails AC-6; the parameter-set flag | 1 s |
| Real child | 36 items (one alert per fake outcome) in all framings and each reachable fault path; in-process and real-child results identical; the patched `child_timeout` and the pin of 10 | 8 s |
| No files | the file-open recorder on that sample with its positive control; `hidden/` not opened before outputs are written; the run step does not import `worldgen.truth` | 9 s |
| Parallel | parallel equals sequential, on replies and on fault choices from the fake model; the 1-token stress sum; sorted output | 6 s |
| Dirty run | a run made on a dirty tree is marked and listed, and left out of the three and the spread; a set with two valid runs and one dirty run cannot be a baseline | under 1 s |
| Infrastructure-invalid | a run above the fixture threshold is marked, scored, listed, and left out of the three and the spread; a run of model-caused failures is not marked; a set with two valid runs cannot be a baseline | under 1 s |
| Index | every attempt listed; an aborted run's calls and known cost recorded; total spend adds up | under 1 s |
| Pacer | the fake clock; wait counted as queue time | under 1 s |
| Shutdown | an interrupted run is marked aborted and leaves no child process. Skipped with a clear message where `/proc` is missing | 3 s |
| Manifest and report | every NFR-3 field; the dirty flag; the infrastructure-invalid threshold; no environment variable; hashes; AC-24; refusal of a real run without parameters | 2 s |
| Hidden-file check | the command passes on the committed world and fails on a changed copy made in a temporary folder | under 1 s |
| Output folder | no test writes under the repository; `runs/` does not exist after the suite | under 1 s |
| Cost and modelled time | exact decimals; "not available"; "at least X"; LOW, BASE and HIGH under both policies | 1 s |
| Fake model | the key is unique across 615 bundles; choices do not follow call order | 1 s |
| Mutation proofs | by hand with `T06_MUTATION=1`, recorded as evidence, skipped in the default gate: each deliberate breakage ends the way its entry names, two copies at a time under a 1 GiB memory limit; the limit's own proof; an unnamed ending is not a catch. In the default gate: only the check that every breakage names a guard test that exists, and the switch test | 28.98 s by hand, measured; under 0.5 s in the gate |

The target, set by the owner's judgment on 2026-10-15 and replacing the earlier targets of that day (under 75 seconds,
alarm at 90) and of 2026-10-13 (under 60 seconds, alarm at 80): the slowest of three runs of the gate is under 90
seconds, with an alarm at 100. Genesis kills the gate's test command after 120 seconds by default (genesis-kit
`tools/genesis.mjs:1131`, the default timeout of `genesis gate`; the kill is at `genesis.mjs:1087`), and the memory
guard below also stops a command after a wall-clock limit of 110 seconds. If a run measures above the target, the owner is told before anything is cut.
The gate is run with the charger in, with the owner's performance setting noted beside the timings. Balanced runs
before the change took 61.78 to 65.02 s, so the change is the most likely explanation of the speed-up; four Balanced runs after the change (55.87, 56.99, 55.93 and 56.40 s) are close to the three Turbo runs (56.04 to 56.88 s), so the power mode shows no measurable difference. Before every timed run the charger state is read from
`/sys/class/power_supply/AC1/online` and the fixed benchmark `python3 -I tools/bench_reference.py` is run. On the
build machine it takes about 0.77 to 0.82 s with the charger in; a reading well above that means the machine is
slower than when the recorded timings were taken. The slowest measured run is 85.86 s, so the margin to the target is about 4 s, and about 34 s to the 120-second stop.
The charger check is `tools/power_check.sh`, and a timed run goes through `tools/memory_guard.sh`, which watches the
memory in use and kills the run's process group above 3,000 MB. It also enforces a wall-clock limit,
`MEMORY_GUARD_MAX_SECONDS`, 110 seconds unless set: past it the guard kills the run's process group, says "STOPPED BY
GUARD: the command ran longer than the limit of N s" and exits non-zero (137). `tools/bench_reference.py`, `tools/power_check.sh`
and `tools/memory_guard.sh` are timing aids for the gate on the build machine, not part of the harness: the harness
never imports or calls them, and `tests/t06_harness/test_timing_tools.py` checks the two scripts with harmless dummy
processes only. The memory guard's trigger is the memory in use on the whole machine, not the command's own: a spike
in any other process can stop a healthy timed run, and the guard's output then says that it stopped it. Only the
run's own process group is ever killed. A timed run starts with `tools/timed_run.sh`, which refuses (exit code 2,
nothing started) unless the charger check says exactly "plugged in" and the benchmark exits with 0, prints
N=12000000 and result 983797, and takes no longer than `BENCH_MAX_S` (1.2 s unless set). Its `--unchecked` flag runs
anyway and marks the output "UNCHECKED TIMING"; such a time is not recorded as a gate timing.

Outside the gate: one run set of 5,535 calls through the real child with the fake model, before the independent
review, written to a folder outside the repository.

It is made on the uncommitted tree, so its three runs are dirty runs. It is recorded as "dirty by design: a
full-scale rehearsal of the real-child path, not a baseline". It gives per-run figures only: no spread, and it
counts toward nothing. Its outcome, written here, must include all of:

- a full comparison of every one of its results with the in-process path on the same world and the same fake
  model: identical, with timings removed;
- no child process left when it ends;
- no error: no aborted run and no harness fault.

For the comparison to cover all 5,535 results, the fake's choices in the rehearsal are replies and the faults a
model can raise, which the child turns into results. The three kinds only the parent builds have no in-process
form and are not part of the rehearsal; they stay with the gate's real-child tests.

Result: done. Run on 2026-10-14, charger in and Best performance on, written to `/tmp/t06-rehearsal-20261014-091327`. Dirty by design: a full-scale rehearsal of the real-child path, not a baseline. One run set; three runs of 1,845 items through the real agent process with the test-only fake model and 4 workers, each completed with no abort and no harness fault, in 24.3, 29.7 and 23.7 seconds (77.4 seconds in all, with one in-process run of the same world and fake model). All 5,535 results are identical to the in-process path with timings removed; the calls and the cost of each run equal the in-process run's. Each run gave 1,569 replies without failure and 276 failures: 93 malformed_output, 42 invalid_citation, 39 timeout, 27 missing_citations, 27 model_refusal, 27 unknown_schema_version and 21 provider_error. None was marked infrastructure-invalid. No agent process was left when it ended. Memory in use rose from 1.44 GB to a peak of 1.67 GB; the run process peaked at 70 MB resident.

## Before committing T06

- `git status` must show nothing under `runs/` before anything is staged.
- The 5,535-call rehearsal has been made and its outcome is written into this document: the full comparison
  with the in-process path, no child process left, no error.
- The T04 and T05 suites still pass, run by hand, since the T06 gate does not run them.

## Honest limits

- **No real model has run.** The harness is built and tested against the test-only fake model only: the t06
  gate passes, and the 5,535-call rehearsal through the real child is done ("Result" above).
- **The full world goes through the real child only outside the gate.**
- **No-files is tested on a sample.** It is not enforced on every item.
- **Latency includes child start-up** and, with several workers, contention.
- **Cost is a lower bound** whenever an attempt returned no token counts.
- **Three runs.** The spread is a minimum and a maximum of three values.
- **Excluding infrastructure-invalid runs makes latency and cost look friendlier;** invalid runs are published
  with all their figures.
- **Six TRUE_MATCH alerts per family.** Family figures are counts.
- **Fifteen injection pairs.** Injection divergence is a count.
- **The acceptance check is partial** until AC-16 targets exist.
- **Modelled time is an assumption**, under two policies and three parameter sets, none of them measured.
- **`truncated_evidence` is not reachable through the harness.**
- **Abort waits for calls in flight,** up to 100 seconds each with the placeholder settings. The harness
  cannot kill a child in flight; a hard kill is wave 2.
- **A fault stops new hand-offs only once it has been collected.** With several workers the main thread checks
  for faults before the pacer wait and again immediately before each submit. A worker that fails after the last
  check cannot stop its successor from being submitted, so at most the items already submitted or in the act of
  being submitted still run; their calls are made, and the aborted run is never scored (`DEC-T06-PARALLEL-3`).
  The tests show a fault that comes back during the pacer wait; the window between the last check and
  the submit is not tested.
- **What an interrupt leaves uncounted.** With several workers, a second Ctrl-C gives up the wait: the run is
  still marked aborted, but the calls then in flight are missing from its calls and its known cost, and the
  harness process ends only when they return. With one worker, Ctrl-C cuts the call in flight short; the model
  calls it had finished are counted, one that was under way is not.
- **Ctrl-C is covered from the moment the run is listed until its hand-offs end.** Before the run is listed
  nothing was started and nothing is recorded. After the last hand-off, while the outputs are being written,
  an interrupt is not caught, and the run stays listed as started.
- **The pacer spaces hand-offs, one per item.** A call that retries makes more model calls than the setting.
- **A changed hidden file stops a run only if the check command is run first.** The run step does not look at
  `hidden/`; the check before a paid run is a step done by hand.
- **Thread safety was audited by reading.** The tests show it for the fake model, not for a real adapter.
- **The orphan-process test reads `/proc`.** Where `/proc` is missing it is skipped with a clear message, so
  clean shutdown is then not shown on that system.

## For T07 and wave 2

T07:

- The real provider adapter, the provider, and key handling, with its decision record (`DEC-T06-NO-ADAPTER`).
- Enforcing `timeout_s` and raising `ModelRefusal`, the two limits T05 left for a real adapter.
- An adapter that is safe to call from several threads.
- A rerun by hand of the T04 and T05 suites after the adapter is registered in `model_interface/providers.py`,
  with the real output put into the review evidence. T07's gate runs `tests/t07_baseline` only.
- The hidden-file check command, run before the paid run.
- The default run-output folder `runs/` and the end of the refusal of paths inside the repository; then the
  first output written under `runs/`, and its commit.
- The real price table and the real modelled-time parameter file, committed before the first baseline run.
- The worker count and the pacer setting for the paid run.
- The infrastructure-invalid threshold, set before the paid run (`DEC-T06-INFRA-INVALID`).
- The baseline run set, its published report and the AC-16 targets record.
- Enforcing a written re-run cause. In T06 the manifest holds one only when the owner supplies it.
- Model IDs must be text: the real adapter reports the model ID as text, never as a number (known issue 2 below).
- Both tables sourced: the price table and the modelled-time file of the paid run are both of kind "sourced"
  (known issue 4 below).

Wave 2:

- An operating-system sandbox for the agent process.
- Killing a child process in flight when a run is aborted.
- QA_SAMPLING and the review-policy code (FR-13).
- The spec tension on citation existence (`DEC-T05-CITATIONS`).
- A definition of "spread" and of the percentile method in `SPEC.md`.
- AC-12 as an acceptance check, and the remaining targets of AC-6.
- The audit log and evaluation mode's isolated per-run log (FR-10, FR-14).

Known issues carried forward from T06, none fixed in T06:

1. **Injection divergence has no primary-family cells.** FR-20 (`SPEC.md:34`): "An evaluation harness scores any
   agent configuration on a world and reports every figure defined in the Metrics section, broken down by run, by
   framing and by primary family." The report's injection block (`_injection` in `harness/score.py`) is broken down
   by framing, by cause and by label, and overall, but not by primary family.
2. **Mixed numeric and text model IDs break manifest serialisation.** The manifest's `model.reported` counts the
   reported model IDs as they came. If one run's provider reports some as numbers and some as text, the keys are of
   mixed types and `json.dumps(..., sort_keys=True)` raises `TypeError` when the manifest is hashed or written
   (`harness/manifest.py`). Only text, or only numbers, works.
3. **Inputs the run step accepts but the shared schema refuses.** The run step writes them, and the score step
   then refuses the run: a blank `--rerun-cause` (`rerun_cause` must be non-empty text); a model name of only spaces
   (`Settings` refuses only the empty string; `model.requested` must be non-empty text); a non-finite temperature
   or `timeout_s` (`Settings` accepts NaN and infinity; the schema requires a finite number); and a reported model
   ID that is a non-finite number. A blank reported model ID that is text is accepted by both.
4. **Acceptance `mechanism_only` follows the modelled-time file only.** In a run set's report, `acceptance` is
   marked mechanism-only only when the modelled-time file is a fixture (`harness/score.py`). With a fixture price
   table and a sourced modelled-time file it is not so marked; the report's own `mechanism_only.cost` still says the
   cost figures come from a fixture.
5. **One reference-agent assertion compares the report with itself.** In `tests/t06_harness/test_reference.py`,
   the assertion on the injection block's `overall` takes `divergent`, `by_cause` and `by_label` from the report it
   checks, so only `pairs == 45` and the separate `verdicts_differ == 0` check prove anything there. The divergence
   counts are checked independently on the full world by `test_full_world_injection_figures` in `test_score.py`.
