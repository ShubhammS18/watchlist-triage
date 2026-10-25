"""For tests only. This is not the agent. It tries every in-scope route by which Python code could look a host name
up, and every way to make a socket object, and reports what happened.

It runs in two places: inside the agent process, started by `run_child`, and as the control, in a plain child
process that has no block at all. The same payload goes to both, so the block is the only difference.

Payload: "routes" maps a route name to the host name that route must use. Each route gets its own name, so a
server counting name lookups can tell which route sent one.
"""
import os
import socket
import subprocess

PORT = 80


def _with_socket(call, kind=socket.SOCK_STREAM):
    def route(host):
        with socket.socket(type=kind) as sock:
            call(sock, (host, PORT))
    return route


def _private_socket(host):
    import _socket
    sock = _socket.socket()
    try:
        sock.connect((host, PORT))
    finally:
        sock.close()


def _http(host):
    import http.client
    http.client.HTTPConnection(host, PORT, timeout=2).request("GET", "/")


def _urllib(host):
    import urllib.request
    urllib.request.urlopen(f"http://{host}/", timeout=2)


def _socketserver(host):
    import socketserver
    socketserver.TCPServer((host, PORT), socketserver.BaseRequestHandler).server_close()


def _multiprocessing(host):
    from multiprocessing.connection import Client
    Client((host, PORT))


def _asyncio(host):
    import asyncio
    loop = asyncio.new_event_loop()  # makes a socket pair of its own
    try:
        loop.run_until_complete(loop.getaddrinfo(host, PORT))
    finally:
        loop.close()


def _ctypes(host):
    import ctypes
    ctypes.CDLL(None).gethostbyname(host.encode())


def _from_fd(make):
    """Make a socket object from the file descriptor of a real socket, taken from the unaudited socket pair."""
    import _socket
    first, second = _socket.socketpair()
    try:
        make(first.fileno()).close()
    finally:
        first.close()
        second.close()


def _program(host):
    subprocess.run(["getent", "hosts", host], stdout=subprocess.DEVNULL)


ROUTES = {
    "connect": _with_socket(lambda sock, address: sock.connect(address)),
    "connect_ex": _with_socket(lambda sock, address: sock.connect_ex(address)),
    "bind": _with_socket(lambda sock, address: sock.bind(address)),
    "sendto": _with_socket(lambda sock, address: sock.sendto(b"probe", address), socket.SOCK_DGRAM),
    "sendmsg": _with_socket(lambda sock, address: sock.sendmsg([b"probe"], [], 0, address), socket.SOCK_DGRAM),
    "private_socket": _private_socket,
    "create_connection": lambda host: socket.create_connection((host, PORT), timeout=2).close(),
    "getaddrinfo": lambda host: socket.getaddrinfo(host, PORT),
    "gethostbyname": socket.gethostbyname,
    "gethostbyname_ex": socket.gethostbyname_ex,
    "gethostbyaddr": socket.gethostbyaddr,
    "getnameinfo": lambda host: socket.getnameinfo((host, PORT), 0),
    "http_client": _http,
    "urllib": _urllib,
    "socketserver": _socketserver,
    "multiprocessing": _multiprocessing,
    "asyncio": _asyncio,
    "ctypes": _ctypes,
    "program": _program,
}

MAKE_SOCKET = {
    "socket": lambda: socket.socket().close(),
    "socketpair": lambda: [sock.close() for sock in socket.socketpair()],
    "fromfd": lambda: _from_fd(lambda fd: socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)),
    "fileno": lambda: _from_fd(lambda fd: socket.socket(fileno=os.dup(fd))),
    "create_server": lambda: socket.create_server(("127.0.0.1", 0)).close(),
    "private_socket": lambda: __import__("_socket").socket().close(),  # the C type under socket.socket
}


def _refusal(error):
    """The guard's refusal behind an error, if any. Some libraries wrap it: urllib in URLError, for example."""
    while error is not None:
        if isinstance(error, PermissionError):
            return error
        error = error.reason if isinstance(getattr(error, "reason", None), BaseException) else (
            error.__cause__ or error.__context__)
    return None


def _attempt(call, *args):
    try:
        call(*args)
    except Exception as error:
        refusal = _refusal(error)
        return f"blocked: {refusal}" if refusal else f"error: {type(error).__name__}: {error}"
    return "reached"


def _unaudited_socketpair():
    """The one way to get a socket object that raises no audit event. It makes only local (AF_UNIX) sockets."""
    import _socket
    first, second = _socket.socketpair()
    try:
        return {"family": socket.AddressFamily(first.family).name,
                "inet": _attempt(_socket.socketpair, socket.AF_INET),
                "connect_with_a_name": _attempt(first.connect, ("lookup-probe.invalid", PORT))}
    finally:
        first.close()
        second.close()


def main(model, payload):
    report = {name: _attempt(ROUTES[name], host) for name, host in payload.get("routes", {}).items()}
    report.update({f"make:{name}": _attempt(MAKE_SOCKET[name]) for name in payload.get("make", [])})
    if payload.get("unaudited_socketpair"):
        report["unaudited_socketpair"] = _unaudited_socketpair()
    return report
