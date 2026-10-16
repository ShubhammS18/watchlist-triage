# T06 harness independent review, round 10

Verdict: DO NOT APPROVE. I found one active-record contradiction. I changed no files.

## Part A — round-9 findings

| Finding | Status | Evidence |
|---|---|---|
| Gate time limit | FIXED for the timed gate path. memory_guard.sh (tools/memory_guard.sh:12) defaults to 110 seconds and kills the command’s process group when it exceeds that limit at line 45 (tools/memory_guard.sh:45); timed_run.sh (tools/timed_run.sh:52) invokes the guard. A dummy-process test covers the timeout at test_timing_tools.py (tests/t06_harness/test_timing_tools.py:53). The active record separately assigns a 120-second limit to Genesis at project.json (.genesis/project.json:1260). I cannot confirm this Genesis enforcement from the reviewed files. |  |
| Citation test oracle | FIXED for the reported empty-list defect. The expected count now requires a non-empty cited-ID list at test_score.py (tests/t06_harness/test_score.py:185), matching the SPEC definition (SPEC.md:130) and scorer (harness/score.py:83). |  |

## Part B — findings

1. CONTRADICTS an active record — a parallel run can hand off another item after a harness fault. DEC-T06-PARALLEL-2 (.genesis/project.json:989) requires no new hand-off after a fault. In run.py (harness/run.py:259), the main thread collects failures before it waits in the pacer, then submits the next item at line 263 (harness/run.py:263) without collecting again. A worker can fail during that wait. A read-only, in-memory reproduction with two workers produced RuntimeError ['first', 'second']: second started after first failed. The fault test at test_parallel.py (tests/t06_harness/test_parallel.py:230) uses no pacer; the pacer test at line 164 (tests/t06_harness/test_parallel.py:164) has no fault.
2. IMPROVEMENT only — the citation oracle still recognizes invalid IDs by one sentinel. test_score.py (tests/t06_harness/test_score.py:185) checks for EVD-UNKNOWN rather than membership in the sent bundle. The current fake cases do not show an incorrect expected score; another invalid ID would weaken this test.

I found no other confirmed unmet T06-owned SPEC requirement, false active record, or test currently passing for the wrong reason. I did not run the full gate or mutation proofs under the read-only instruction, so I cannot confirm this review’s gate timing or the documented rehearsal result.
