"""For tests only. Runs inside `unshare -rnm`: a private network with only the loopback device, and a private view
of the files, where /etc/resolv.conf names a fake name server on 127.0.0.1. That server counts every query it
gets, by name, and answers each with "no such name" at once. Nothing here can reach a real network.

It runs the routes of w2_07_probes twice with the same payload, first in a control child with no block and then in
the agent process, and prints, as JSON, each one's report and the queries the server got during it.

Usage: python -I netns_count.py REPO_ROOT FAKE_RESOLV_CONF
"""
import json
import socket
import subprocess
import sys
import threading
import time
from collections import Counter

ROOT, RESOLV_CONF = sys.argv[1], sys.argv[2]
sys.path.insert(0, ROOT)

from model_interface.runner import run_child  # noqa: E402
from model_interface.stub import Stub  # noqa: E402
from tests.w2_07_isolation import w2_07_probes  # noqa: E402

CONTROL = ("import json, sys; sys.path.insert(0, sys.argv[1]); "
           "from tests.w2_07_isolation import w2_07_probes; "
           "print(json.dumps(w2_07_probes.main(None, json.loads(sys.argv[2]))))")
SETTLE_S = 0.5  # time for the last query to be counted once a child has ended


def query_name(packet):
    """The name asked for in a DNS query, or None where the packet does not parse."""
    labels, at = [], 12
    try:
        while packet[at]:
            labels.append(packet[at + 1:at + 1 + packet[at]].decode("ascii"))
            at += 1 + packet[at]
    except (IndexError, UnicodeDecodeError):
        return None
    return ".".join(labels).lower()


def no_such_name(packet):
    """The answer "no such name" to a query: the same id and question, flags set to a response with rcode 3."""
    end = packet.index(0, 12) + 5
    return packet[:2] + b"\x81\x83" + packet[4:6] + b"\x00\x00\x00\x00\x00\x00" + packet[12:end]


def serve(sock, queries):
    while True:
        packet, sender = sock.recvfrom(4096)
        queries[query_name(packet)] += 1
        try:
            sock.sendto(no_such_name(packet), sender)
        except ValueError:
            pass


def counted(run, queries):
    queries.clear()
    report = run()
    time.sleep(SETTLE_S)
    return {"report": report, "queries": dict(queries), "total": sum(queries.values())}


def main():
    subprocess.run(["ip", "link", "set", "lo", "up"], check=True)
    subprocess.run(["mount", "--bind", RESOLV_CONF, "/etc/resolv.conf"], check=True)
    queries = Counter()
    server = socket.socket(type=socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 53))
    threading.Thread(target=serve, args=(server, queries), daemon=True).start()

    hosts = {route: f"{route.replace('_', '-')}.lookup-probe.invalid" for route in w2_07_probes.ROUTES}
    # getnameinfo refuses a name without looking it up; what it looks up is the name of an address
    hosts["getnameinfo"] = "192.0.2.1"
    payload = {"routes": hosts}

    def control():
        done = subprocess.run([sys.executable, "-I", "-c", CONTROL, ROOT, json.dumps(payload)], env={},
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout.splitlines()[-1])

    result = {"names": {**hosts, "getnameinfo": "1.2.0.192.in-addr.arpa"},
              "control": counted(control, queries),
              "agent": counted(lambda: run_child("tests.w2_07_isolation.w2_07_probes", payload, Stub()), queries)}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
