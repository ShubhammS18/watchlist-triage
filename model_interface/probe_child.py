"""For tests only. This is not the agent.

It runs inside the agent process, tries each blocked thing that the payload names, optionally sleeps, optionally
asks the model once, and reports what happened so that a test can check the block, the time limit and the pipe.
"""
import os
import socket
import subprocess
import time
from dataclasses import asdict

from . import ModelError, request_from

PROGRAM = "/bin/true"


def _connect(host, port):
    with socket.socket() as sock:
        sock.connect((host, port))


def _create_connection(host, port):
    socket.create_connection((host, port), timeout=2).close()


def _sendto(host, port):
    with socket.socket(type=socket.SOCK_DGRAM) as sock:
        sock.sendto(b"probe", (host, port))


def _fork(host, port):
    if os.fork() == 0:
        os._exit(0)  # only reached if the block is missing


def _ctypes(host, port):
    import ctypes
    ctypes.CDLL(None)


PROBES = {
    "connect": _connect,
    "create_connection": _create_connection,
    "sendto": _sendto,
    "getaddrinfo": lambda host, port: socket.getaddrinfo(host, port),
    "gethostbyname": lambda host, port: socket.gethostbyname(host),
    "subprocess": lambda host, port: subprocess.run([PROGRAM]),
    "system": lambda host, port: os.system(PROGRAM),
    "exec": lambda host, port: os.execv(PROGRAM, [PROGRAM]),
    "spawn": lambda host, port: os.spawnv(os.P_WAIT, PROGRAM, [PROGRAM]),
    "posix_spawn": lambda host, port: os.posix_spawn(PROGRAM, [PROGRAM], {}),
    "fork": _fork,
    "ctypes": _ctypes,
}


def _attempt(probe, host, port):
    try:
        probe(host, port)
    except PermissionError as error:
        return f"blocked: {error}"
    except OSError as error:
        return f"error: {error}"
    return "reached"


def main(model, payload):
    """Payload keys, all optional: "probes" (names), "host", "port", "sleep_s", "request" (a request as JSON)."""
    host, port = payload.get("host", "127.0.0.1"), payload.get("port", 9)
    report = {name: _attempt(PROBES[name], host, port) for name in payload.get("probes", [])}
    time.sleep(payload.get("sleep_s", 0))
    if "request" in payload:
        try:
            report["result"] = asdict(model(request_from(payload["request"])))
        except ModelError as error:
            report["model_error"] = type(error).__name__
    return report
