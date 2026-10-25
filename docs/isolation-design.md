# Name-lookup isolation for W2-07-dns-isolation

Requirements: FR-9 and the network part of AC-11. Decision records: `DEC-W2-07-SOCKET-BLOCK` and
`DEC-W2-07-NETNS-PROOF`, both owner decisions of 2026-10-25, within the scope set by `DEC-T04-AC11-SCOPE`.

## The gap

The T04 guard in the agent process (`model_interface/child.py`) refused `socket.connect`, `socket.bind`,
`socket.sendto` and `socket.sendmsg`. On Python 3.12.3, a socket's `connect`, `connect_ex`, `bind`, `sendto` and
`sendmsg` turn a host name into an address in C before they raise that event, and the C call is not the audited
`socket.getaddrinfo`. So the call was refused, but only after a name lookup had left the process. A fake name
server counting queries saw one under the old guard. It is also why `test_a_name_lookup_is_refused` in
`tests/t04_model_interface/` failed offline: its `connect` probe looked up `example.com`.

## The change

The guard in the agent process now refuses socket creation, not only connections: `"socket.__new__"` is added to
`BLOCKED`. With no socket object, the name-taking socket calls cannot be reached. The old socket events stay as a
second check. The agent process needs no socket: it hands model requests to the parent through a pipe, and the
parent makes the call.

Rejected: wrapping each socket method, which misses lookups made in C; refusing only internet sockets, which adds
logic for no use; and a network namespace around the agent process, which is the operating-system sandbox that
stays out of scope.

## Threat model

The claim covers ordinary, accidental and prompt-injected routes; hostile code inside the process stays out of
scope. This is a guard inside Python, as in T04: code in the process could put back what it replaces.

## What is covered and what is not

| Route | In the agent process |
|---|---|
| a socket's `connect`, `connect_ex`, `bind`, `sendto`, `sendmsg` with a name, also on the C type `_socket.socket` | refused at `socket.__new__` |
| libraries built on a socket object: `socketserver`, `multiprocessing.connection`, `asyncio` (its event loop makes a socket pair first) | refused at `socket.__new__` |
| `socket.create_connection` and what is built on it, such as `http.client` and `urllib.request` | refused at `socket.getaddrinfo`, as before |
| `getaddrinfo`, `gethostbyname`, `gethostbyname_ex`, `gethostbyaddr`, `getnameinfo` | refused by their own events, as before |
| `getent` or another program; libc's resolver through `ctypes` | refused by the program and ctypes blocks of T04 |
| every way to make a socket object: `socket.socket`, `socketpair`, `fromfd`, `socket(fileno=)`, `create_server`, `_socket.socket` | refused at `socket.__new__` |

Not covered:

- `_socket.socketpair()` raises no audit event and still works. It makes only local (AF_UNIX) sockets, which take
  no host name, and asking it for an internet pair fails. A test pins this down.
- `socket.getfqdn()` swallows the refusal and returns the name unchanged. It sends no query.
- Hostile code inside the process, as above.
- Only Python 3.12.3 on Linux (WSL2, glibc resolver) was tested. Another Python version may order the C lookup
  and the audit event differently.

## The evidence

`tests/w2_07_isolation/` (the gate `tests`) checks this four ways:

- **Counting queries.** Inside `unshare -rnm` (a private network and file view, no root) `/etc/resolv.conf` names a
  fake name server on 127.0.0.1 that counts every query. Every route above, given its own name, sends at least one
  query from a control child with no block, and the agent process sends none at all, each route refused by name.
- **Refused before the resolver.** Without the namespace, every route in the agent process ends in the guard's
  refusal and none in `gaierror`, the sign that the resolver ran.
- **No socket object.** Every way to make one is refused, and the one unaudited route is pinned down as above.
- **With no network.** The T04 name-lookup test passes inside `unshare -rn`.

A copy of the package with `"socket.__new__"` removed makes the first three fail (`test_dns_mutation.py`, run
inside `unshare -rn` so the broken copy cannot send a lookup off the machine).

The namespace proofs need Linux with unprivileged user namespaces. Where that is not available they fail with a
message saying so. `WT_SKIP_NETNS=1` skips them, with the message "zero-query proof did not run". The gate does not
set it.

## Supersedes

`docs/model-interface-design.md` stays as it was when T04 closed. These lines in it are out of date.

| Line | What it says | Now |
|---|---|---|
| `docs/model-interface-design.md:18-19` | agent code that tries to look up a name is refused | it was refused, but `connect` and the like had already sent the lookup; now each is refused before any lookup is sent |
| `docs/model-interface-design.md:94-95` | the network events the guard refuses | `socket.__new__` is refused as well |
