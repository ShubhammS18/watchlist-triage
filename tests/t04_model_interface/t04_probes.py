"""For tests only. This is not the agent. It adds probes to the ones in model_interface.probe_child.

It runs in two places: inside the agent process, started by `run_child`, and as the control, in a plain child
process that has no block at all. The same payload goes to both, so the block is the only difference.

Every program probe starts this same Python with `-c`. A probe named "audit:EVENT" raises that audit event by
hand, which is the only way to reach the events that real calls raise only on Windows.

A payload key "forged_call" sends that object up the pipe as a model call exactly as given, so that a test can
check what the parent does with a call of the wrong shape.
"""
import os
import pty
import socket
import subprocess
import sys
from dataclasses import make_dataclass

from model_interface import probe_child

PYTHON = [sys.executable, "-I", "-c", "pass"]


def _wait(pid):
    if os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]) != 0:
        raise RuntimeError("the started program did not finish cleanly")


def _must_be_zero(status):
    if status != 0:
        raise RuntimeError(f"the started program ended with status {status}")


def _bind(host, port):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))


def _sendmsg(host, port):
    with socket.socket(type=socket.SOCK_DGRAM) as sock:
        sock.sendmsg([b"probe"], [], 0, (host, port))


def _fork(host, port):
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    _wait(pid)


def _forkpty(host, port):
    pid, fd = os.forkpty()
    if pid == 0:
        os._exit(0)
    _wait(pid)
    os.close(fd)


EXTRA = {
    "bind": _bind,
    "sendmsg": _sendmsg,
    "gethostbyaddr": lambda host, port: socket.gethostbyaddr("127.0.0.1"),
    "getnameinfo": lambda host, port: socket.getnameinfo(("127.0.0.1", port), socket.NI_NUMERICHOST),
    "subprocess": lambda host, port: subprocess.run(PYTHON, check=True),
    "system": lambda host, port: _must_be_zero(os.system(" ".join(PYTHON))),
    "exec": lambda host, port: os.execv(PYTHON[0], [*PYTHON[:-1], "print('EXEC-REACHED')"]),
    "spawn": lambda host, port: _must_be_zero(os.spawnv(os.P_WAIT, PYTHON[0], PYTHON)),
    "posix_spawn": lambda host, port: _wait(os.posix_spawn(PYTHON[0], PYTHON, {})),
    "fork": _fork,
    "forkpty": _forkpty,
    "pty_spawn": lambda host, port: _must_be_zero(pty.spawn(PYTHON)),
}


def main(model, payload):
    """Same payload as model_interface.probe_child.main, with the extra probe names allowed."""
    probe_child.PROBES.update(EXTRA)
    for name in payload.get("probes", []):
        if name.startswith("audit:"):
            probe_child.PROBES[name] = lambda host, port, event=name[len("audit:"):]: sys.audit(event)
    if "forged_call" in payload:
        call = payload["forged_call"]
        model(make_dataclass("Forged", list(call))(**call))  # the parent should end the run here
        return {"forged_call": "accepted"}
    return probe_child.main(model, payload)
