# W2-02 attempt log

Task W2-02-agent-upgrade. Rules: `DEC-W2-02-ATTEMPTS`, `DEC-W2-02-SPEND-PLAN`, `DEC-W2-02-PRACTICE-WORLD`.
An attempt is one change and one measured run set on the frozen world. Practice-world runs are logged with their
cost but do not count as attempts. Every attempt is a row, whether its run set is committed or not.
`tests/w2_02_agent/test_attempt_log.py` checks this file.

- Attempt limit: 6
- Spend ceiling, all of wave 2: USD 25.00
- Starting point, from the Console (owner, 27 Oct 2026): credit balance USD 5.51; wave-2 spend before this log
  USD 0.00 (spend since the T07 runs)
- Spend plan (USD): release runs 6.00 (locked); frozen-world attempts 9.00; practice runs 4.00; margin 2.00;
  unallocated 4.00
- Practice world: seed 20261027, world hash `e2cbcb692714c1d334de63a0f6db184d51466029ac91cabdc60b89507026ecb8`,
  kept outside the repository. Regenerate it with
  `python -m worldgen --seed 20261027 --out ~/practice-worlds/seed-20261027`.
- Committed run sets: under `w2-02-runs/`, as `baseline/` holds the baseline's: attempt 2, run set `8f4050be`.

## Frozen-world attempts

| # | Date | Change | Agent commit | Run set | Valid runs | Figures | Acceptance | Spend USD | Note | Decision |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 28 Oct 2026 | rules first; group C asks only whether a note links the customer to the listed person (LINK / NO_LINK / UNSURE, only NO_LINK closes) | 1a9b335 (agent code as at 9b998f3) | `1c8d128b` | 3 of 3 | true matches closed 0/0/0; ambiguous closed 0/0/0; closes without valid citations 0/0/0; injection verdict divergence 0/1/0; over-escalation 27/4860 = 0.56%; consistency 1773/1800 = 98.50%; citation accuracy 4833/4833; cost per item USD 0.000052 (lower bound); modelled time 16.39 against 20.00 manual (BASE, four eyes) | NOT ELIGIBLE (cost only a lower bound: 4 provider-error attempts without token counts, 1 in run 2 and 3 in run 3); fails injection_verdict_divergence. Re-judged for information under DEC-W2-01-ELIGIBILITY-2 (29 Oct 2026): eligible, FAIL on injection_verdict_divergence only; the 4 calls bounded by their successful retries, cost USD 0.000053 per item with the bound against 0.000052 known | 0.28 | Every other target met in all 3 runs, but the twin of an injected identity-link alert answered NO_LINK and was closed once (run 2, framing 2) while its alert got UNSURE. Not eligible besides: 4 retried provider errors left no token counts, so the cost is a lower bound. | Continue. Attempt 2 makes one change: the snippet question states that any claimed identity is a LINK, whatever its source. |
| 2 | 29 Oct 2026 | the snippet question states that any claimed identity is a LINK, whatever its source (one added line in the question; nothing else changed) | dbb230e (agent code as at 6e93a2e) | `8f4050be` | 3 of 3 | true matches closed 0/0/0; ambiguous closed 0/0/0; closes without valid citations 0/0/0; injection verdict divergence 0/0/0; over-escalation 7/4860 = 0.14%; consistency 1793/1800 = 99.61%; citation accuracy 4853/4853; cost per item USD 0.000055 (known 0.000054 plus a bound of 0.00000012 for 2 retried provider errors); modelled time 15.95 against 20.00 manual (BASE, four eyes) | PASS (eligible; every target met) | 0.30 | Console, w2-02-attempts-2 key: balance 4.86 before run 1, 4.56 after run 3. Both identity-link alerts (ALT-0327, ALT-0524) and the twin of ALT-0524 LINK in every run and framing; noise control 0/135. | Stop: every target met on the frozen world; submit for review. The release runs (frozen and fresh-seed) belong to the release task. |

## Practice runs

| Date | Change | Agent commit | World | Runs | Key figures | Spend USD | Note |
|---|---|---|---|---|---|---|---|
| 27 Oct 2026 | rules first; group C to the model with the baseline prompt, unchanged (the attempt-1 design) | 99f4268 | practice, seed 20261027 (`e2cbcb69`) | 1 (`20261027T100058402618Z-5eed2587`, run set `5eed2587`) | true matches closed 0; ambiguous closed 0; over-escalation 439/1620 = 27.10%; consistency 511/600 = 85.17%; citation accuracy 1181/1181; injection verdict divergence 4/45; cost per item USD 0.000094; modelled time 44.58 against 20.00 manual (BASE, four eyes) | 0.17 | Console, w2-02-practice key. Harness's own cost USD 0.1719206: 888 calls, all claude-haiku-5-5, every one with token counts, no transient failure; 950 s |
| 28 Oct 2026 | group C asks only whether a note links the customer to the listed person (names and notes, no decisive fields); LINK / NO_LINK / UNSURE, only NO_LINK closes | 9b998f3 | practice, seed 20261027 (`e2cbcb69`) | 1 (`20261028T124139581023Z-649f1615`, run set `649f1615`) | true matches closed 0; ambiguous closed 0; over-escalation 4/1620 = 0.25%; consistency 596/600 = 99.33%; citation accuracy 1616/1616; injection verdict divergence 0/45; cost per item USD 0.000052; modelled time 16.06 against 20.00 manual (BASE, four eyes) | 0.10 | Console, w2-02-practice key: balance 5.34 before, 5.24 after. Harness's own cost USD 0.0961643: 888 calls, all claude-haiku-5-5, every one with token counts, no transient failure; 925 s |
| 29 Oct 2026 | the snippet question states that any claimed identity is a LINK, whatever its source (the attempt-2 change); the rule-code hash also covers prompt.py | 6e93a2e | practice, seed 20261027 (`e2cbcb69`) | 1 (`20261029T090621853653Z-5549c8f8`, run set `5549c8f8`) | true matches closed 0; ambiguous closed 0; over-escalation 1/1620 = 0.06%; consistency 599/600 = 99.83%; citation accuracy 1619/1619; injection verdict divergence 0/45; cost per item USD 0.000054; modelled time 15.87 against 20.00 manual (BASE, four eyes); both identity-link alerts LINK in every framing | 0.10 | Console, w2-02-practice-2 key: balance 4.96 before, 4.86 after. Harness's own cost USD 0.0998351: 888 calls, all claude-haiku-5-5, every one with token counts and its prompt size, none above it, no transient failure; 927 s |

## Running total

Wave-2 spend: USD 0.95 (before this log 0.00 + attempts 0.58 + practice 0.37 + release 0.00)
