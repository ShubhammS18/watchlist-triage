# T06 harness independent review, round 9

Verdict: DO NOT APPROVE. The three round-8 findings are fixed. I found one active-record contradiction in the gate’s time limit. I changed no files.

## Part A — round-8 findings

| Finding | Status | Evidence |
|---|---|---|
| Unhashable state | FIXED | schema.py (harness/schema.py:215) checks that state is text before dictionary membership. score.py (harness/score.py:381) treats a failed index check as an entry problem. |
| Optional table note | FIXED | The shared table check requires note to be null or text of at most 500 characters in cost.py (harness/cost.py:41); the scorer calls it for both embedded tables in score.py (harness/score.py:434). |
| Huge integers | FIXED | schema.py (harness/schema.py:68) catches OverflowError before the SECONDS and REPORTED_ID rules use the result. |

## Part B — findings

1. CONTRADICTS an active record — the gate has no 120-second stop. DEC-T06-GATE-TIME-6 says the gate stops at 120 seconds (project.json (.genesis/project.json:1233); harness-design.md (docs/harness-design.md:574)). The documented gate command is plain pytest (harness-design.md (docs/harness-design.md:549)). The timed wrapper passes the command to the memory guard (timed_run.sh (tools/timed_run.sh:52)), whose loop stops it on excess memory or exit, with no elapsed-time check (memory_guard.sh (tools/memory_guard.sh:24)). A test that hangs below the memory limit can therefore run past 120 seconds. The timing-tool tests use their own 10-second subprocess timeout; that does not impose a limit on the gate (test_timing_tools.py (tests/t06_harness/test_timing_tools.py:137)). I cannot confirm this stop is supplied by an external runner outside the reviewed files.
2. IMPROVEMENT only — one full-world test has a weak citation-existence oracle. The expected count treats any answer lacking "EVD-UNKNOWN" as valid, including an empty cited-ID list (test_score.py (tests/t06_harness/test_score.py:185)). The SPEC requires a non-empty set (SPEC.md (SPEC.md:130)), which the scorer checks (score.py (harness/score.py:83)). The current fake-model cases do not expose the difference, so this does not show a wrong current score; it limits what that test independently proves.

I found no other unmet T06-owned SPEC requirement or false active record in the reviewed code. I did not run the gate or mutation proofs under the read-only instruction, so I cannot confirm this review’s gate timing or the documented rehearsal results.
