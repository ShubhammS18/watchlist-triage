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
- Committed run sets: under `w2-02-runs/`, as `baseline/` holds the baseline's; none yet.

## Frozen-world attempts

| # | Date | Change | Agent commit | Run set | Valid runs | Figures | Acceptance | Spend USD | Note | Decision |
|---|---|---|---|---|---|---|---|---|---|---|

## Practice runs

| Date | Change | Agent commit | World | Runs | Key figures | Spend USD | Note |
|---|---|---|---|---|---|---|---|
| 27 Oct 2026 | rules first; group C to the model with the baseline prompt, unchanged (the attempt-1 design) | 99f4268 | practice, seed 20261027 (`e2cbcb69`) | 1 (`20261027T100058402618Z-5eed2587`, run set `5eed2587`) | true matches closed 0; ambiguous closed 0; over-escalation 439/1620 = 27.10%; consistency 511/600 = 85.17%; citation accuracy 1181/1181; injection verdict divergence 4/45; cost per item USD 0.000094; modelled time 44.58 against 20.00 manual (BASE, four eyes) | 0.17 | Console, w2-02-practice key. Harness's own cost USD 0.1719206: 888 calls, all claude-haiku-5-5, every one with token counts, no transient failure; 950 s |

## Running total

Wave-2 spend: USD 0.17 (before this log 0.00 + attempts 0.00 + practice 0.17 + release 0.00)
