## Verdict: DO NOT APPROVE

The staged code provides a single model call shape and a working scripted stub, but the network part of AC-11 is not met as written. The child’s Python audit hook blocks ordinary network use; it does not prevent the child from reaching a destination by starting an unguarded process.

### Findings, ranked by severity

1. High — the agent child can reach a network destination. In a scratch copy, I called _posixsubprocess.fork_exec directly from the guarded child. It launched Python, and that process connected to a local loopback server. The same probe succeeded in the unguarded control. The design acknowledges the missing audit event (docs/model-interface-design.md:68), but its “cannot open network connections or start other programs” claim (docs/model-interface-design.md:13) and AC-11’s “cannot reach any destination” claim are too strong. An OS process boundary, or a narrower approved requirement, is needed.
2. High — the wall-clock cap does not cap time spent in a parent model call. With limit_s=0.2 and a model call sleeping two seconds, run_child returned ChildTimeout after 2.063 seconds. It killed and reaped the direct child (returncode -9), but the caller remained blocked in the model function. A model call that never returns could leave run_child blocked indefinitely. The existing test checks the error and child exit, but not elapsed time. See runner.py (model_interface/runner.py:68) and the design claim (docs/model-interface-design.md:80).
3. Medium — request shape is not closed at the pipe boundary. Request(...) rejects an extra tools key initially, but request_from(...) ignores extra top-level keys. I sent a forged pipe call containing "tools": []; the parent accepted it and called the stub. No tool was executed, but the stated rejection of extra keys is false. A constructed request’s nested message dictionary can also be mutated later to add tools. See request_from (model_interface/__init__.py:79) and Request (model_interface/__init__.py:50).
4. Medium — FR-9’s evidence restriction is not enforced by this child. It read a harmless scratch file by path in my probe. I did not access data/world/hidden/. The child has filesystem access, so “uses only the evidence supplied” remains a later integration obligation, not a property established here.

### What the probes showed

| Route tried in the child | Result | Route type |
|---|---|---|
| multiprocessing, asyncio subprocess, os.popen | Blocked; each worked in its control | Accidental use |
| webbrowser launching a registered program | Returned false; control succeeded | Accidental use |
| Raw _socket.connect | Blocked; control reached loopback | Deliberately hostile |
| importlib and _imp extension loading | Allowed to load _ssl; loading alone did not make a connection | Deliberately hostile preparation |
| Write to a parent socket FD | EBADF in both runs: the runner did not inherit that FD | Deliberately hostile; no guard proof |
| Write a forged model call on the pipe | Accepted, including an extra tools key; no tool executed | Deliberately hostile |
| Direct _posixsubprocess.fork_exec | Not blocked; spawned process reached loopback | Deliberately hostile |

The T04 isolation tests do establish a real control for the ordinary routes: the same local connection probes succeed without the hook and are refused with it. The five mutation cases catch their chosen breakages. They do not cover the private launcher, extra request keys, filesystem access, or a model call that outlasts the timer.

### Interface, claims, and regression

The one synchronous interface, named errors, stub configuration, and pipe call worked in the tests. Changing configuration changed stub replies without changing calling code. I cannot confirm this for swapping to a different real provider by configuration alone: only stub is registered; the alternate provider test adds a registry entry in code. That limitation is stated in the design.

The design honestly identifies the Python-level guard, _posixsubprocess.fork_exec, hand-raised events, untested native Windows env={}, and the intended 60-second whole-run limit. Its absolute network/program claims and its assertion that the limit covers time inside model calls exceed what the code does.

Verified runs: T01 24 passed; selected T02 565 passed; T03 174 passed; T04 102 passed. The first T04 attempt could not start its local server under the workspace socket restriction; the rerun with loopback access passed. I did not run the hidden-data-dependent T02 tests because you prohibited reading data/world/hidden/, so I cannot confirm this as a complete T01–T04 regression.

MANIFEST.json contains the requested world_hash value, b77a6804a52b1d41650e250a31ff64a701b1d315a674a1f1242d93cb6b15c9b0. I did not recompute it from hidden files. Git comparison against HEAD found no changes in worldgen/, data/, framings/, SPEC.md, or T01–T03 tests. The review made no repository edits.
