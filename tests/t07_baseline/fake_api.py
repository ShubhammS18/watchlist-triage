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
    """A local server that records every request and answers with `self.script(handler, body)`."""
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

    def log_message(self, *args):
        pass


def answer(handler, status, reply, headers=()):
    data = reply if isinstance(reply, bytes) else json.dumps(reply).encode()
    handler.send_response(status)
    for name, value in (("content-type", "application/json"), ("content-length", str(len(data))), *headers):
        handler.send_header(name, value)
    handler.end_headers()
    handler.wfile.write(data)


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv(KEY_VARIABLE, CANARY)
    fake = Fake()
    thread = threading.Thread(target=fake.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    yield fake
    fake.shutdown()
    fake.server_close()
