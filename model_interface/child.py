"""Start-up script of the agent process. It installs a network guard first, then runs the agent code.

Run by `runner.run_child` as `python -I child.py MODULE`. The agent code in MODULE gets one thing from outside:
a `model` that passes each request up the pipe to the parent, which owns the real model.

The guard also refuses starting another program and loading a library through ctypes, since either would be a
way around it. Importing ctypes loads a library, so the agent process cannot import ctypes at all. The private
launcher that `subprocess` is built on, `_posixsubprocess.fork_exec`, raises no audit event, so it is replaced
with a function that refuses, and importing a fresh copy of it is refused too.

Limit: this is a guard inside Python, not an operating-system sandbox. It stops ordinary and accidental use and
use that a prompt talks the agent into. It does not stop code written to defeat it: the replacements above are
plain assignments, and code in this process could put the originals back.
"""
import sys

BLOCKED = frozenset((
    # network
    "socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg",
    "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr", "socket.getnameinfo",
    # starting another program
    "subprocess.Popen", "os.system", "os.exec", "os.spawn", "os.posix_spawn", "os.fork", "os.forkpty",
    "os.startfile", "os.startfile/2", "pty.spawn",
    # loading a library through ctypes
    "ctypes.dlopen"))


# Modules that may not be imported once the launcher is closed: the launcher itself, and the modules that start
# a second interpreter, which would run without this hook.
NO_IMPORT = frozenset(("_posixsubprocess", "_xxsubinterpreters", "_xxinterpchannels"))
_launcher_closed = []


def _block(event, args):
    if event in BLOCKED:
        raise PermissionError(f"blocked in the agent process: {event}")
    if event == "import" and _launcher_closed and args[0] in NO_IMPORT:
        raise PermissionError(f"blocked in the agent process: import of {args[0]}")


def _refuse_launch(*args, **kwargs):
    raise PermissionError("blocked in the agent process: _posixsubprocess.fork_exec")


# Python offers no call to remove an audit hook once added, and the hook also sees calls that skip the `socket`
# module's own functions. `socket.create_connection` is covered because it looks the name up and then connects.
sys.addaudithook(_block)

# Everything below runs with the guard already installed.
import _imp  # noqa: E402

try:
    import _posixsubprocess  # noqa: E402
    import subprocess  # noqa: E402
    _posixsubprocess.fork_exec = subprocess._fork_exec = _refuse_launch
except ImportError:  # no such launcher on this platform
    pass


def _create_builtin(spec, _real=_imp.create_builtin):
    """Building a fresh copy of a built-in module raises no import event, so it is refused here instead."""
    if spec.name in NO_IMPORT:
        raise PermissionError(f"blocked in the agent process: import of {spec.name}")
    return _real(spec)


_imp.create_builtin = _create_builtin
_launcher_closed.append(True)

import importlib  # noqa: E402
import traceback  # noqa: E402
from dataclasses import asdict  # noqa: E402
from pathlib import Path  # noqa: E402


def main(module):
    to_parent, from_parent = sys.stdout, sys.stdin
    sys.stdout = sys.stderr  # a stray print must not corrupt the pipe
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # -I leaves the repository off the path
    from model_interface import ERRORS, Result, receive, send

    def model(request):
        send(to_parent, {"call": asdict(request)})
        reply = receive(from_parent)
        if reply is None:
            raise ERRORS["ModelError"]("the parent closed the pipe")
        if "error" in reply:
            raise ERRORS[reply["error"]["type"]](reply["error"]["message"])
        return Result(**reply["result"])

    try:
        payload = receive(from_parent)["payload"]
        message = {"done": importlib.import_module(module).main(model, payload)}
    except Exception:
        message = {"failed": traceback.format_exc()}
    send(to_parent, message)


if __name__ == "__main__":
    main(sys.argv[1])
