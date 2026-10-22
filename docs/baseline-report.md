# Baseline report (T07)

Status: draft for review, 22 Oct 2026. Run figures come from the committed run output in `baseline/`
(commit f580c1b), byte copies of what the harness wrote, listed in `baseline/SHA256SUMS`. The runs were made at
commit 229362c. The trial figures come from `docs/evidence/t07/trial/trial-results.json`, the break-even shares are
derived from `config/modelled_time.json`, and the bill is the Console's. Evidence for the checks named below is in
`docs/evidence/t07/`.

## Supersedes

The T04, T05 and T06 design docs stay as they were when their tasks closed. These lines in them are out of date;
this report and the code describe the current state. `docs/README.md` indexes all design docs.

| Line | What it says | Now |
|---|---|---|
| `docs/model-interface-design.md:46` | T04 has no real provider adapter, no SDK and no keys | `model_interface/anthropic_api.py` is a real adapter for the Anthropic Messages API (standard library only), registered as `anthropic`; the key comes from one environment variable |
| `docs/model-interface-design.md:174-175` | Stub only; swapping to a real provider by configuration is not tested | With the adapter registered (one entry in `providers.py`), the baseline switched to Claude Haiku 5.5 by configuration alone (`config/model.json`), and the T04 registry test now expects both providers |
| `docs/baseline-agent-design.md:12-14` | The agent has only run against the stub; no adapter, no baseline numbers | The agent ran 5,535 items against Claude Haiku 5.5; the numbers are below |
| `docs/baseline-agent-design.md:300` | No real model has run; no baseline numbers | As above |
| `docs/harness-design.md:30-31` | The harness has only been planned against a test-only fake model; the adapter comes in T07 | The harness ran the baseline with the real adapter; the harness itself still holds no provider code |
| `docs/harness-design.md:134-135` | T07 adds a default `runs/` folder inside the repository and lifts the refusal of paths inside it | Not done. Runs were written outside the repository, as in T06, and then copied byte for byte into `baseline/` with a SHA-256 list. There is no `runs/` folder |
| `docs/harness-design.md:635` | No real model has run; the harness is tested against the fake model only | Three real runs were made and scored |
| `docs/harness-design.md:681-682` | T07 adds the default `runs/` folder and commits the first output under it | Replaced by the copy into `baseline/` |

## In short

- **The baseline missed 3 true matches** over the three runs: one in each run, every time in the second framing
  and in the common-name family. A missed true match is a sanctions or PEP hit the agent recommended closing. The
  release must miss none, in every run and every framing.
- It closed **1 alert that was ambiguous by design** (run 3). The release must close none.
- It escalated **52.7% of clear false positives**. Under the modelled review times this makes
  agent-assisted review slower than manual review in every parameter set and review policy: at BASE with every close
  second-reviewed, 71.70 minutes per alert against 20.00 for manual clearing. To save time it would
  have to escalate fewer than about 3.95% of them (derived, below).
- When it closed a clear false positive, it cited supporting evidence **every time** (2298/2298), and every close
  in every run passed the automatic citation check.
- The same alert got the same verdict in all three framings for **68.8%** of alerts.
- Model cost was **0.000187 USD per alert** (1.0369551 USD for all three runs), and the Console bill is within about 0.3% of it.

## What was run

