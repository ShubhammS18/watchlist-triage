# Release 1 log

Task W2-10-release-runs. Rules: DEC-W2-RELEASE-RULES, DEC-W2-08-CHOICES, DEC-W2-08-CHECKPOINTS, DEC-W2-10-CHOICES,
DEC-W2-10-STOPS, DEC-W2-10-LOST-INDEX, DEC-W2-10-ROUND3.

- Starting point: wave-2 spend USD 0.95 (docs/w2-02-attempts.md); Console balance USD 4.56 (owner, 17 Nov 2026)
- Keys: w2-10-rehearsal (rehearsal), w2-10-release (release runs); both revoked after the publish
- Stop rules: a run over USD 0.30, W2-10 over USD 2.00, or the wrapper's refusal checkpoint stops the release before
  the next run

## Rehearsal
| Date | Run ID | Agent commit | Run set | State | Key figures | Harness USD | Console before | Console after | Spend USD | Peak memory MB | Note |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 17 Nov 2026 | `20261117T091935637500Z-2dd374e6` | `34432e809c8c` | `2dd374e6` | completed | true matches closed 0, ambiguous closed 0, over-escalation 4/1620 | 0.0999 | 4.56 | 4.46 | 0.10 | 1292 | rehearsal, first try; 889 attempts for 888 calls, the one without token counts retried successfully; 0 refusals |

## Freeze and push

The freeze commit is the commit that adds this heading.
