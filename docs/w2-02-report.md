# Upgraded agent report (W2-02)

Status: Draft, 29 Oct 2026; review round 2 fixes applied. Run figures come from the committed run output in `w2-02-runs/`
(commit 05f6bbe), byte copies of what the harness wrote, listed in `w2-02-runs/SHA256SUMS`. The runs were made at
commit dbb230e; the agent code is as at 6e93a2e. The pass or fail is the release check's own
(`python -m harness acceptance w2-02-runs 8f4050be…`, `docs/acceptance-design.md`). The bill is the Console's. The
attempt log is `docs/w2-02-attempts.md`.

## In short

- On the frozen world the upgraded agent **met every release target** in three valid runs (run set `8f4050be`):
  no true match and no ambiguous alert closed, and no injection verdict change, in any run or framing. The release
  check's result is **PASS (cost bounded under a stated assumption)**: 2 failed calls left no usage and were
  bounded from their successful retries (see Cost, below).
- It escalated **0.14% of clear false positives** (7/4860), against 52.7% for the baseline and a target of at most
  3.9%.
- The three framings of an alert agreed for **99.6%** of alerts (1793/1800), against 68.8% for the baseline.
- On the modelled review times, assisted review took **15.95 minutes per alert against 20.00** for manual clearing
  (BASE, every close second-reviewed); the baseline took 71.70.
- Model cost was **USD 0.000055 per alert-framing item**, USD 0.30 for the three runs.
- These are results on one synthetic world, whose labels were made from the same rubric the rules are written from.
  The release runs, frozen and fresh-seed, belong to the release task. See Limits.

## What changed

The baseline sent every alert to the model with one prompt. The upgraded agent (`triage_agent/`) changes three
things; `baseline_agent/` is untouched.

1. **Rules decide what the fields settle** (`triage_agent/rules.py`, written from `docs/rubric.md` v1.2 only). The
   decisive identifiers are date of birth and ID number.
   - If a decisive identifier agrees, or none conflicts, the alert is escalated, citing the decisive items present.
   - If a decisive identifier conflicts, none agrees and there is no note, the alert is closed, citing the
     conflicting items on both sides.
   - These decisions make no model call. Per framing on the frozen world: 67 items escalated by rule, 252 closed
     by rule, 296 to the model (alerts and control twins).
2. **The model reads only the notes.** For the remaining items, whose close depends on reading a note, the model
   sees the names as recorded and the quoted notes, never the decisive fields. It answers one question: does a note
   link the customer to the listed person? LINK and UNSURE escalate, citing the notes; only NO_LINK closes, citing
   the conflicting decisive items. An unreadable answer or a failed call escalates as a system failure, never closes.
3. **A claimed identity is a link.** The question states that any note claiming the customer is the listed person
   is a LINK, whatever its source or how reliable it seems. This was attempt 2's one change, after attempt 1 closed
   the control twin of an injected alert once on that kind of note.

A static test reads the agent's source and checks three things: every import statement of each module names a module
on that module's list, so none names the world generator; no module has a name or attribute spelled importlib,
`__import__`, `exec`, `eval` or `__builtins__`; and no module's source holds a generator string of 20 characters or
more or a note text of the frozen world. Nothing is checked at run time, so it does not show that no import happens
at run time, and it does not check short fragments, text put together from pieces, or notes the generator would
write on another seed. The manifest records the prompt
hash (`1740d71e…`) and a hash of the rule code (`1c964fd8…`), and the run-set ID includes both; the release check
confirms they agree. The rule-code hash covers the triage package's own decision files (`rules.py`, `recommend.py`,
`child.py`, `prompt.py`); the shared baseline modules it also uses are pinned by the clean commit among the run-set
inputs. Model, temperature and every other run setting are the baseline's (`config/run-triage.json`
differs from `config/run.json` only in the agent).

## Attempts and practice runs

An attempt is one change and one three-run set on the frozen world; the limit was six. Practice runs used a
separate world (seed 20261027), kept outside the repository, and do not count as attempts.

| # | Date | Change | Run set | Result | Spend USD |
|---|---|---|---|---|---|
| 1 | 28 Oct 2026 | rules first; the model asked only whether a note links the customer to the listed person | `1c8d128b` | NOT ELIGIBLE at the time (4 failed calls left no token counts); re-judged under the later cost rule: FAIL on injection verdict divergence only (0/1/0) | 0.28 |
| 2 | 29 Oct 2026 | a claimed identity is a LINK, whatever its source | `8f4050be` | **PASS (cost bounded under a stated assumption)**, 2 calls bounded | 0.30 |

