"""The Anthropic Messages API as a model, for task T07 (DEC-T07-ADAPTER). Python standard library only.

One call is one HTTP request: no tools, no streaming, no retries and no waiting on `retry-after`, because retries
belong to the baseline agent (DEC-T05-RETRIES). `timeout_s` is one deadline for sending the request and reading
the reply, so a reply that trickles in slowly still ends on time. Connecting starts with the time left but is not
cut at the deadline: the name lookup has no timeout, and the TCP connect and TLS handshake each get the time left.
The agent's child-process limit bounds the whole call.

The API key is read from the environment variable WT_ANTHROPIC_API_KEY when the model is made, and from nowhere
else. It is sent only in the x-api-key header, and no error text or repr names it.

How an answer becomes a result or an error:

    200 with text blocks              Result: the text of the "text" blocks, the reported model ID as text,
                                      token counts from usage (None where missing)
    200, stop_reason "refusal"        ModelRefusal
    200 with no text, or unreadable   BadReply
    400 "usage limits", 402           ProviderError naming the spend limit
    429                               ProviderError naming the rate limit (or the spend cap)
    529                               ProviderError naming the overload
    500, 504, any other 5xx           ProviderError naming a server error
    any other status                  ProviderError naming the refused request
    timeout_s passed                  ModelTimeout
    connection failed or broken       ProviderError
"""
import http.client
import io
import json
import os
import time
from urllib.parse import urlsplit

from . import BadReply, ModelRefusal, ModelTimeout, ProviderError, Request, Result

KEY_VARIABLE = "WT_ANTHROPIC_API_KEY"
API_URL = "https://api.anthropic.com"
VERSION = "2023-06-01"
LOCAL_HOSTS = ("127.0.0.1", "localhost")  # plain http is allowed only here, for the fake servers of the tests


class _Deadline:
    """Wraps a connected socket so that every send and read has only the time left until `deadline`.

    http.client sends through `sendall` and reads the status line, the headers and the body through the file that
    `makefile` returns, so these two cover every byte sent and read after the connection is made.
    """

    def __init__(self, sock, deadline):
        self._sock, self._deadline = sock, deadline

    def _left(self):
        left = self._deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("the deadline passed")
        self._sock.settimeout(left)

    def sendall(self, data):
        self._left()
        self._sock.sendall(data)

    def makefile(self, mode="rb", *args, **kwargs):
        # The socket's own file keeps it open while a response is still being read after the connection is
        # closed, as http.client does for a reply that ends the connection.
        raw, left = self._sock.makefile("rb", buffering=0), self._left

        class Reader(io.RawIOBase):
            def readable(self):
                return True

            def readinto(self, buffer):
                left()
                return raw.readinto(buffer)

            def close(self):
                raw.close()
                super().close()

        return io.BufferedReader(Reader())

    def close(self):
        self._sock.close()


