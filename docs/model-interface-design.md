# Model interface design for T04-model-interface

Requirements: FR-9, FR-16, the network part of AC-11 and the stub-model part of AC-14. Decision records: eleven
`DEC-T04-*` records, listed below. Eight are owner decisions of 2026-10-10. Three more of the same day follow the
independent reviews: two after `docs/reviews/t04-review-round-1.md` and one after
`docs/reviews/t04-review-round-2.md`.

## What it is

`model_interface` is the one way any code in this project reaches a model. A model is a function that takes a
request and returns a result, or raises a named error. Which model that is comes from a JSON file, so changing
the model means changing that file and no code.

T04 also provides the agent process. Agent code runs in a child Python process with a guard inside Python that
refuses the ordinary ways of opening a network connection or starting another program. The only thing the agent
code is handed is a `model` function, and each call to it travels over a pipe to the parent process, which owns
the real model.

**What is proven, and what is not.** The guard is proven against ordinary, accidental and prompt-injected routes:
agent code, or a library it uses, that simply tries to connect, look up a name or start a program is refused, and
the tests show the same attempt succeeding without the guard. Code written on purpose to defeat the guard from
inside the process is out of scope (`DEC-T04-AC11-SCOPE`). The guard is not a security boundary.

**Wording elsewhere is broader than this.** The approved plan and `KICKOFF.md` describe T04 as enforcing that the
agent process "can reach nothing except the model interface", and AC-11 in `SPEC.md` says the agent process
"cannot reach any destination except the model interface". Both are the original wording and neither is edited
here. `DEC-T04-AC11-SCOPE` governs what T04 claims (`DEC-T04-PLAN-WORDING`); the wave-2 reopen aligns the two.

T04 ships a scripted stub and no real model. There is no agent here either: the baseline agent is task T05.

## The decisions

| Decision | In one line |
|---|---|
| `DEC-T04-INTERFACE` | One synchronous call: messages `[{role, content}]` plus settings (`model`, `temperature`, `max_tokens`, `timeout_s`) go in; text, the provider-reported `model_id`, input and output token counts (`None` if unknown) and `latency_s` come out. No tools and no function-calling. |
| `DEC-T04-STUB` | The stub plays back a script: a default reply, an optional sequence of replies, and chosen failures (timeout, empty reply, provider error). No network, no randomness, and it never decides an alert. |
| `DEC-T04-CONFIG` | One JSON file names the provider, the model and the decoding settings. The default provider is the stub, the file holds no secrets, and an unknown provider is a clear error. Environment variables come later, for real keys only. |
| `DEC-T04-ISOLATION` | The agent process is a child Python started with `-I` that talks to the parent over a pipe. The network is blocked inside Python before any agent code runs, and the parent owns the model. |
| `DEC-T04-NO-ADAPTER` | T04 has no real provider adapter, no SDK and no keys. `PROVIDERS` in `providers.py` is the slot where an adapter is registered. |
| `DEC-T04-ERRORS` | Errors are named: `ModelError` is the base, with `ModelTimeout`, `BadReply` and `ProviderError`. The interface never retries. Retry limits and timeout handling belong to T05. |
| `DEC-T04-NO-PROGRAMS` | The same guard also refuses starting another program and loading a library through ctypes, since either would be a way around it. |
| `DEC-T04-WALLCLOCK` | `run_child` gives the whole child run 60 seconds by default. After that the child is killed and `ChildTimeout` is raised. It is a safety net, not the timeout policy of AC-13. |
| `DEC-T04-AC11-SCOPE` | Amends `DEC-T04-ISOLATION`. The guard is proven against ordinary, accidental and prompt-injected routes. Deliberately hostile code inside the agent is out of scope until an operating-system sandbox exists. `SPEC.md` is not changed; a clarification of AC-11's network part goes to the wave-2 reopen. |
| `DEC-T04-WALLCLOCK-THREAD` | Amends `DEC-T04-WALLCLOCK`. The parent runs each model call in a worker thread and waits within the limit, so `ChildTimeout` is raised on time even if the call has not returned. The abandoned thread may linger until its call returns. |
| `DEC-T04-PLAN-WORDING` | The plan and `KICKOFF.md` text for T04 ("can reach nothing except the model interface") is the original wording. `DEC-T04-AC11-SCOPE` governs. The wave-2 reopen aligns the T04 task text and AC-11. Plan text is not hand-edited. |

### Which records are current

`genesis help` lists no command that marks one record as replaced by another, so this table is the marker.