| | |
|---|---|
| Agent | The naive baseline agent: one fixed prompt, one call per alert-framing item, CLOSE or ESCALATE with a reason and cited evidence IDs; any fault of the model or the agent process fails closed to ESCALATE |
| Model | Claude Haiku 5.5, requested as `claude-haiku-5-5`; Anthropic reported `claude-haiku-5-5` for all 5,535 calls |
| Provider | Anthropic Messages API, through `model_interface/anthropic_api.py`; no SDK, no tools, no streaming, no batch API |
| Temperature | 1. Claude Haiku 5.5 accepts no other value, so it is sent explicitly and recorded as 1. The baseline is therefore not deterministic, which the three runs show (see the spread below) |
| Thinking | Off. Every request sends `thinking: {"type": "disabled"}`. It is pinned in `config/model.json` under `options`; the manifest records that file's hash (`4ec986f2718c...`) among the run-set inputs, not the setting itself. The adapter refuses any other value |
| Answer size | max_tokens 512; the largest answer in the trial was 232 tokens |
| Timeouts and retries | 30 s per call: one deadline for sending and reading; connecting is bounded only by the agent's 100 s child limit; the agent retries a timeout or provider error 2 times with no backoff; the adapter itself never retries. No call needed a retry |
| Load | 4 workers, at most 120 hand-offs per minute; about 16 to 17 minutes per run |
| Validity rule | A run is invalid for infrastructure reasons if more than 2% of its items end in a timeout or provider error. No run had any |
| World | The frozen synthetic world (hash `b77a6804a52b...`): 600 alerts in three framings, plus 15 control twins in three framings, so 1,845 items per run |
| Prompt | The fixed T05 prompt, hash `0c2538b80f10...` |
| Tables | Price table `config/prices.json` and modelled-time file `config/modelled_time.json`, both sourced; their hashes are in every manifest |
| Runs | Three, at commit 229362c with a clean tree, all with identical inputs: run set `f2e614d2`. All three are valid; the set is eligible as a baseline. The output folder's index lists no aborted or repeated run |

The modelled-time file was committed on its own (1f06342) before any paid call, trials included; it is an ancestor of
the run commit and its hash matches every manifest. The hidden files of the world were checked against the world
manifest before the runs. All run output was scanned with gitleaks, built-in rules only: no leaks.

## Results

Pooled over the three valid runs (numerators and denominators summed), with each run's own value (runs 1 / 2 / 3)
and the lowest and highest. Rates are over main items, the 600 alerts in each of three framings.

| Figure | Pooled | Run 1 / 2 / 3 | Min | Max |
|---|---|---|---|---|
| Missed true matches (true matches recommended CLOSE; a count, never a rate) | 3 | 1 / 1 / 1 | 1 | 1 |
| Ambiguous-by-design alerts closed | 1 | 0 / 0 / 1 | 0 | 1 |
| Over-escalation: clear false positives escalated, failures included | 2562/4860 = 52.72% | 859/1620 = 53.02% / 850/1620 = 52.47% / 853/1620 = 52.65% | 52.47% | 53.02% |
| of which genuine escalations by the model | 2559/4860 = 52.65% | 858/1620 = 52.96% / 849/1620 = 52.41% / 852/1620 = 52.59% | 52.41% | 52.96% |
| of which failures, over the same items | 3/4860 = 0.06% | 1/1620 = 0.06% / 1/1620 = 0.06% / 1/1620 = 0.06% | 0.06% | 0.06% |
| failures over the escalations alone | 3/2562 = 0.12% | 1/859 = 0.12% / 1/850 = 0.12% / 1/853 = 0.12% | 0.12% | 0.12% |
| Verdict consistency: alerts whose three framings agree | 1239/1800 = 68.83% | 412/600 = 68.67% / 418/600 = 69.67% / 409/600 = 68.17% | 68.17% | 69.67% |
| Citation accuracy: closes of clear false positives citing the supporting evidence | 2298/2298 = 100.00% | 761/761 = 100.00% / 770/770 = 100.00% / 767/767 = 100.00% | 100.00% | 100.00% |
| Citation existence: answers whose cited IDs are all in what was sent | 5396/5396 = 100.00% | 1799/1799 = 100.00% / 1799/1799 = 100.00% / 1798/1798 = 100.00% | 100.00% | 100.00% |
| Citation precision (information only) | 6654/13862 = 48.00% | 2206/4609 = 47.86% / 2230/4643 = 48.03% / 2218/4610 = 48.11% | 47.86% | 48.11% |
| Failures (all were unreadable answers) | 4 | 1 / 1 / 2 | 1 | 2 |
| Invalid citations | 0 | 0 / 0 / 0 | 0 | 0 |
| Missing citations | 0 | 0 / 0 / 0 | 0 | 0 |
| CLOSE verdicts | 2302 | 762 / 771 / 769 | 762 | 771 |
| ESCALATE verdicts | 3098 | 1038 / 1029 / 1031 | 1029 | 1038 |
| Latency, model call, median (s) | 1.636 | 1.668 / 1.631 / 1.616 | 1.616 | 1.668 |
| Latency, model call, p95 (s) | 2.553 | 2.765 / 2.521 / 2.357 | 2.357 | 2.765 |
| Latency, item, hand-off to checked result, median (s) | 1.674 | 1.708 / 1.669 / 1.653 | 1.653 | 1.708 |
| Latency, item, hand-off to checked result, p95 (s) | 2.594 | 2.804 / 2.558 / 2.394 | 2.394 | 2.804 |
| Closes re-checked for a valid citation set: violations | 0 of 2302 | 0 of 762 / 0 of 771 / 0 of 769 | 0 | 0 |
| Injected-text pairs (alert and its control twin, per run and framing) that diverged | 69 of 135 | 25 of 45 / 20 of 45 / 24 of 45 | 20 | 25 |
| of which the verdict differed | 14 | 5 / 4 / 5 | 4 | 5 |
| Answers citing the injected item | 1 | 0 / 0 / 1 | 0 | 1 |
| Control-twin closes re-checked: violations | 0 of 24 | | | |

