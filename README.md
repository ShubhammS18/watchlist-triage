# watchlist-triage

An L1 triage agent for sanctions and PEP name-match alerts. For each alert it recommends CLOSE or ESCALATE and cites
its evidence. In the design a human reviewer decides every alert, but that part is not built: **nothing asks a human
yet**. The agent's output is a recommendation that nobody approves (see "What was not built").

All data is synthetic. "True match" (TRUE_MATCH) is a benchmark label I planted in a synthetic world, not a real hit
or a legal determination. I make no claim of regulatory compliance, sufficiency or production fitness.

Why the task matters: Kim and Yang (2024) report, citing earlier industry sources, that false positives make up over
90% of sanctions screening alerts (Frontiers in Artificial Intelligence, doi 10.3389/frai.2024.1374323). The
synthetic world has 90% clear false positives because I set it that way for testing, not because this system
measured it.

## Release 1

Release 1 ran the upgraded agent, frozen in one commit (`fb4ab457ae95`, tag `release-1-freeze`), three times on the
frozen world and three times on a fresh-seed world, and published the result at the tag `release-1` (18 Nov 2026).
The fresh world's seed came from the freeze commit's hash by the documented function; the first try (counter 0) was
accepted, with no rejected try. All six runs were valid and none was replaced. The full record is
`docs/release-log.md`; the figures below are from the committed check outputs, `release/check-frozen.json` and
`release/check-fresh.json`.

- **Frozen world: PASS.** It met every release target.
- **Fresh world: PASS (safety counts only).** The fresh world is judged on the safety counts alone, by the rules
  fixed before the freeze (`DEC-W2-RELEASE-RULES`). It passed them. Its other rates are shown for information and
  were not judged, so this is not a pass on every target.

| Release figure | Target | Frozen world | Fresh world |
|---|---|---|---|
| True matches closed, per run | 0 in every run | 0, 0, 0 | 0, 0, 0 |
| Ambiguous alerts closed, per run | 0 in every run | 0, 0, 0 | 0, 0, 0 |
| Closes without a valid citation set, per run | 0 in every run | 0, 0, 0 | 0, 0, 0 |
| Verdicts changed by injected text, per run | 0 in every run | 0, 0, 0 | 0, 0, 0 |
| Clear false positives escalated | at most 3.9% | 12/4860 (0.25%) | 10/4860 (0.21%), information only |
| Alerts whose three framings agree | at least 1239/1800 | 1788/1800 (99.33%) | 1790/1800 (99.44%), information only |
| Citation accuracy | at least 100% | 4848/4848 | 4850/4850, information only |
| Model cost per alert-framing item | at most USD 0.20 | USD 0.000054 | USD 0.000054, information only |
| Modelled minutes per alert, assisted against manual | assisted lower | 16.06 against 20.00 | 16.02 against 20.00, information only |
| Result | | PASS | PASS (safety counts only) |

The first four rows are the safety counts. The modelled times are at the base settings with every close
second-reviewed. On the frozen world every call left token counts, so its cost needed no assumption. On the fresh
world 2 failed calls left no token counts; each was retried successfully, and its cost is bounded under the stated
assumption that a failed call is billed no more than a successful call with the same input and the full answer
limit.

Release 1's rehearsal and six runs cost USD 0.70, and wave 2 in all cost USD 1.65. These spend figures come from the
Console balances in the release log, which are my readings of the provider's Console, not figures the repository can
check.

## What was not built

I released the evaluation half of the specification first, with the audit log; the operational half waits
(`DEC-W2-SCOPE`). These requirements are not met. They are documented gaps, not dropped requirements, and the
specification is unchanged:

- **FR-8** (pipeline half): a pipeline fault (audit write, L2 enqueue, checkpoint, persistence) keeping an alert not
  final.
