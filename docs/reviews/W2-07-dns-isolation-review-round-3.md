# W2-07-dns-isolation — independent review, round 3

Review range: `HEAD~1..HEAD` (`021a921`). Repo unchanged.

## Checks

1. **RESOLVED — `docs/isolation-design.md:62-63`.** The evidence bullet now limits refusal to the listed audited socket-creation routes and checks the unaudited local socket pair separately. This removes round 2 finding 3.

2. **RESOLVED — `tests/w2_07_isolation/conftest.py:13-24`.** The availability probe now checks the loopback operation required by the proof, and a failure gives the specific command and cause. Nonzero exit with empty stderr and timeout still have fallback messages. This is correct for the sandbox failure seen in round 2.

3. **RESOLVED — `tests/w2_07_isolation/w2_07_probes.py:133-154`; `tests/w2_07_isolation/test_dns_isolation.py:94-103`.** The AF_INET pair probe now records whether a pair was returned and the OSError errno. The assertion requires no returned pair and an OSError, without hard-coding errno 95. An EPERM denial and an EOPNOTSUPP denial both establish that no AF_INET pair was created in the tested environment; a successful pair fails the test.

## New issues on changed lines

None found.

## W2-07 test run

Command: `.venv/bin/python -m pytest tests/w2_07_isolation -q -p no:cacheprovider`.

Result: exit 1, `1 failed, 3 passed, 22 errors`. The 22 fixture errors now all give the same clear cause: `zero-query proof cannot run: unshare -rnm ip link set lo up failed here (Cannot open netlink socket: Operation not permitted)`. The old-variable nested test also fails because it requires that proof to pass. Thus the failure has one distinct availability cause, but pytest does not print it just once. The zero-query proof could not run in this sandbox.