Where runs tie, the report keeps the first run's fraction as the minimum or maximum; the percentages above are the
values. Citation accuracy is 100% in each run (761/761, 770/770, 767/767). Of the
69 pairs that diverged, 14 got a different verdict and 55 differed only in which items
they cited; none diverged because one side failed.

By framing (pooled over the three runs; 1,800 items each):

| Framing | Missed true matches | Ambiguous closed | Over-escalation | Citation accuracy | Failures | CLOSE / ESCALATE |
|---|---|---|---|---|---|---|
| 1 | 0 | 1 | 900/1620 = 55.56% | 720/720 | 2 | 721 / 1079 |
| 2 | 3 | 0 | 840/1620 = 51.85% | 780/780 | 1 | 783 / 1017 |
| 3 | 0 | 0 | 822/1620 = 50.74% | 798/798 | 1 | 798 / 1002 |

By primary family (pooled; "none" is the 420 plain alerts):

| Family | Items | Missed true matches | Ambiguous closed | Over-escalation | Verdict consistency | Citation accuracy | Failures |
|---|---|---|---|---|---|---|---|
| common name collisions | 378 | 3 | 1 | 119/270 = 44.07% | 86/126 = 68.25% | 151/151 | 0 |
| contradictory evidence | 108 | 0 | 0 | no clear false positives | 36/36 = 100.00% | not applicable | 0 |
| name variants | 378 | 0 | 0 | 168/270 = 62.22% | 95/126 = 75.40% | 102/102 | 1 |
| none | 3780 | 0 | 0 | 1961/3780 = 51.88% | 835/1260 = 66.27% | 1819/1819 | 3 |
| pep status | 378 | 0 | 0 | 165/270 = 61.11% | 96/126 = 76.19% | 105/105 | 0 |
| thin identifiers | 378 | 0 | 0 | 149/270 = 55.19% | 91/126 = 72.22% | 121/121 | 0 |

The report gives the same figures for secondary families of true matches separately; they are never added into the
totals above.

## Modelled review time

These are labelled assumptions, not measurements: minutes of analyst effort per alert, from public sources that are
mostly vendor claims (`config/modelled_time.json` gives a source or a stated assumption for each value). Manual
review clears every alert by hand and sends the 60 that must escalate to L2. Assisted review reads each proposal,
sends every ESCALATE to L2, and, under "every close second-reviewed", has a second analyst check each CLOSE.
Each run and framing is worked out on its own and then averaged.

| Set | Manual clearing, proposal review, L2, second review (min) | Manual per alert | Assisted, every close second-reviewed: pooled (min to max) | Assisted, no second review: pooled (min to max) | Assisted faster? |
|---|---|---|---|---|---|
| LOW | 3, 0.5, 40, 1 | 7.000000 | 23.874444 (23.795000 to 23.990000) | 23.448148 (23.366667 to 23.566667) | no, in neither policy |
| BASE | 8, 2, 120, 2 | 20.000000 | 71.697037 (71.456667 to 72.046667) | 70.844444 (70.600000 to 71.200000) | no, in neither policy |
| HIGH | 30, 5, 480, 5 | 78.000000 | 282.509259 (281.541667 to 283.916667) | 280.377778 (279.400000 to 281.800000) | no, in neither policy |

Escalating everything would not beat manual clearing in any set either. BASE was chosen on the side that makes the
agent's saving harder to show.

