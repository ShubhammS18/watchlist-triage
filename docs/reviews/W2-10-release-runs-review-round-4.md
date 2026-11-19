## Blocker

- README.md (README.md:9) still says the release runs are “still to come.” DEC-W2-RELEASE-RULES requires the README to state the supported result: frozen world PASS on all release targets; fresh world PASS on safety counts only. The tagged outputs support that narrower wording, but the public status does not report it.

## Shoulds

- README.md (README.md:91) says the evaluation’s main limit is “One synthetic world.” Release 1 used two synthetic worlds. The earlier upgraded-agent section can still describe its own one-world attempt, but the overall limit is stale.
- docs/w2-10-release-runs.md (docs/w2-10-release-runs.md:3) still presents the task as a pre-freeze design, and its “No real model” limit at line 745 (docs/w2-10-release-runs.md:745) is stale when read as the published task’s status. Label that material as pre-release history when recording this review.

## Notes

- docs/release-log.md (docs/release-log.md:38) agrees with the artifacts: three completed, valid runs per world; all six checkpoint copies match, all six audit logs verify, and both run sets’ SHA256SUMS verify. The committed checks reproduce at release-1; the publish and sign-off tests passed 16/16. No forbidden file changed between the freeze and publish.
- docs/release-log.md (docs/release-log.md:52) correctly records frozen PASS and fresh PASS (safety counts only). The fresh rates are informational, so a README claim that it met every target would exceed the evidence. The USD 1.65 running total matches the logged amounts; Console balances and key revocation remain owner attestations, as the rules’ stated limits allow.

No files were changed.
