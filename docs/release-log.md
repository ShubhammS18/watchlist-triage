# Release 1 log

Task W2-10-release-runs. Rules: DEC-W2-RELEASE-RULES, DEC-W2-08-CHOICES, DEC-W2-08-CHECKPOINTS, DEC-W2-10-CHOICES,
DEC-W2-10-STOPS, DEC-W2-10-LOST-INDEX, DEC-W2-10-ROUND3.

- Freeze commit: `fb4ab457ae9512c6073b59458c7263421b23d844`, tag `release-1-freeze`
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

```
2026-11-17T13:57:02Z
fb4ab457ae9512c6073b59458c7263421b23d844	refs/tags/release-1-freeze^{}
```

- Tag page: https://github.com/ShubhammS18/watchlist-triage/releases/tag/release-1-freeze
- Owner, 2026-11-17: the tag was public, as shown above, before the fresh world was made.

## Generation

- Run at (UTC): 2026-11-17T14:06:13Z (the owner's `date -u` reading at the generation step)
- One try, accepted at counter 0; no rejected try. The release check's own replay matches the record.

| Counter | Seed | Outcome | Error type | World hash |
|---|---|---|---|---|
| 0 | 3386666965265652 | accepted | none | `078687d3cd02886b0b45ccc21e20dfb5b39df58aeb1775774b91b140f5421d8e` |

## Frozen world
| # | Run ID | State | Valid or replaced | Reason | Re-run cause | Checkpoint committed | Harness USD | Console before | Console after | Spend USD | Note |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `20261118T063504891589Z-494505a1` | completed | valid |  | none | yes | 0.1000 | 4.46 | 4.36 | 0.10 | 0 refusals; every call left token counts |
| 2 | `20261118T065600682718Z-494505a1` | completed | valid |  | none | yes | 0.0999 | 4.36 | 4.26 | 0.10 | 0 refusals; every call left token counts |
| 3 | `20261118T071837280041Z-494505a1` | completed | valid |  | none | yes | 0.0998 | 4.26 | 4.16 | 0.10 | 0 refusals; every call left token counts |

## Fresh world
| # | Run ID | State | Valid or replaced | Reason | Re-run cause | Checkpoint committed | Harness USD | Console before | Console after | Spend USD | Note |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `20261118T074243814625Z-ea98bd39` | completed | valid |  | none | yes | 0.0998 | 4.16 | 4.06 | 0.10 | 0 refusals; every call left token counts |
| 2 | `20261118T080337937147Z-ea98bd39` | completed | valid |  | none | yes | 0.0998 | 4.06 | 3.96 | 0.10 | 0 refusals; 1 call left no token counts (ALT-0260/1, ProviderError) and was retried successfully, so the check bounded its cost and the run is valid |
| 3 | `20261118T085818577239Z-ea98bd39` | completed | valid |  | none | yes | 0.0997 | 3.96 | 3.86 | 0.10 | 0 refusals; 1 call left no token counts (ALT-0520/2, ProviderError) and was retried successfully, so the check bounded its cost and the run is valid |

## Results
| World | Run set | Check output | Result |
|---|---|---|---|
| frozen | `494505a1` | `release/check-frozen.json` | PASS |
| fresh | `ea98bd39` | `release/check-fresh.json` | PASS (safety counts only) |

## Console sign-off

No sign-off row: the frozen-world result is PASS, not the qualified pass, so step 8 needs none.

| Run set | Console USD | Harness USD | Sign-off |
|---|---|---|---|

## Running total

Wave-2 spend: USD 1.65 (before this log 0.95 + rehearsal 0.10 + frozen 0.30 + fresh 0.30)