| Record | Status | Read together with |
|---|---|---|
| `DEC-T04-INTERFACE` | active | |
| `DEC-T04-STUB` | active | |
| `DEC-T04-CONFIG` | active | |
| `DEC-T04-ISOLATION` | amended | `DEC-T04-AC11-SCOPE`, which narrows what the guard is claimed to stop |
| `DEC-T04-NO-ADAPTER` | active | |
| `DEC-T04-ERRORS` | active | |
| `DEC-T04-NO-PROGRAMS` | active | |
| `DEC-T04-WALLCLOCK` | amended | `DEC-T04-WALLCLOCK-THREAD`, which makes the limit hold during a model call |
| `DEC-T04-AC11-SCOPE` | active | |
| `DEC-T04-WALLCLOCK-THREAD` | active | |
| `DEC-T04-PLAN-WORDING` | active | `DEC-T04-AC11-SCOPE`, which it names as the governing scope |

## How a run works

1. The caller loads the configuration: `model, settings = providers.load()`.
2. The caller starts the agent process: `run_child(module, payload, model)`.
3. The child's start-up script, `child.py`, installs the guard as its first act, then imports `module` and calls
   its `main(model, payload)`.
4. Each time the agent code calls `model(request)`, the request goes up the pipe as one line of JSON. The parent
   checks its shape, calls the real model once in a worker thread, and sends back the result or the name of the
   error.
5. Whatever `main` returns goes back to the caller of `run_child`.

**The request shape is closed.** A request is exactly `{"messages": [...], "settings": {...}}`, each message is
exactly `{"role": text, "content": text}`, and the settings are exactly the four named fields. Any other key at
any level, a missing key or a value of the wrong type is refused with a `ValueError`; at the pipe the run ends
with a `ChildError` and the model is not called.

A request copies its messages when it is built. It resists normal assignment and later edits to the caller's
lists and dictionaries. A deliberate `__dict__` write in the same process can still change it; that is
in-process manipulation and out of scope.

**The guard is a Python audit hook.** It refuses these events:

- network: `socket.connect`, `socket.bind`, `socket.sendto`, `socket.sendmsg`, `socket.getaddrinfo`,
  `socket.gethostbyname`, `socket.gethostbyaddr`, `socket.getnameinfo`
- starting another program: `subprocess.Popen`, `os.system`, `os.exec`, `os.spawn`, `os.posix_spawn`, `os.fork`,
  `os.forkpty`, `os.startfile`, `os.startfile/2`, `pty.spawn`
- loading a library through ctypes: `ctypes.dlopen`

**Three routes needed patches on top of the hook.** The review found that the private launcher underneath
`subprocess` raises no audit event. Closing it took three patches in `child.py`:

1. `fork_exec`: the launcher function itself, and `subprocess`'s own reference to it, are replaced with a function
   that refuses.
2. `create_builtin`: building a fresh copy of the launcher module raises no import event either, so the function
   that builds built-in modules is wrapped to refuse that module.
3. `builtin_importer`: the standard importer for built-in modules reaches the same function, so the same wrapper
   covers it.

The hook also refuses importing the launcher module afresh, and importing the modules that start a second
interpreter, which would run without the hook.

These patches are ordinary Python assignments inside the agent process. Hostile code running in that process
could restore the originals and undo them. That is why the operating-system sandbox is an open item for wave 2,
and why hostile in-process code is out of scope until then.

## Files

| File | Purpose |
|---|---|
| `model_interface/__init__.py` | request, message, settings and result types; the named errors; the one-line JSON messages of the pipe |
| `model_interface/stub.py` | the scripted stub |
| `model_interface/providers.py` | the provider registry and the configuration loader |
| `model_interface/config.json` | the default configuration: provider `stub` |
| `model_interface/runner.py` | parent side: `run_child`, the pipe protocol, the worker thread and the wall-clock limit |
| `model_interface/child.py` | child side: installs the guard, then runs the agent code |
| `model_interface/probe_child.py` | for tests only: tries the blocked things from inside the child. Not the agent |

The package uses the Python standard library only.

## Launcher routes tried by hand

No committed test covers these. Each route was tried by hand on 2026-10-10 from a scratch copy of the package,
with a local server on this machine counting connections. The outcomes are those in the stage 4e report.

| Route | Outcome | Status |
|---|---|---|
| direct | tried by hand on 2026-10-10, outcome as in the 4e report | not proven by a committed test |
| via_subprocess_name | tried by hand on 2026-10-10, outcome as in the 4e report | not proven by a committed test |
| reimport | tried by hand on 2026-10-10, outcome as in the 4e report | not proven by a committed test |
| reload | tried by hand on 2026-10-10, outcome as in the 4e report | not proven by a committed test |
| create_builtin | tried by hand on 2026-10-10, outcome as in the 4e report | not proven by a committed test |
| builtin_importer | tried by hand on 2026-10-10, outcome as in the 4e report | not proven by a committed test |
| subinterpreter | tried by hand on 2026-10-10, outcome as in the 4e report | not proven by a committed test |
| spawnv_passfds | tried by hand on 2026-10-10 | no working control, not proven |
| gc_search | tried by hand on 2026-10-10 | no working control, not proven |
| flip_the_flag | tried by hand on 2026-10-10 | no working control, not proven |
| posix_fork | tried by hand on 2026-10-10 | no working control, not proven |

