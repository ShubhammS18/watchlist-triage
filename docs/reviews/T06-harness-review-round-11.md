Verdict: DO NOT APPROVE. One active decision remains contradicted. I changed no files.

## Part A — round-10 findings

- Hand-off after a fault during the pacer wait: PARTLY FIXED. run.py (harness/run.py:264) now collects results after the wait and checks for faults before submission. A fault can still arrive between that check and the submission (harness/run.py:267).
- Citation oracle: FIXED. test_score.py (tests/t06_harness/test_score.py:186) requires a non-empty citation list whose IDs all belong to the sent bundle.

## Part B — findings

1. CONTRADICTS an active record — a worker fault can precede a new hand-off. DEC-T06-PARALLEL-2 (.genesis/project.json:989) requires no new hand-off after a fault. The final check at run.py (harness/run.py:264) and submission at line 267 (harness/run.py:267) are separate operations. In a read-only, in-memory reproduction, the first worker’s fault was queued before the second submission, yet the second agent started. This window exists with or without pacing. The pacer fault test (tests/t06_harness/test_parallel.py:232) covers a fault queued before the final check.
2. IMPROVEMENT only — a reference-agent injection assertion is tautological. test_reference.py (tests/t06_harness/test_reference.py:84) compares divergent, by_cause, and by_label with those same values from the report. That part passes regardless of their correctness; the assertion does check pairs == 45.

The T06 suite passed 340 tests, with 6 skipped. I found no other confirmed T06-owned SPEC contradiction. I cannot confirm this: the documented 5,535-call rehearsal and manual mutation proofs were not reproduced in this read-only review.
