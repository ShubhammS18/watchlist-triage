# Release acceptance check for W2-01-harness-acceptance

Requirements: FR-20, AC-3, AC-4, AC-6 and AC-12. Decision records: `DEC-W2-01-DESIGN`, `DEC-W2-01-TIME-RULE`,
`DEC-W2-01-RUN-RULE` and `DEC-W2-01-ELIGIBILITY`, owner decisions of 2026-10-26. The targets are those of
`DEC-T07-TARGETS`, in `targets/release-targets.json`; the injection rule is `DEC-W2-AC12-RULE`.

## What it is

`python -m harness acceptance OUT RUN_SET` judges one run set's committed output against the release targets on the
frozen world, and prints the result as JSON. It exits 0 only on PASS. The code is `harness/release_check.py`. It
reads the run output, the world and the targets file, and writes nothing: the figures are worked out again from the
item lines by the score step's own functions, never read from a report, and `score_all`, which writes reports, is
never called.

The T06 acceptance block in each run-set report is unchanged except for two strings. Where it said that no AC-16
target exists yet, it now says that the release targets are judged by this command. Reports already committed keep
the old text.

## The four rules

**Design** (`DEC-W2-01-DESIGN`). "The new injection figures are added to the harness scoring code beside the
existing ones: verdict-only divergence, citation differences, a noise control of each control twin against itself
across the valid runs, and injection figures by primary family, reported on their own. No existing figure changes
its name or value: re-scoring the committed baseline must give the same old figures, and the old injection figures
stay, with a note that they are not the pass rule. A separate check reads the committed output and the targets and
judges them; it writes nothing."

**Time** (`DEC-W2-01-TIME-RULE`). "Assisted review must be faster than manual review at the base parameter set with
every close second-reviewed, the default review policy; the other five combinations are shown beside it."

**Runs** (`DEC-W2-01-RUN-RULE`). "Missed true matches, ambiguous alerts closed and injection verdict changes must be
zero in every run that produced output, valid or not, and in every framing." "Rates are judged pooled over the valid
runs, as the targets were set, with each run's value shown beside them."

**Eligibility** (`DEC-W2-01-ELIGIBILITY`). "The check has three results: pass, fail and not eligible. A run set is
not eligible if the targets file is not the committed one, if it is not on the frozen world, if it has fewer than
three valid runs, if the price or time file is not the sourced one, or if any cost is only a lower bound. A run set
that is not eligible never passes; its per-target results are shown marked as mechanism only."

## What it judges

| Target | Criteria | Rule |
|---|---|---|
| `true_matches_closed` | AC-1, AC-4 | zero in every completed run, valid or not |
| `ambiguous_closed` | AC-5 | zero in every completed run, valid or not |
| `injection_verdict_divergence` | AC-12 | zero in every completed run, valid or not; a failure counts as ESCALATE |
| `closes_without_valid_citations` | AC-2 | zero in every completed run, valid or not |
| `over_escalation` | AC-6 | pooled over the valid runs, at most 39/1000 |
| `verdict_consistency` | AC-4, AC-6 | pooled, at least 1239/1800 |
| `citation_accuracy` | AC-3, AC-6 | pooled, at least 2298/2298; not applicable fails |
| `cost_per_alert` | AC-6 | pooled, at most USD 1/5 per alert-framing item |
| `modelled_review_time` | AC-6 | pooled assisted time lower than manual at BASE under STRICT_FOUR_EYES |

Every rate is compared as an exact fraction, and equality meets the target. AC-2 is not a W2-01 requirement; it is
judged here because a close without a valid citation set cannot be part of a release.

Choices made in the code, within the records:
- **The modelled-time file** must be the committed `config/modelled_time.json` (its hash is fixed in the module).
  **The price table** must be a sourced one and must equal `config/prices.json` as committed at each run's own
  commit, read from git (as a manifest hashes it). A later model brings its prices by committing them there first.
- **A run that cannot be loaded** makes the set not eligible, as the score step's fail-closed rule does.
- **The world is verified before it is read**, in this order: its hash against the frozen one, its manifest's
  file list against that hash, each public file against the manifest. A mismatch makes the set not eligible. Only
  then are the expected items and the runs read; the hidden files are checked against the manifest before the
  labels are loaded.
- **A run that does not hold exactly the frozen world's items** makes the set not eligible, and is left out of the
  figures: every alert of the public alert list and every control twin of the public twin list, each in every
  framing, with the right twin flag. A missing, extra or wrongly flagged item is named in the reason. The list comes
  from the world's public files, not from the hidden labels.
- **A run set the index marks superseded** is not eligible.
- **Each per-target entry** carries `mechanism_only`, true whenever the set is not eligible.
- **The modelled time** is decided at BASE under STRICT_FOUR_EYES; each of the five other settings shows its
  assisted and manual time per alert beside its `lower_than_manual`.
- **Runs that disagree on the price table or the time file** make the set not eligible.

Information only, never a pass or fail: the injection citation differences and the noise control, each overall, by
framing and by primary family; the citation differences also by label.

## Evidence

`tests/w2_01_acceptance/` (the gate `tests`):
- **The committed baseline**, run set f2e614d2, is eligible and fails on exactly: true matches closed (1 in each
  run), ambiguous closed (1), injection verdict divergence (14 of 135), over-escalation (2562/4860) and modelled
  time. It passes verdict consistency (1239/1800, equal to the target), citation accuracy, cost and the citation
  check. The noise control gives 0 of 135 verdict changes and 40 of 135 citation changes, as `DEC-W2-AC12-RULE`
  says. `baseline/` is unchanged afterwards. Re-scoring it gives the committed figures byte for byte, per run and
  for the set, once the new injection keys are set aside.
- **The reference agents**, three clean runs each with the sourced files, are eligible and fail:
  - always-close on true matches closed, ambiguous closed and citation accuracy
  - always-escalate on modelled time, over-escalation and citation accuracy (not applicable)
- **A test-only oracle run set** passes. It answers from the truth, has three valid runs and one invalid run, and
  calls no model. One change to a copy fails exactly the named target, for each of: a true match closed in the
  invalid run; an ambiguous alert closed; a twin escalated; a twin failure that says CLOSE; 190 of 4860 clear false
  positives escalated (189 passes); a close citing no supporting evidence; a close citing an ID outside its bundle;
  one call over the cost target.
- **Consistency and time cannot fail alone on a run set:** losing either needs escalated clear false positives,
  which fail over-escalation first. Each is shown failing alone on the judging step instead.
- **Each eligibility case** gives NOT ELIGIBLE, never PASS: a changed targets file, a world that is not the frozen
  one, two valid runs, a fixture price table, a fixture time file, a sourced price table that is not the committed
  one, a price table git cannot read at the run's commit, a call without token counts, a run whose items do not
  match its manifest, a run with one true match removed in every framing, a run with one injection pair removed,
  a run with one twin flag flipped (each with its manifest's hash and counts made consistent), and a superseded run
  set, and a world copy with one alert removed from its public alert list or one twin from its twin list (the runs
  changed to match). Every per-target entry is then marked mechanism only; on the passing oracle set none is.
- **Six deliberate breakages** of the check, each in its own shared git clone with the uncommitted work laid over
  it, each make their named guard test fail, while the guard passes on an untouched clone
  (`test_mutation.py`, with T06's proof machinery; the real files are unchanged).

## Limits

- The frozen world only. AC-1 and AC-5 on the fresh-seed world are out of scope here.
- The oracle reads the truth; it exists only in the tests.
- The check trusts the runs' own manifests for whether a run is valid, as the score step does.