In short, the 4e report shows each of the first seven refused in the guarded child and working in a control with
no guard. `create_builtin` and `builtin_importer` worked in the guarded child on the first try and were closed
afterwards. A hand check is weaker than a committed test: nothing fails if a later change reopens one of them.

## Honest limits

- **A guard inside Python, not a security boundary.** It stops ordinary and accidental network use and use that a
  prompt talks the agent into. It does not stop code written to defeat it. There is no operating-system sandbox.
- **The patches can be undone from inside.** See "Three routes needed patches" above. Other routes of the same
  kind may exist that were not found.
- **The launcher routes are not covered by a committed test.** See the table above.
- **A request is not sealed against deliberate change.** It resists normal assignment and later edits to the
  caller's lists. A deliberate `__dict__` write in the same process can still change it.
- **The child can read any file the user can read.** The guard is about the network and other programs. It does
  nothing about the filesystem. See the FR-9 open item below.
- **Three events are tested by hand only.** `os.spawn`, `os.startfile` and `os.startfile/2` are raised by real
  calls only on Windows. The tests raise them with `sys.audit` and check that the hook refuses them; no real call
  is exercised.
- **ctypes cannot be imported in the child.** Importing it loads a library, which the guard refuses. Agent code
  that needs ctypes, directly or through a library, will not run there.
- **The empty child environment is untested on native Windows.** The child is started with `env={}` so that
  nothing in the parent's environment reaches it. This works on Linux and WSL, where it was tested. Native
  Windows may need some system variables and has not been tried.
- **Synchronous only.** One call, one answer. No streaming, no batching, no parallel calls.
- **Stub only.** No real model has been called through this interface. Changing the stub's replies by
  configuration is tested; swapping to a real provider by configuration alone is not, because none is registered.
- **The 60-second limit covers the whole child run**, including time the parent spends inside model calls. It is
  not a per-call limit.
- **An abandoned model call may linger.** When the limit runs out during a model call, `run_child` kills the
  child and raises `ChildTimeout` at once, but the worker thread making the call is not stopped. It lingers until
  the call returns, and a call that never returns leaves its thread behind for the life of the parent.
- **No cost, token or retry policy yet.** The interface reports token counts when a provider gives them and
  never retries. What to do with either is for later tasks.
- **Placeholder defaults.** `max_tokens` 512 and `timeout_s` 30 in `config.json` are placeholders, not chosen
  values. The stub ignores both.

## Open items

For T05 and T06:

- **FR-9, "uses only the evidence supplied".** The child can read any file by path, so T04 does not establish
  this. It must be enforced where the agent is built and run: the agent is given its evidence bundle in the
  payload and nothing in it opens files, and the harness checks that.
- How the whole-run wall-clock limit of `run_child` fits with the timeout policy that T05 sets for AC-13.

For the wave-2 reopen:

- An operating-system sandbox for the agent process (`DEC-T04-ISOLATION`, `DEC-T04-NO-PROGRAMS`,
  `DEC-T04-AC11-SCOPE`). Until it exists, hostile in-process code stays out of scope.
- Align the T04 task text in the plan and the network part of AC-11 in `SPEC.md` with the proven scope
  (`DEC-T04-AC11-SCOPE`, `DEC-T04-PLAN-WORDING`). Until then both keep their original, broader wording.
- The parts of AC-11 and AC-14 that T04 does not cover stay under `WAVE2-RESERVED`: the capability allowlist
  check and the rejection of closing without a written reason (AC-11), and override, rejection and stop (AC-14).

## How to run the tests

```
.venv/bin/python -m pytest tests/t04_model_interface -q -p no:cacheprovider
```

- `test_interface.py`: the result fields, the stub's default reply, sequence and failures, one call per request
  with no retry, a request that resists normal assignment and later edits to the caller's lists, forged calls
  and forged settings refused at the pipe, and two
  configuration files driving the same code to different replies.
- `test_isolation.py`: every blocked thing is tried first in a control child with no guard, where it must work,
  and then in the agent process, where it must be refused by name. It also checks that a model call through the
  pipe still works there, that a child past its limit is killed, and that a 2-second model call against a
  0.2-second limit ends in `ChildTimeout` in under a second.
- `test_mutation.py`: eight deliberate breakages, each applied to a temporary copy, must make the tests fail: no
  network block, no program block, no limit, no model-call thread, unknown request keys accepted, unknown
  settings keys accepted, an added retry, and a hardcoded stub. The real files are not changed.