- **FR-10** (operational mode): the full alert lifecycle. Only evaluation mode exists.
- **FR-11**: the L2 queue.
- **FR-12**: reviewer approval, rejection and override.
- **FR-13**: the review policies, STRICT_FOUR_EYES and QA_SAMPLING.
- **FR-17**: the reviewer command line and API, including stop.
- **FR-19**: the export of an alert's lifecycle.
- **AC-8**: the tests of the review policies.
- **AC-13** (pipeline half): the pipeline-fault tests.
- **AC-14** (override, rejection, stop): the tests of override, rejection and stop.
- **AC-15**: complete lifecycle records for the operational demo set; the demo set does not exist.
- **AC-18**: the export checked against the audit chain.
- **AC-20** (operational half): an L2 queue record for every escalation in the demo set.

What follows from this:

- **Nothing asks a human yet.** No reviewer sees, approves or overrides a recommendation, and no alert reaches a final
  disposition.
- **There are no reviewer identities yet**, because operational mode was not built. When it is, they will be
  self-asserted: a roster name with no authentication (FR-13).
- **The audit log records the agent's recommendations, not human decisions.** Each evaluation run writes a
  hash-chained log with a checkpoint committed to git (`docs/w2-05-audit-log.md`). It can show that a log was not
  edited, cut or reordered after its checkpoint. It cannot show that the harness or the model told the truth, that a
  run nobody checkpointed never happened, or anything about human decisions, and its anchor is only as strong as the
  public git history.
- **No human spot-check of the reasons was done.** The specification names one as a mitigation for reasons that are
  not supported by the evidence they cite; it has not happened.

## What the evidence does not show

- **Synthetic worlds.** Two worlds, the frozen world and the fresh-seed world, both from my generator. Neither may
  represent real alerts, whose fields are messier.
- **Small samples.** 6 true matches per primary family in each world, too few for a per-family claim.
- **I can see the labels.** I built the world. The agent's loader does not read the hidden label files, but I did
  while building.
- **The rubric is the generator's.** The agent's rules come from the same rubric the generator used to make the
  labels, so a high score shows the rubric can be written as code, not that the agent handles real alerts.
- **The frozen world is not unseen.** The upgrade's second attempt was chosen after its first attempt failed on that
  world.
- **The fresh world tests less than it may seem.** It tests overfitting to the particular planted cases, not my
  assumptions about how to plant them.
- **The seed could have been chosen through the freeze commit.** Anyone could make many freeze commits, look at each
  fresh world and keep the easiest. I tagged and pushed the freeze before making the fresh world, which makes the
  order public, but nothing proves that no other commit was tried privately (`docs/w2-08-release-protocol.md`).
- **No real analyst timings.** The modelled times are assumptions, mostly from vendor claims, with their sources in
  `config/modelled_time.json`; they are not measurements.
- **Three runs show the spread; they do not bound it.** The model runs at temperature 1.
- **Reasons may contain synthetic customer values.** The agent's written reason is free text; it appears in the run
  output (`baseline/`, `w2-02-runs/`, `rehearsal/`, `release/`) and is the one free-text field of the audit log.
- **Closes that rest on reading a note rest on the model's answer**, with no automatic double-check.

Each automated check is narrower than its name:

- **Citations:** the checks test which evidence is cited, not whether the reason is right.
- **Injection:** a pass means no verdict changed; differences in cited evidence are reported but do not decide it.
- **Network isolation:** covers ordinary, accidental and prompt-injected routes from the agent process, name lookups
  included, on Python 3.12.3 on Linux. Deliberately hostile code inside the process is out of scope
  (`docs/isolation-design.md`).
- **Capability allowlist:** shows the outward capabilities equal a reviewed list; that none of them serves account
  actions or regulator reporting rests on reading that list (`docs/w2-06-boundary-checks.md`).
- **World drift:** byte-identical regeneration under Python 3.12 only, on every push and pull request that GitHub
  runs; it does not block a merge (`docs/w2-04-ci-drift.md`).
- **Audit log:** see "What was not built".
- **Release check:** it cannot tell a run ruined by infrastructure from one stopped on purpose, so every run and its
  reason is in the release log; the order of the freeze push and the fresh world rests on the log's evidence and my
  statement.

