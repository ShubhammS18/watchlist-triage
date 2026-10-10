"""T04: the guard in the agent process refuses the ordinary routes to anything but the model interface.

This covers the network part of AC-11 in the scope set by DEC-T04-AC11-SCOPE: ordinary, accidental and
prompt-injected routes. Code written to defeat the guard from inside the process is out of scope, and nothing
here tests it. This is a guard inside Python, not an operating-system sandbox.

Each blocked thing is tried twice with the same payload: first in a control child that has no block, where it
must work, and then in the agent process, where it must be refused by name.
"""
import ast
import inspect
import json
import socket
import subprocess
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path

import pytest

from model_interface import Request, Settings, runner
from model_interface.runner import CHILD, ChildError, ChildTimeout, run_child
from model_interface.stub import Stub

ROOT = Path(__file__).resolve().parents[2]
PROBE = "tests.t04_model_interface.t04_probes"
REQUEST = asdict(Request([{"role": "user", "content": "ping"}], Settings("stub-1", 0, 64, 5)))
REFUSED = "blocked: blocked in the agent process: "

# probe name -> the audit event that must refuse it
NETWORK = {
    "connect": "socket.connect",
    "create_connection": "socket.getaddrinfo",  # it looks the name up first, and that is already refused
    "sendto": "socket.sendto",
    "sendmsg": "socket.sendmsg",
    "bind": "socket.bind",
    "getaddrinfo": "socket.getaddrinfo",
    "gethostbyname": "socket.gethostbyname",
    "gethostbyaddr": "socket.gethostbyaddr",
    "getnameinfo": "socket.getnameinfo",
}
PROGRAMS = {
    "subprocess": "subprocess.Popen",
    "system": "os.system",
    "exec": "os.exec",
    "spawn": "os.fork",  # on Linux os.spawnv forks and then execs
    "posix_spawn": "os.posix_spawn",
    "fork": "os.fork",
    "forkpty": "os.forkpty",
    "pty_spawn": "pty.spawn",
    "ctypes": "ctypes.dlopen",
}
# No real call raises these on Linux, so they are only raised by hand.
WINDOWS_ONLY = ("os.spawn", "os.startfile", "os.startfile/2")
EVENTS = sorted({*NETWORK.values(), *PROGRAMS.values(), *WINDOWS_ONLY})

CONTROL = ("import json, sys; sys.path.insert(0, sys.argv[1]); "
           "from tests.t04_model_interface import t04_probes; "
           "print(json.dumps(t04_probes.main(None, json.loads(sys.argv[2]))))")


