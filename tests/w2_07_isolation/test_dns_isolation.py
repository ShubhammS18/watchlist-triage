"""W2-07: every in-scope route by which the agent process could look up a host name is refused before any lookup.

Scope as in DEC-W2-07-SOCKET-BLOCK-2 and DEC-T04-AC11-SCOPE: ordinary, accidental and prompt-injected routes. Code
written to defeat the guard from inside the process is out of scope, and nothing here tests it.

The strongest proof counts queries: in a private network namespace with a fake name server, each route sends at
least one query from a control child with no block, and none at all from the agent process.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from model_interface.runner import run_child
from model_interface.stub import Stub

from w2_07_probes import MAKE_SOCKET, ROUTES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROBE = "tests.w2_07_isolation.w2_07_probes"
REFUSED = "blocked: blocked in the agent process: "

# route -> the audit event that must refuse it in the agent process
EXPECTED = {
    "connect": "socket.__new__",
    "connect_ex": "socket.__new__",
    "bind": "socket.__new__",
    "sendto": "socket.__new__",
    "sendmsg": "socket.__new__",
    "private_socket": "socket.__new__",
    "create_connection": "socket.getaddrinfo",
    "getaddrinfo": "socket.getaddrinfo",
    "gethostbyname": "socket.gethostbyname",
    "gethostbyname_ex": "socket.gethostbyname",
    "gethostbyaddr": "socket.gethostbyaddr",
    "getnameinfo": "socket.getnameinfo",
    "http_client": "socket.getaddrinfo",
    "urllib": "socket.getaddrinfo",
    "socketserver": "socket.__new__",
    "multiprocessing": "socket.__new__",
    "asyncio": "socket.__new__",  # its event loop makes a socket pair before anything else
    "ctypes": "ctypes.dlopen",
    "program": "subprocess.Popen",
}


def test_every_route_has_an_expected_refusal():
    assert sorted(EXPECTED) == sorted(ROUTES)


# ---- the count, in a private network namespace

@pytest.fixture(scope="module")
def counted(netns, tmp_path_factory):
    resolv_conf = tmp_path_factory.mktemp("netns").joinpath("resolv.conf")
    resolv_conf.write_text("nameserver 127.0.0.1\noptions timeout:1 attempts:1\n", encoding="utf-8")
    done = subprocess.run(["unshare", "-rnm", sys.executable, "-I", str(HERE.joinpath("netns_count.py")), str(ROOT),
                           str(resolv_conf)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.splitlines()[-1])


@pytest.mark.parametrize("route", ROUTES)
def test_the_route_sends_a_query_from_the_control_child(counted, route):
    # This is what shows that the counter sees real lookups.
    assert counted["control"]["queries"].get(counted["names"][route], 0) >= 1, counted["control"]["report"][route]


def test_no_dns_query_leaves_the_agent_process(counted):
    assert counted["control"]["total"] >= len(ROUTES)
    assert counted["agent"]["total"] == 0, counted["agent"]["queries"]
    assert counted["agent"]["report"] == {route: REFUSED + event for route, event in EXPECTED.items()}


# ---- without the namespace

def test_refused_before_the_resolver():
    # A gaierror would mean the resolver ran. The names never resolve, and none is looked up.
    routes = {route: "lookup-probe.invalid" for route in ROUTES}
    report = run_child(PROBE, {"routes": routes}, Stub(), limit_s=10)
    assert not [route for route, outcome in report.items() if "gaierror" in outcome]
    assert report == {route: REFUSED + event for route, event in EXPECTED.items()}


def test_no_socket_object_can_be_made():
    report = run_child(PROBE, {"make": list(MAKE_SOCKET), "unaudited_socketpair": True}, Stub(), limit_s=10)
    pair = report.pop("unaudited_socketpair")
    assert report == {f"make:{name}": REFUSED + "socket.__new__" for name in MAKE_SOCKET}
    # The one unaudited way to a socket object makes only local sockets, and these take no host name.
    assert pair == {"family": "AF_UNIX", "inet": "error: OSError: [Errno 95] Operation not supported",
                    "connect_with_a_name": "error: TypeError: a bytes-like object is required, not 'tuple'"}


def test_the_proof_cannot_be_skipped_by_the_old_variable():
    # WT_SKIP_NETNS once skipped the namespace proofs. It is gone: with it set, the proof still runs and passes.
    test = "tests/w2_07_isolation/test_dns_isolation.py::test_no_dns_query_leaves_the_agent_process"
    done = subprocess.run([sys.executable, "-m", "pytest", test, "-q", "-p", "no:cacheprovider", "-rs"], cwd=ROOT,
                          env={**os.environ, "WT_SKIP_NETNS": "1"}, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stdout
    assert "1 passed" in done.stdout and "skipped" not in done.stdout


# ---- the T04 name-lookup test, with no network at all

def test_t04_name_lookup_test_passes_with_no_network(netns):
    test = "tests/t04_model_interface/test_isolation.py::test_a_name_lookup_is_refused"
    done = subprocess.run(["unshare", "-rn", sys.executable, "-m", "pytest", test, "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stdout
    assert "1 passed" in done.stdout