## Break-even escalation share (derived)

This figure is derived from the modelled-time assumptions above, not measured. It answers: if the agent escalated
every true match and every ambiguous alert (all 60, as it must) and some share of the 540 clear false positives,
how large could that share be before assisted review stops being faster than manual review? Below the break-even
share, assisted review is faster; at it, the two are equal. Each extra wrong escalation adds an L2 review and, when
closes are second-reviewed, removes one second review. The time is linear in the counts, so averaging over runs and
framings does not change the share. The last column gives the same point as a share of all 600 alerts escalated.

| Set | Policy | Break-even, clear false positives escalated | Largest whole count still faster | Same point, all alerts escalated |
|---|---|---|---|---|
| LOW | every close second-reviewed | 24.62 of 540 = 4.56% | 24 = 4.44% | 14.10% |
| LOW | no second review | 37.50 of 540 = 6.94% | 37 = 6.85% | 16.25% |
| BASE | every close second-reviewed | 21.36 of 540 = 3.95% | 21 = 3.89% | 13.56% |
| BASE | no second review | 30.00 of 540 = 5.56% | 29 = 5.37% | 15.00% |
| HIGH | every close second-reviewed | 25.89 of 540 = 4.80% | 25 = 4.63% | 14.32% |
| HIGH | no second review | 31.25 of 540 = 5.79% | 31 = 5.74% | 15.21% |

The baseline escalated 52.72% of clear false positives, more than seven times even the largest break-even share (6.94%,
LOW with no second review), and more than thirteen times the BASE share under every close second-reviewed.

## Cost and the billing check

Cost is worked out from the token counts Anthropic reported for each call and the dated price table in every
manifest (USD 0.10 per million input tokens and 0.50 per million output tokens, read 19 Oct 2026). Every call
reported its token counts and had a price, so no figure here is a lower bound.

| | Pooled | Run 1 / 2 / 3 |
|---|---|---|
| Cost per alert (main items) | 3371461/18000000000 USD, about 0.0001873 | 0.0001877 / 0.0001871 / 0.0001871 |
| Main items | 1.0114383 USD | |
| Control twins | 0.0255168 USD | |
| All items | 1.0369551 USD | 0.3463892 USD / 0.3452872 USD / 0.3452787 USD |

Billing check: the Anthropic Console showed USD 1.04 for the run key, against the harness's 1.0369551, about 0.3%
apart once the Console's rounding to cents is allowed for; the rule was to investigate a gap above 5%. The trial's
0.0035544 shows as 0.00 in the Console. Total model spend for the task, trial and runs: USD 1.0405095. The key
check before each run uses Anthropic's token-counting endpoint, which Anthropic documents as free (token-counting page, read 20 Oct 2026).

## Trial

Before the counted runs, the same agent and settings ran once on 21 hand-written alerts shaped like the world's
but not taken from it (`trial/alerts.json`), with a separate key. Every pre-declared check passed, so no setting
changed:

- every answer was readable, none was refused, and every call reported `claude-haiku-5-5`;
- the 99th-percentile latency was 3.74 s (limit 10 s), so the 30-second timeout stayed;
- the largest answer was 232 output tokens, none reached the 512 cap, so max_tokens stayed at 512;
- 18 of 21 answers matched the hand-written expected answer: all 12 that should escalate did, and 3 of 9
  that should close were escalated. This was information only; no setting was tuned on it;
- cost USD 0.0035544; gitleaks found nothing in the output.

## Limits

- **Vendor-sourced times.** Most modelled-time values come from vendor marketing material, two parameters rest on
  stated assumptions with no public source, and the L2 sources describe general AML alert investigation, not
  screening escalations specifically. No analyst interviews were possible. The time figures and the break-even
  shares inherit all of this.
- **Temperature 1.** The provider fixes it for this model, so the same alert can get different answers in different
  runs. Three runs show the spread; they do not bound it.
- **One world.** These figures are for the frozen synthetic world only. The fresh-seed world comes later.
- **Byte order of the set report.** The harness rewrites the run set's report every time it scores. Scoring from
  the run command and from the score command orders the runs differently, and where runs tie on a figure the
  minimum or maximum shown is the first run's fraction; in the one pair compared, the files differ in bytes but in no
  value.
  `baseline/` holds the version the score command wrote. (`docs/evidence/t07/known-issues.md`, issue 3.)
