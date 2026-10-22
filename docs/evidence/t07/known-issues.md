# T07 evidence: known issues

## 1. One stall of the T04 name-lookup isolation test (cause unconfirmed)

**What failed.** On 21 Oct 2026 at 06:19 UTC, at commit 1f06342 with a clean tree, charger in and benchmark
0.770 s, the full T04 suite run through `tools/timed_run.sh` ended with 128 passed and 8 errors in 17.18 s
(`t04-suite.txt`). The 8 errors are the 8 T04 mutation proofs. Before they run, a setup step copies
`model_interface/` and `tests/t04_model_interface/` to a temporary folder and runs the whole suite there; that copy
must pass first. In the copy, one test failed: `test_isolation.py::test_a_name_lookup_is_refused`. It starts the
guarded agent process, asks it to try four name lookups and connections, and expects each to be refused, within a
5-second limit. The process did not answer within 5 seconds (`ChildTimeout: the agent process was killed after 5
seconds`), so the setup step failed and none of the 8 proofs ran. The same test passed in the main run of the same
suite a few seconds earlier.

**How often it recurred.** Not once in these reruns:

| Run | File | Result |
|---|---|---|
| that test alone, in the repo, 5 times (not timed_run; diagnostic, no file) | - | 5 passed, 0.04-0.05 s each |
| that test alone, in a fresh copy built like the proofs' copy, 3 times (diagnostic, no file) | - | 3 passed, 0.05-0.08 s each |
| full T04 suite again | `t04-suite-rerun.txt` | 136 passed in 41.69 s |
| T04 mutation-proof file alone | `t04-mutation-1.txt` | 8 passed in 34.86 s |
| T04 mutation-proof file alone | `t04-mutation-2.txt` | 8 passed in 34.80 s |
| T04 mutation-proof file alone | `t04-mutation-3.txt` | 8 passed in 34.89 s |

So: 1 stall in 1 + 1 + 3 = 5 runs of the untouched-copy setup through `timed_run.sh` (the first run, plus the
rerun and the three mutation-file runs, each of which runs the copy first), and none in 8 direct runs of the test.

**Cause: unconfirmed.** The test normally answers in about a twentieth of a second, so the stall was more than a
hundred times its usual time. A deterministic fault would fail every time; a race would not, so a code cause is not ruled out. It did not recur. A
possible cause is contention for the host's CPU (WSL shares the Windows host's processors, and a pause in the WSL
virtual machine would stall a child process start), but this was not measured and is not shown. The copy holds
the whole `model_interface/` package, including the T07 adapter, so a missing file is ruled out.

**Effect on T07.** Apart from the new adapter module in `model_interface/`, the registry entry and its test, no T04
file changed in T07.
The test that stalled is about the network guard of the agent process, which T07 did not touch. Reported here so
the reviewer sees the failed run as well as the passing ones; `t04-suite.txt` is kept unchanged.

**If it recurs.** Run the test alone under a trace of the child process start, and consider whether the 5-second
limit in that test is too tight for this machine; any change to the test is a T04 change and an owner decision.

## 2. S4 output files are lost

The S4 session's temporary folder was empty when S7 started (recreated at 05:53 UTC on 21 Oct 2026), so no S4
output could be copied here. The S5 and S6 files (`t07-suite-s5.txt`, `t07-suite-s5-unchecked.txt` and
`t07-suite-s6.txt`) are at the top level of `docs/evidence/t07/`, byte for byte as they were written.

## 3. The set report's bytes depend on which command scored last

**What happens.** The harness rewrites a run set's report (`sets/<run set>.json`) every time it scores, worked out
afresh from the item lines. `run-and-score` scores the run it just made first; `score` takes the runs in index order.
The two orders give set reports with the same values but different bytes: the list of runs is in a different order,
and where runs tie on a figure, the minimum or maximum shown is the tied fraction of whichever run comes first (for
example 49/49 against 52/52, both exactly 1).

**Where it was seen.** On 21 Oct 2026 (S11) the set report written by run 3's own `run-and-score` had SHA-256
`89dc81f4d21426390ca984819d19b34a55ee3c220a96478aa81048e0a5351f4e`. `python -m harness score ~/t07-runs data/world`
(no `--rescore`) kept all three run reports and rewrote the set report as
`1450fede30e7b4d53990cd62c55f3a8ae4ec8d4598be322f34bf5e24b62f0114`. The earlier file was not kept. On a copy of the
output folder: `score` twice gave `1450fede...` both times, and scoring with run 3 first, as `run-and-score` does,
gave `89dc81f4...` exactly. The two versions differ in 3 places in the run order and in 36 tied minimum or maximum
entries; the pooled block and the eligibility are identical. No value differs.

**Effect.** None on any figure. `baseline/` holds the `1450fede...` version (written by `score`), and its SHA-256 is
in `baseline/SHA256SUMS`. Anyone who re-scores the baseline output with `run-and-score`'s order would get different
bytes, not different numbers. This is T06 behaviour; T07 did not change it.

## 4. The gitleaks report of run 1 alone was replaced

The helper names its report after the scanned folder, so the S11 scan of `~/t07-runs` (all three runs) wrote
`gitleaks-t07-runs.json` over the S10 scan of the same folder when it held run 1 only. Both scans reported "no leaks
found" and exit 0, and both reports were `[]`; the S10 result is recorded in the S10 report to the owner, not in a
file here.
