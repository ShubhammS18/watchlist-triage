## Verdict: APPROVE WITH FIXES

The round 1 behavior gaps I could retest are closed. The remaining fixes are claims that still read more broadly than the approved scope.

### Findings, ranked by severity

1. Medium — the scope wording is inconsistent. The design and scope decision (docs/model-interface-design.md:18) clearly limit the Python guard to ordinary, accidental, and prompt-injected routes and defer hostile in-process code to a wave-2 OS sandbox. But the T04 outcome in PLAN.md (.genesis/PLAN.md:35), KICKOFF.md (.genesis/KICKOFF.md:7), and project.json (.genesis/project.json:818) still says the agent “can reach nothing except the model interface.” The opening line of test_isolation.py (tests/t04_model_interface/test_isolation.py:1) does too. SPEC.md’s AC-11 (SPEC.md:84) remains absolute; the owner decision explicitly defers that clarification to wave 2. Thus I cannot say there is no remaining claim stronger than the code.
2. Low — request immutability needs precise wording. A constructed Request (model_interface/__init__.py:62) copies caller-owned message dictionaries and resists normal assignment; I verified both. Deliberate request.__dict__["messages"] = ... still changes its serialized content. That is in-process manipulation, not the aliasing bug from round 1, but the package’s unqualified “cannot be changed” claim is too strong.

### Verified by running on a scratch copy

- Direct _posixsubprocess.fork_exec launched Python and connected to a loopback server in the unguarded control. The guarded child (model_interface/child.py:40) raised PermissionError; no connection arrived. I found no additional ordinary or prompt-injected launcher or network route in the routes examined. I cannot confirm this for every possible route.
- A two-second model call with limit_s=0.2 raised ChildTimeout after 0.203 seconds. Its worker thread had not returned at that point and finished later, matching the documented lingering-thread limit (docs/model-interface-design.md:158).
- Forged top-level, message, and settings keys, plus a wrong-typed setting, produced clean ValueError at parsing and ChildError at the pipe. The model was called zero times in each probe.
- The FR-9 filesystem restriction (docs/model-interface-design.md:168) is correctly listed as open for T05/T06, not proven by T04.
- I accept owner decision 11 A’s lack of a committed launcher regression test for the narrowed scope, with the disclosed risk that a later change could reopen that route without a test failure.

| Regression | Result |
|---|---:|
| T01 | 24 passed |
| T02 safe subset | 568 passed |
| T03 | 173 passed; 1 hidden-dependent test could not be run meaningfully |
| T04 | 136 passed |

I cannot confirm this as a complete T01–T04 regression: the scratch copy excluded data/world/hidden/, so hidden-dependent T02 tests and the one T03 file-count test were unavailable. The MANIFEST (data/world/MANIFEST.json) states world_hash = b77a6804a52b1d41650e250a31ff64a701b1d315a674a1f1242d93cb6b15c9b0; I did not recompute it from hidden files. Git comparison with HEAD found no changes in worldgen/, data/, framings/, SPEC.md, or tests T01–T03. I made no repository edits.
