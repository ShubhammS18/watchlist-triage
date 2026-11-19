## Blockers

- docs/release-checklist.md:3 (docs/release-checklist.md:3) — The checklist cannot satisfy the before release review required by SPEC.md:51 (SPEC.md:51) and DEC-W2-SCOPE. Release 1 was published on 18 Nov; the checklist and rewritten README were committed on 19 Nov. The release-1 tag contains no checklist and still has a README saying the release runs “are still to come.” docs/README.md:26 (docs/README.md:26) correctly calls the checklist a draft, but the historical pre-release review cannot be claimed for release 1.
- docs/release-checklist.md:3 (docs/release-checklist.md:3) — “Every public-facing claim” exceeds the checklist’s coverage. It lists claims from the current top-level README, while NFR-8 calls for all public-facing text. Even within that README, the test-installation and git-clone guidance at README.md:164 (README.md:164) has no corresponding claim entry.

## Shoulds

- tests/w2_09_readme/test_readme.py:139 (tests/w2_09_readme/test_readme.py:139) — The figure gate checks the frozen and fresh result cells, but not the Target column. Changing “at most 3.9%” to “at most 39%” passed that check. The gate’s stated “every release figure” coverage at docs/release-checklist.md:5 (docs/release-checklist.md:5) is therefore too broad.
- tests/w2_09_readme/test_readme.py:147 (tests/w2_09_readme/test_readme.py:147) — Figures outside the table are checked selectively. In-memory changes to release spend from USD 0.70 to USD 7.00 and baseline over-escalation from 52.7% to 5.27% passed the relevant gate checks. The current figures agree with docs/release-log.md:65 (docs/release-log.md:65) and docs/baseline-report.md:102 (docs/baseline-report.md:102); the issue is regression detection.

## Notes

- tests/w2_09_readme/test_readme.py:86 (tests/w2_09_readme/test_readme.py:86) — The gate does catch removal of a listed scope gap: an in-memory deletion of FR-11 failed. The current thirteen IDs and qualifiers match DEC-W2-SCOPE.
- README.md:29 (README.md:29) — I found no incorrect current release-table figure against either committed check output. The current README also includes the NFR-7 limitations. Its “over 90%” wording accurately attributes the statistic to Kim and Yang’s paper, which cites earlier sources for it.

The W2-09 suite passed (10 passed). I changed no files.