| Date | Change | Run set | Key figures | Spend USD |
|---|---|---|---|---|
| 27 Oct 2026 | rules first; the rest to the model with the baseline prompt | `5eed2587` | over-escalation 27.10%; consistency 85.17%; injection divergence 4/45 | 0.17 |
| 28 Oct 2026 | the note-only question (attempt 1's design) | `649f1615` | over-escalation 0.25%; consistency 99.33%; injection divergence 0/45 | 0.10 |
| 29 Oct 2026 | a claimed identity is a LINK (attempt 2's design) | `5549c8f8` | over-escalation 0.06%; consistency 99.83%; injection divergence 0/45 | 0.10 |

Wave-2 spend so far: USD 0.95 (attempts 0.58, practice 0.37), from the Console, against a ceiling of 25.00.

## Results: attempt 2 beside the baseline

Frozen world, Claude Haiku 5.5, three runs of 600 alerts and 15 control twins in three framings. Per-run values are
runs 1/2/3; rates are pooled over the valid runs.

| Target | Release target | Attempt 2 (`8f4050be`) | Baseline (`f2e614d2`) |
|---|---|---|---|
| True matches closed | 0 in every run and framing | 0/0/0 | 1/1/1 |
| Ambiguous alerts closed | 0 in every run and framing | 0/0/0 | 0/0/1 |
| Closes without a valid citation set | 0 in every run | 0/0/0 | 0/0/0 |
| Injection verdict divergence | 0 in every run and framing | 0/0/0 of 45 | 5/4/5 of 45 |
| Over-escalation of clear false positives | at most 3.9% | 7/4860 = 0.14% (2/3/2) | 2562/4860 = 52.72% |
| Verdict consistency across framings | at least 1239/1800 | 1793/1800 = 99.61% | 1239/1800 = 68.83% |
| Citation accuracy | 100% | 4853/4853 | 2298/2298 |
| Cost per alert-framing item | at most USD 0.20 | USD 0.000055 | USD 0.000187 |
| Modelled time, BASE, every close second-reviewed | assisted below manual | 15.95 against 20.00 | 71.70 against 20.00 |
| Release check | | PASS (cost bounded under a stated assumption) | FAIL (5 targets) |

More detail on attempt 2:
- **Injection.** 0 of 135 alert-and-twin pairs differed in verdict and 0 in citations. The noise control (each
  control twin against itself across runs) gave 0 of 135 in both. The two alerts whose notes claim the customer is
  the listed person were answered LINK in every run and framing, as was the one control twin of that kind.
- **The 7 escalated clear false positives** came from 5 alerts: one answered UNSURE in framing 1 of every run, three
  answered UNSURE once, and one failed once on an unreadable answer and escalated as a system failure. These are
  also the only items behind the lost consistency.
- **Cost.** Known cost USD 0.000054388 per item, plus a bound of 0.000000120 for two calls that failed with a provider
  error and left no token counts, both retried successfully. The bound is under a stated assumption, not a proof:
  that a failed call is billed no more than its successful retry's input and the full answer limit
  (`DEC-W2-01-ELIGIBILITY-3`). Because the pass rests on it, the release check labels the result PASS (cost bounded
  under a stated assumption), not PASS (`DEC-W2-01-PASS-LABEL`); a plain PASS needs every call to report its usage.
  This task accepts the labelled pass only with the owner's sign-off, in the attempt log, that the Console total
  matches the harness's cost. The harness's own cost for the three runs is USD 0.2998; the Console showed USD 0.30
  (balance 4.86 before run 1, 4.56 after run 3).
- **Modelled time, the other five settings** (assisted against manual, minutes per alert): BASE with no second
  review 14.16 against 20.00; HIGH 58.12 and 53.62 against 78.00; LOW 5.45 and 4.55 against 7.00. Assisted was lower
  in all six.

## Limits

- **One synthetic world.** These figures are for the frozen synthetic world only, which may not represent real
  alerts.
- **The fresh-seed release test has not been run.** It belongs to the release task, as do the release runs on the
  frozen world.
- **The rules come from the same rubric that made the labels.** In the words of `DEC-W2-02-RULES-FIRST`: "Because
  the generator used the same rubric to make the labels, a high score on synthetic worlds shows that the rubric can
  be written as code and that the model is used narrowly; it does not show that the agent handles real alerts,
  whose fields are messier. The fresh-seed test does not remove this limit, since the same generator builds it."
- **A wrong reading of a note can recommend a close.** Closes that depend on reading a note rest on the model's
  answer, with no automatic double-check; one such error occurred in attempt 1 (on a control twin), none in attempt
  2 (`DEC-W2-02-MODEL-READING-RISK`; a test shows the behaviour with a scripted wrong answer). In the operational
  design, an L1 reviewer approves every proposal before it is final. Under the default four-eyes policy a second
  reviewer also confirms every close; under QA sampling only a sample of closes gets that second check. Escalations
  go to L2. Operational mode is not built yet, so none of this review was part of these evaluation runs.
- **Citation accuracy checks the cited IDs**, not whether the written reason is right.
- **Temperature 1.** The provider fixes it for this model, so the same item can get different answers in different
  runs. Three runs show the spread; they do not bound it. Over-escalation and consistency moved between runs (2 to 3
  items, 597 to 598 alerts); a zero in three runs is not a proof of zero.
- **Modelled times are assumptions**, mostly from vendor sources (`config/modelled_time.json`), not measurements.
- **Two attempts on one world.** Attempt 2's change was chosen after seeing attempt 1's failure on this world, so
  the frozen world is no longer unseen by the design.
- **Alerts are not named here.** The figures count items by run and framing; the item lines in `w2-02-runs/` hold
  each answer.
