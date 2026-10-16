Verdict: APPROVE. I found no confirmed T06-owned SPEC requirement or active DEC-T06 record contradicted by the code.

Part A — round-11 findings

- Hand-off after a fault: STATED LIMIT. The scheduler collects results and checks faults after the pacer wait, immediately before submission (run.py (harness/run.py:264)). A fault arriving between that check and submission is the limit now stated in DEC-T06-PARALLEL-3 (project.json (.genesis/project.json:2314)). I found no ordered case where a fault was already collected and then ignored.
- Reference-agent assertion: NOT FIXED. The assertion still compares divergent, by_cause, and by_label with themselves (test_reference.py (tests/t06_harness/test_reference.py:84)).

Part B — findings

- IMPROVEMENT only: The reference-agent assertion above can pass with incorrect injection counts. It does check pairs == 45, and a separate full-world test checks divergence against independently counted results (test_score.py (tests/t06_harness/test_score.py:252)). I found no confirmed blocking finding.

The T06 suite passed 340 tests, with 6 skipped. The workspace status was unchanged. I cannot confirm this: the documented 5,535-call rehearsal, manual mutation proofs, and historical timing measurements were not reproduced in this review.