class Anthropic:
    """A model that asks the Anthropic Messages API. Made by the configuration loader from its `options`.

    `thinking` must be "disabled": it is in the options so that the configuration file, and so its hash in every
    manifest, says how the model was asked. `base_url` exists for the tests; only the Anthropic API or a local
    test server is accepted, so a configuration cannot send the key anywhere else.
    """

    def __init__(self, thinking, base_url=API_URL):
        if thinking != "disabled":
            raise ValueError('thinking must be "disabled"')
        url = urlsplit(base_url)
        if not (base_url == API_URL or (url.scheme == "http" and url.hostname in LOCAL_HOSTS and url.path == "")):
            raise ValueError(f"base_url must be {API_URL} or a local test server")
        key = os.environ.get(KEY_VARIABLE, "")
        if not key.strip():
            raise ValueError(f"the API key is missing: set {KEY_VARIABLE}")
        # http.client quotes a bad header value in its error text, so a key it would refuse is refused here first
        if not (key.isascii() and key.isprintable() and not any(c.isspace() for c in key)):
            raise ValueError(f"{KEY_VARIABLE} holds characters an API key cannot have")
        self._key, self._url, self._thinking = key, url, thinking

    def __repr__(self):
        return f"Anthropic(thinking={self._thinking!r}, base_url={self._url.geturl()!r})"

    def __call__(self, request):
        if not isinstance(request, Request):
            raise TypeError("the adapter takes a Request")
        settings = request.settings
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        body = {"model": settings.model, "max_tokens": settings.max_tokens, "temperature": settings.temperature,
                "thinking": {"type": self._thinking}}
        if messages[0]["role"] == "system":  # the API takes the opening system message as a top-level field
            body["system"] = messages.pop(0)["content"]
        body["messages"] = messages
        begun = time.monotonic()
        status, raw = self._post(json.dumps(body).encode("utf-8"), begun + settings.timeout_s)
        latency_s = time.monotonic() - begun
        reply = _json_or_none(raw)
        if status != 200:
            raise ProviderError(_failure(status, reply))
        return _result(reply, latency_s)

    def _post(self, data, deadline):
        """Send one request and return (status, body bytes). Never retried."""
        left = deadline - time.monotonic()
        kind = http.client.HTTPSConnection if self._url.scheme == "https" else http.client.HTTPConnection
        connection = kind(self._url.hostname, self._url.port, timeout=max(left, 0.001))
        headers = {"x-api-key": self._key, "anthropic-version": VERSION, "content-type": "application/json"}
        try:
            connection.connect()
            connection.sock = _Deadline(connection.sock, deadline)
            connection.request("POST", "/v1/messages", body=data, headers=headers)
            response = connection.getresponse()
            return response.status, response.read()
        except TimeoutError:
            raise ModelTimeout("the model did not answer within timeout_s") from None
        except (OSError, http.client.HTTPException) as error:
            raise ProviderError(f"the connection to the provider failed: {type(error).__name__}") from None
        finally:
            connection.close()


def _json_or_none(raw):
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _failure(status, reply):
    """The error text for a status other than 200. It names the status and the error type, never the key."""
    error = reply.get("error") if isinstance(reply, dict) else None
    error = error if isinstance(error, dict) else {}
    kind = error.get("type") if isinstance(error.get("type"), str) else "unknown"
    message = error.get("message") if isinstance(error.get("message"), str) else ""
    details = error.get("details") if isinstance(error.get("details"), dict) else {}
    if status == 402 or (status == 400 and "usage limits" in message):
        what = "spend limit reached"
    elif status == 429:
        what = ("spend cap reached" if details.get("error_code") == "enforced_spend_limit_reached"
                else "rate limit reached")
    elif status == 529:
        what = "provider overloaded"
    elif status >= 500:
        what = "provider server error"
    else:
        what = "request refused by the provider"
    return f"{what}: HTTP {status} {kind}"


def _result(reply, latency_s):
    """A Result from a 200 reply, or the error that the reply amounts to."""
    if not isinstance(reply, dict):
        raise BadReply("the provider's reply is not a JSON object")
    if reply.get("stop_reason") == "refusal":
        details = reply.get("stop_details") if isinstance(reply.get("stop_details"), dict) else {}
        raise ModelRefusal(f"the model refused: category {details.get('category')}")
    model_id = reply.get("model")
    if isinstance(model_id, bool) or not isinstance(model_id, (str, int, float)):
        raise BadReply("the provider's reply names no model")
    blocks = reply.get("content") if isinstance(reply.get("content"), list) else []
    text = "".join(block["text"] for block in blocks
                   if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str))
    if not text:
        raise BadReply("the provider's reply holds no text")
    usage = reply.get("usage") if isinstance(reply.get("usage"), dict) else {}
    count = lambda name: usage[name] if type(usage.get(name)) is int and usage[name] >= 0 else None
    return Result(text=text, model_id=str(model_id), input_tokens=count("input_tokens"),
                  output_tokens=count("output_tokens"), latency_s=latency_s)