def run_control(payload):
    """Run the probes in a child started the same way as the agent process but with no block. Returns its output."""
    done = subprocess.run([sys.executable, "-I", "-c", CONTROL, str(ROOT), json.dumps(payload)],
                          env={}, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout


def arrivals(server):
    """How many connections reached the test's server since the last count."""
    count = 0
    while True:
        try:
            server.accept()[0].close()
        except TimeoutError:
            return count
        count += 1


@pytest.fixture(scope="module")
def server():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        sock.settimeout(0.5)
        yield sock


@pytest.fixture(scope="module")
def payload(server):
    probes = [*NETWORK, *(name for name in PROGRAMS if name != "exec"), *(f"audit:{event}" for event in EVENTS)]
    return {"probes": probes, "host": "localhost", "port": server.getsockname()[1]}


@pytest.fixture(scope="module")
def control(server, payload):
    """(report, connections that arrived) for the child with no block. Always runs before the blocked child."""
    return json.loads(run_control(payload).splitlines()[-1]), arrivals(server)


@pytest.fixture(scope="module")
def blocked(server, payload, control):
    """(report, connections that arrived) for the agent process, given the same payload plus one model call."""
    return run_child(PROBE, {**payload, "request": REQUEST}, Stub()), arrivals(server)


# ---- network

def test_control_child_without_the_block_connects_to_the_local_server(control):
    report, arrived = control
    assert report["connect"] == "reached" and report["create_connection"] == "reached"
    assert arrived == 2


def test_no_connection_from_the_agent_process_arrives_at_the_local_server(blocked):
    assert blocked[1] == 0


@pytest.mark.parametrize("probe", NETWORK)
def test_network_route_works_in_the_control_and_is_refused_in_the_agent_process(control, blocked, probe):
    assert control[0][probe] == "reached"
    assert blocked[0][probe] == REFUSED + NETWORK[probe]


def test_a_model_call_through_the_pipe_still_works_in_the_agent_process(blocked):
    assert blocked[0]["result"] == {"text": "stub reply", "model_id": "stub-1", "input_tokens": None,
                                    "output_tokens": None, "latency_s": 0.0}


def test_an_outside_address_is_refused():
    probes = ["connect", "create_connection", "sendto", "sendmsg"]
    report = run_child(PROBE, {"probes": probes, "host": "203.0.113.1", "port": 80}, Stub(), limit_s=5)
    assert report == {probe: REFUSED + NETWORK[probe] for probe in probes}


def test_a_name_lookup_is_refused():
    probes = ["getaddrinfo", "gethostbyname", "connect", "create_connection"]
    report = run_child(PROBE, {"probes": probes, "host": "example.com", "port": 443}, Stub(), limit_s=5)
    assert report == {probe: REFUSED + NETWORK[probe] for probe in probes}


# ---- starting other programs, and loading a library through ctypes

@pytest.mark.parametrize("probe", [name for name in PROGRAMS if name != "exec"])
def test_program_start_works_in_the_control_and_is_refused_in_the_agent_process(control, blocked, probe):
    assert control[0][probe] == "reached"
    assert blocked[0][probe] == REFUSED + PROGRAMS[probe]


def test_exec_works_in_the_control_and_is_refused_in_the_agent_process():
    # exec replaces the process that calls it, so it gets a child of its own in both halves
    assert "EXEC-REACHED" in run_control({"probes": ["exec"]})
    assert run_child(PROBE, {"probes": ["exec"]}, Stub()) == {"exec": REFUSED + PROGRAMS["exec"]}


# ---- the hook itself

@pytest.mark.parametrize("event", EVENTS)
def test_event_raised_by_hand_passes_in_the_control_and_is_refused_in_the_agent_process(control, blocked, event):
    assert control[0][f"audit:{event}"] == "reached"
    assert blocked[0][f"audit:{event}"] == REFUSED + event


def child_source():
    return ast.parse(CHILD.read_text(encoding="utf-8")).body


def test_every_event_the_hook_blocks_is_covered_here():
    assigned = next(node for node in child_source() if isinstance(node, ast.Assign) and node.targets[0].id == "BLOCKED")
    assert sorted(ast.literal_eval(assigned.value.args[0])) == EVENTS


def test_the_block_is_installed_before_anything_else_is_imported():
    body = child_source()
    installed = next(n for n, node in enumerate(body) if ast.unparse(node) == "sys.addaudithook(_block)")
    imports = [ast.unparse(node) for node in body[:installed] if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert imports == ["import sys"]
    assert not [node for node in body[:installed] if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)]


# ---- how the agent process is started, and the wall-clock limit

@pytest.fixture
def started(monkeypatch):
    """Every child process that run_child starts during the test, with the arguments it was started with."""
    real, seen = subprocess.Popen, []

    def record(*args, **kwargs):
        seen.append((real(*args, **kwargs), args, kwargs))
        return seen[-1][0]

    monkeypatch.setattr(runner.subprocess, "Popen", record)
    return seen


def test_the_agent_process_is_an_isolated_python_with_an_empty_environment(started):
    assert run_child(PROBE, {}, Stub()) == {}
    (process, args, kwargs), = started
    assert args[0][:3] == [sys.executable, "-I", str(CHILD)]
    assert kwargs["env"] == {}
    assert process.poll() is not None


def test_a_child_that_sleeps_past_the_limit_is_killed_and_reported_by_name(started):
    begun = time.monotonic()
    with pytest.raises(ChildTimeout) as caught:
        run_child(PROBE, {"sleep_s": 5}, Stub(), limit_s=1)
    assert time.monotonic() - begun < 4
    assert isinstance(caught.value, ChildError) and "1 seconds" in str(caught.value)
    assert started[0][0].poll() == -9


def test_a_model_call_that_outlasts_the_limit_ends_the_run_on_time(started):
    returned = threading.Event()

    def slow(request):
        time.sleep(2)
        returned.set()
        return Stub()(request)

    begun = time.monotonic()
    with pytest.raises(ChildTimeout):
        run_child(PROBE, {"request": REQUEST}, slow, limit_s=0.2)
    assert time.monotonic() - begun < 1
    assert started[0][0].poll() == -9
    # The model call was abandoned, not stopped: its thread lingers until the call returns.
    assert not returned.is_set()
    assert returned.wait(5)


def test_a_fault_in_the_model_itself_reaches_the_caller_unchanged():
    def broken(request):
        raise ZeroDivisionError("a bug in the model, not a ModelError")

    with pytest.raises(ZeroDivisionError):
        run_child(PROBE, {"request": REQUEST}, broken)


def test_a_child_inside_the_limit_is_not_reported_as_timed_out():
    assert run_child(PROBE, {"sleep_s": 0.2, "request": REQUEST}, Stub(), limit_s=30)["result"]["text"] == "stub reply"


def test_the_default_limit_is_sixty_seconds():
    assert inspect.signature(run_child).parameters["limit_s"].default == 60


def test_a_child_that_fails_is_reported_and_not_mistaken_for_a_timeout():
    with pytest.raises(ChildError) as caught:
        run_child("tests.t04_model_interface.no_such_module", {}, Stub())
    assert not isinstance(caught.value, ChildTimeout) and "ModuleNotFoundError" in str(caught.value)