- **One stall of an earlier test.** During the hand reruns of the earlier suites, one T04 isolation test once took
  more than its 5-second limit inside a copy of the code, and it did not recur in five further runs. The cause is
  unconfirmed. (`docs/evidence/t07/known-issues.md`, issue 1.)
- **The reports say no targets exist.** Each run's report and the set report contain an acceptance block whose
  citation-accuracy line says it is not determined because no target exists yet. The harness never reads the
  targets file, so that line will stay as it is in these committed reports after the targets are recorded; the
  targets record is the place to read them.
- **Injected text.** In 14 of 135 alert-and-twin pairs the verdict differed. At temperature 1 the same alert can
  change verdict by chance, so these runs cannot separate the effect of the injected text from sampling noise. The
  harness also gives no breakdown of injection results by primary family (a known harness issue).
- **Missed alert not named here.** The report counts missed true matches by run, framing and family but does not
  name the alert; finding it needs the hidden labels, which this report does not open.
- **The wrapper's cost estimate.** The run cost the wrapper prints before a run (USD 0.8509) is an upper bound for
  one attempt per item only if no prompt byte becomes more than one token, which held in the trial (2.39 to 2.57
  bytes per token); every answer is counted at the 512-token cap, and retries are not counted. The runs cost about 0.35 each.
- **Key check hardened after the runs (review round 1).** The wrapper's key check followed HTTP redirects, which could
  carry the key to another host, and the wrapper accepted a local address; it now accepts only
  `https://api.anthropic.com` and refuses any redirect. Every run and the trial were aimed at Anthropic's default
  address (neither `config/model.json` nor `trial/model.json` sets one). The trial used only the adapter, which never
  follows redirects. The old wrapper key check could have followed a redirect from that address, so exposure of the
  run key cannot be ruled out from these files; both keys were revoked after the fix. Since the run commit, the
  agent, the harness and the adapter's behaviour are unchanged; the wrapper's pre-run checks and comments, the
  adapter's and the trial script's comments, and the T07 tests and docs changed.

## What the release must fix

- Miss no true match, in any run or framing. The baseline missed one per run, always in the second framing of the
  common-name family.
- Close no ambiguous-by-design alert. The baseline closed one.
- Escalate far fewer clear false positives: from about 53% to below the break-even share, so that assisted review is
  faster than manual review. Under BASE with every close second-reviewed that means below about 3.95%.
- Give the same verdict in all three framings much more often than 69% of alerts.
- Show that injected text does not change verdicts, separated from sampling noise.
- Keep what already works: supporting citations on every close of a clear false positive, a valid citation set on
  every close, and a cost per alert of well under a cent.

The numeric targets for over-escalation, verdict consistency, citation accuracy and cost per alert come from the
rules fixed before the runs and are recorded next, in their own decision record and `targets/release-targets.json`.
This report sets none.

## Traceability

AC-1, AC-5 and AC-6 are release acceptance checks: the baseline is measured against them and is not required to pass them.

| Requirement | Where it is met or shown |
|---|---|
| FR-16 | Model swapped by configuration alone: `config/model.json`, `model_interface/anthropic_api.py` |
| FR-20, FR-21 | Figures by run, framing and primary family: Results. The injection figures have no primary-family breakdown (Limits) |
| FR-22, AC-25 | Modelled review time and its parameters; parameters committed in 1f06342 before the first paid call: What was run, Modelled review time |
| NFR-1 | Missed true matches reported as their own count: In short, Results |
| NFR-3 | Manifests in `baseline/<run>/manifest.json`: What was run |
| NFR-6 | Cost from reported tokens and the dated price table: Cost and the billing check |
| AC-1, AC-5 | Measured, not required of the baseline: 3 missed true matches, 1 ambiguous alert closed |
| AC-2 | Met: 0 violations over all closes |
| AC-6 | Measured, not required of the baseline: assisted time is not lower than manual in any set; the reports' citation-accuracy line reads "not determined: no AC-16 target exists yet" (Limits) |
| AC-16 | Targets not set here; they follow in their own record |
| AC-24 | Each run's own report in `baseline/<run>/report.json` |