## How it is evaluated

- A frozen world of 600 alerts: 30 true matches, 30 ambiguous, 540 clear false positives (`docs/world-design.md`).
  The labels are in hidden files the agent's loader does not read.
- Three framings of each alert, differing only in field order, name format and note wording.
- Three runs, because the model's answers vary.
- The modelled-time assumptions were committed before the baseline's first run. The targets were set after the
  baseline and committed before the upgrade and release results. The release rules were fixed before the freeze.
- A fresh session from a different AI provider reviewed each task with a review gate, in review rounds
  (`docs/reviews/`). Some fixes made after a task's last round were checked only by me, for example W2-10's round-4
  wording fixes and the test-code fix after release 1 (`DEC-W2-10-REVIEW`, `DEC-W2-10-TEST-CLONES`).

The release targets are in `targets/release-targets.json`. The over-escalation, framing-agreement and
citation-accuracy targets are no looser than the baseline's measured values (AC-16).

## History: baseline and upgrade

These are earlier run sets on the frozen world, not the release.

- **Baseline** (wave 1; `docs/baseline-report.md`, output in `baseline/`). Claude Haiku 5.5 with one fixed prompt. It
  closed 3 true matches, one per run; one reading of the hidden labels shows all three are one alert carrying
  injected text (`docs/baseline-report.md`, Correction). It also closed 1 ambiguous alert. It escalated
  52.7% of clear false positives (2562/4860), and the framings agreed for 68.8% of alerts (1239/1800). On the
  modelled times assisted review was slower than manual, 71.70 minutes per alert against 20.00.
- **Upgrade** (wave 2; `docs/w2-02-report.md`, output in `w2-02-runs/`). Same model, settings and world. Rules written
  from the rubric decide the alerts the structured fields settle, with no model call. The model sees only the names
  and the notes and answers whether a note links the customer to the listed person; only "no link" closes, and a
  claimed identity counts as a link. Its second attempt met every target, a pass that rested on a stated cost
  assumption (29 Oct 2026). It escalated 0.14% of clear false positives (7/4860), and the framings agreed for 99.6%
  of alerts (1793/1800).

## Running the tests

Run the tests at `main`, not at the `release-1` tag. At the tag, the W2-08 and W2-10 suites build test copies of the
repository that still carry the real release: its tags clash with the ones the tests make, and its committed run
output stops the made-up releases from being built. After the publish I changed only test code, so the copies are
made without tags and without the release's files (`DEC-W2-10-TEST-CLONES`). The release itself did not change.

No test needs an API key; the adapter is tested against a fake local API. Installing pytest needs the network once.
Several suites read the git history, so use a git clone, not a downloaded archive. I run them with Python 3.12, on
Linux (WSL). `tests/w2_07_isolation/` needs unprivileged user namespaces (`unshare -rnm`) on Linux and fails without
them.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
for t in tests/t0*/ tests/w2_*/; do .venv/bin/python -m pytest "$t" -q -p no:cacheprovider; done
```

## Repository map

- `worldgen/`, `data/world/`: world generator and frozen world
- `framings/`, `model_interface/`, `baseline_agent/`, `harness/`: framings, model adapter, agent, harness
- `baseline_run/`, `baseline/`: run wrapper and committed baseline output
- `triage_agent/`, `w2-02-runs/`: upgraded agent and its committed output
- `rehearsal/`, `release/`, `audit/checkpoints/`: release 1's rehearsal, run output and check outputs, and the audit
  checkpoints
- `config/`, `targets/`: settings and release targets
- `tools/`, `trial/`: the drift check and timing aids; the settings and alerts of the T07 trial
- `docs/`, `tests/`: design docs, reviews, evidence; tests per task

`docs/README.md` says which design docs are current. `docs/release-checklist.md` checks each claim above against its
evidence.

## Licence

Apache-2.0 (`LICENSE`).
