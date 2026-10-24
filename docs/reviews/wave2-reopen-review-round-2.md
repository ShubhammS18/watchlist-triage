# Independent review, round 2 (final)

Scope: round-1 findings 1–6, `round1-fixes.md`, and changed draft lines only. No Genesis command was run; `data/world/hidden/` was not read.

## Round-1 findings

1. **RESOLVED** — `baseline-report.diff:27-38,76-80`; `README.diff:9-12`; `decisions.md:10-11,30`. The revisions describe an association with injected text and the observed control-twin variation, without claiming that the sample proves causation or rules out chance.

2. **RESOLVED** — `baseline-report.diff:20-22,31-45,52-55`; `README.diff:9-12`; `decisions.md:11`. The baseline-only observation is separated from the owner's hidden-label identification of that alert as the three missed true matches.

3. **RESOLVED** — `SPEC.diff:7`. The change note now names the network carve-out, uncrossed breakdowns, main-item cost definition, AC-12 citation relaxation, and time-budget removal as requirement changes, and separates the clarifications.

4. **NOT RESOLVED** — `tasks.md:22-25`; `decisions.md:21,59`. The revised gate checks only that *committed* run sets appear in the attempt log and that its logged spend is at most USD 25. It does not establish a row for every measured attempt (including failed or uncommitted runs), one change and one run set per attempt, the pre-set attempt limit, or spending across all of wave 2. The decision says spending stays *under* USD 25, while the gate allows exactly USD 25. The reviewer comparison with Console figures helps, but is not a gate check. **Fix:** Specify a complete attempt ledger and checks for every attempt, the limit and one-change/one-run-set rule; reconcile the ledger with the owner's Console total for all wave-2 spending and require a total strictly below USD 25. If some evidence is necessarily human-reviewed, state that as an explicit completion gate rather than claiming the test gate checks the whole outcome.

5. **RESOLVED** — `tasks.md:37-41,45,60,62-63,73-75`. The table is now labelled as all requirements on WAVE2-RESERVED and notes the four partial overlaps with completed tasks.

6. **RESOLVED** — `decisions.md:25,29-30`. The section heading no longer contains a requirement ID; the recorded title and text remain free of IDs.

## New issue on a changed line

- **SHOULD** — `commands.md:10`. The changed placeholder check prints `STOP: placeholder found` but exits the `if` successfully and proceeds to the Genesis commands. This contradicts the sequence's “Each step stops on its first error” instruction at line 3 and defeats the stated check. **Fix:** Restore `exit 1` in the `then` branch; the fix log has already moved outside the searched drafts directory.
