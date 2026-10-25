# W2-07-dns-isolation — independent review, round 2

Review range: `b1c13d0..HEAD` (`f9acf2e`). Scope: round 1 findings 1–3, the two superseding decisions, and errors introduced by changed lines. Repo unchanged.

## Round 1 findings

1. **RESOLVED — `tests/w2_07_isolation/conftest.py:12-24`; `.genesis/project.json:1744-1752`.** The `WT_SKIP_NETNS` branch is removed. Namespace failure now fails the tests, and `DEC-W2-07-NETNS-PROOF-2` supersedes the inaccurate gate claim. `tests/w2_07_isolation/test_dns_isolation.py:98-104` checks that setting the old variable still runs the zero-query proof. The fixed gate command therefore has no suite-provided skip path for this proof.

2. **RESOLVED — `tests/w2_07_isolation/conftest.py:16-23`.** A nonzero availability probe with empty stderr now reports its exit status. A timeout also receives a clear failure message.

3. **NOT RESOLVED — `docs/isolation-design.md:62`.** The table at `:41` now correctly says “audited socket-creation routes,” the exception is explicit at `:45-47`, and `DEC-W2-07-SOCKET-BLOCK-2` at `.genesis/project.json:1731-1741` qualifies the old absolute title. But the evidence bullet still says “Every way to make one is refused,” although `_socket.socketpair()` makes AF_UNIX sockets. **NIT; fix:** change that bullet to “The listed audited ways to make a socket are refused; the unaudited local socket pair is checked separately.”

## New issues on changed lines

None found.

## Test observation

I ran `.venv/bin/python -m pytest tests/w2_07_isolation -q -p no:cacheprovider`. It exited 1 (`3 failed, 3 passed, 20 errors`) because this sandbox permits `unshare -rnm true` but denies `ip link set lo up` inside the namespace (`Cannot open netlink socket: Operation not permitted`). It also denies the AF_INET socket-pair probe with EPERM rather than the expected ENOTSUP. These failures arise from sandbox permissions in unchanged test paths; they do not establish a regression in this diff or a successful zero-query proof here.
