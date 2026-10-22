"""T07: a fake Anthropic API on this machine, shared by the T07 tests. No internet, no key."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from model_interface.anthropic_api import KEY_VARIABLE

CANARY = "sk-ant-CANARY-0f3c9a7e-not-a-real-key"
OK = {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
      "content": [{"type": "thinking", "thinking": "", "signature": "x"}, {"type": "text", "text": "pong"}],
      "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 12, "output_tokens": 3}}


class Fake(ThreadingHTTPServer):
    """A local server that records POST, GET, PUT, DELETE, HEAD and PATCH requests. It answers a POST with
    `self.script(handler, body)` and the others with 405."""
    daemon_threads = True
    request_queue_size = 64  # above the thread test's 8 at once, so no connection waits for a retry

    def __init__(self):
        super().__init__(("127.0.0.1", 0), Handler)
        self.requests, self.lock = [], threading.Lock()
        self.script = lambda handler, body: answer(handler, 200, OK)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["content-length"]))
        with self.server.lock:
            self.server.requests.append({"method": self.command, "path": self.path, "headers": dict(self.headers),
                                         "body": json.loads(body)})
        self.server.script(self, json.loads(body))

    def _other(self):
        """Any other method is recorded too, so a redirect followed as a GET (as urllib does) is seen; then 405."""
        with self.server.lock:
            self.server.requests.append({"method": self.command, "path": self.path, "headers": dict(self.headers),
                                         "body": None})
        answer(self, 405, {"error": {"type": "method_not_allowed", "message": "fake"}})

    do_GET = do_PUT = do_DELETE = do_HEAD = do_PATCH = _other

    def log_message(self, *args):
        pass


def answer(handler, status, reply, headers=()):
    data = reply if isinstance(reply, bytes) else json.dumps(reply).encode()
    handler.send_response(status)
    for name, value in (("content-type", "application/json"), ("content-length", str(len(data))), *headers):
        handler.send_header(name, value)
    handler.end_headers()
    handler.wfile.write(data)


def _serve():
    fake = Fake()
    threading.Thread(target=fake.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
    return fake


def _stop(fake):
    fake.shutdown()
    fake.server_close()


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv(KEY_VARIABLE, CANARY)
    fake = _serve()
    yield fake
    _stop(fake)


@pytest.fixture
def other_server():
    """A second fake server, the target of a redirect: it must never be reached."""
    fake = _serve()
    yield fake
    _stop(fake)
