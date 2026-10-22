"""T07: the Anthropic adapter (DEC-T07-ADAPTER), against a fake HTTP server on this machine. No internet, no key."""
import json
import logging
import socket
import threading
import time
import traceback

import pytest

from model_interface import BadReply, ModelRefusal, ModelTimeout, ProviderError, Request, Settings, providers
from model_interface.anthropic_api import KEY_VARIABLE, VERSION, Anthropic

from fake_api import CANARY, OK, answer, other_server, server  # noqa: F401  (fixtures)

SETTINGS = Settings(model="claude-haiku-5-5", temperature=1, max_tokens=512, timeout_s=5)
MESSAGES = [{"role": "system", "content": "be brief"}, {"role": "user", "content": "ping"}]


def model_for(fake):
    return Anthropic(thinking="disabled", base_url=fake.url)


def call(fake, settings=SETTINGS, messages=MESSAGES):
    return model_for(fake)(Request(messages, settings))


# ---- what a good reply becomes

def test_a_reply_becomes_the_text_of_its_text_blocks_with_model_id_and_token_counts(server):
    result = call(server)
    assert (result.text, result.model_id, result.input_tokens, result.output_tokens) == ("pong", "claude-haiku-5-5", 12, 3)
    assert result.latency_s > 0


@pytest.mark.parametrize("reported, kept", [("claude-haiku-5-5", "claude-haiku-5-5"), (20261019, "20261019")])
def test_the_model_id_is_kept_as_text(server, reported, kept):
    server.script = lambda h, b: answer(h, 200, {**OK, "model": reported})
    assert call(server).model_id == kept and isinstance(call(server).model_id, str)


@pytest.mark.parametrize("usage, counts", [(None, (None, None)), ({}, (None, None)), ({"input_tokens": 7}, (7, None)),
                                           ({"input_tokens": "7", "output_tokens": True}, (None, None)),
                                           ({"input_tokens": 0, "output_tokens": 0}, (0, 0))])
def test_a_missing_or_unusable_token_count_is_none_never_zero(server, usage, counts):
    reply = {key: value for key, value in OK.items() if key != "usage"}
    server.script = lambda h, b: answer(h, 200, reply if usage is None else {**reply, "usage": usage})
    result = call(server)
    assert (result.input_tokens, result.output_tokens) == counts


@pytest.mark.parametrize("reply", [b"not json", {**OK, "content": []}, {**OK, "content": [OK["content"][0]]},
                                   {key: value for key, value in OK.items() if key != "model"}])
def test_a_reply_with_no_text_or_no_model_is_a_bad_reply(server, reply):
    server.script = lambda h, b: answer(h, 200, reply)
    with pytest.raises(BadReply):
        call(server)


def test_a_refusal_raises_the_refusal_error(server):
    refusal = {**OK, "content": [], "stop_reason": "refusal",
               "stop_details": {"type": "refusal", "category": "reasoning_extraction", "explanation": "declined"}}
    server.script = lambda h, b: answer(h, 200, refusal)
    with pytest.raises(ModelRefusal, match="reasoning_extraction"):
        call(server)
    assert len(server.requests) == 1


# ---- what the request holds

@pytest.mark.parametrize("temperature", [1, 0.7, 0])
def test_the_request_body_and_headers(server, temperature):
    call(server, Settings(model="claude-haiku-5-5", temperature=temperature, max_tokens=512, timeout_s=5))
    sent, = server.requests
    assert (sent["method"], sent["path"]) == ("POST", "/v1/messages")
    assert sent["body"] == {"model": "claude-haiku-5-5", "max_tokens": 512, "temperature": temperature,
                            "thinking": {"type": "disabled"}, "system": "be brief",
                            "messages": [{"role": "user", "content": "ping"}]}
    assert type(sent["body"]["temperature"]) is type(temperature)  # sent exactly as given, never changed
    assert "top_p" not in sent["body"] and "top_k" not in sent["body"]
    headers = {name.lower(): value for name, value in sent["headers"].items()}
    assert headers["x-api-key"] == CANARY and headers["anthropic-version"] == VERSION == "2023-06-01"
    assert headers["content-type"] == "application/json"


def test_messages_without_an_opening_system_message_are_sent_as_they_are(server):
    call(server, messages=[{"role": "user", "content": "ping"}])
    assert "system" not in server.requests[0]["body"]
    assert server.requests[0]["body"]["messages"] == [{"role": "user", "content": "ping"}]


# ---- one deadline for the whole call

def trickle(handler, head, body, gap):
    """Send `head` and then `body` one byte at a time, `gap` seconds apart."""
    try:
        handler.wfile.write(head)
        handler.wfile.flush()
        for byte in body:
            time.sleep(gap)
            handler.wfile.write(bytes([byte]))
            handler.wfile.flush()
    except OSError:  # the adapter gave up and closed the connection
        pass


@pytest.mark.parametrize("where", ["body", "headers"])
def test_a_reply_that_trickles_in_ends_at_the_overall_deadline(server, where):
    data = json.dumps(OK).encode()
    head = b"HTTP/1.1 200 OK\r\ncontent-type: application/json\r\ncontent-length: %d\r\n\r\n" % len(data)
    if where == "body":
        server.script = lambda h, b: trickle(h, head, data, 0.02)
    else:
        server.script = lambda h, b: trickle(h, b"", head + data, 0.02)
    settings = Settings(model="claude-haiku-5-5", temperature=1, max_tokens=512, timeout_s=0.5)
    begun = time.monotonic()
    with pytest.raises(ModelTimeout):
        call(server, settings)
    # each byte arrives well inside a per-read timeout, so only an overall deadline stops it
    assert 0.5 <= time.monotonic() - begun < 1.0


def test_a_closed_port_is_a_provider_error(monkeypatch):
    monkeypatch.setenv(KEY_VARIABLE, CANARY)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(ProviderError, match="connection"):
        Anthropic(thinking="disabled", base_url=f"http://127.0.0.1:{port}")(Request(MESSAGES, SETTINGS))


# ---- every error status, one request each, no retry

STATUSES = [
    (400, {"error": {"type": "invalid_request_error", "message": "You have reached your specified API usage limits."}},
     "spend limit reached: HTTP 400 invalid_request_error"),
    (400, {"error": {"type": "invalid_request_error", "message": "messages: field required"}},
     "request refused by the provider: HTTP 400 invalid_request_error"),
    (401, {"error": {"type": "authentication_error", "message": "invalid x-api-key"}},
     "request refused by the provider: HTTP 401 authentication_error"),
    (402, {"error": {"type": "billing_error", "message": "billing"}}, "spend limit reached: HTTP 402 billing_error"),
    (403, {"error": {"type": "permission_error", "message": "no"}},
     "request refused by the provider: HTTP 403 permission_error"),
    (404, {"error": {"type": "not_found_error", "message": "no"}},
     "request refused by the provider: HTTP 404 not_found_error"),
    (409, {"error": {"type": "conflict_error", "message": "no"}},
     "request refused by the provider: HTTP 409 conflict_error"),
    (413, {"error": {"type": "request_too_large", "message": "no"}},
     "request refused by the provider: HTTP 413 request_too_large"),
    (429, {"error": {"type": "rate_limit_error", "message": "slow down"}}, "rate limit reached: HTTP 429 rate_limit_error"),
    (429, {"error": {"type": "rate_limit_error", "message": "cap", "details": {"error_code": "enforced_spend_limit_reached"}}},
     "spend cap reached: HTTP 429 rate_limit_error"),
    (500, {"error": {"type": "api_error", "message": "oops"}}, "provider server error: HTTP 500 api_error"),
    (503, b"<html>down</html>", "provider server error: HTTP 503 unknown"),
    (504, {"error": {"type": "timeout_error", "message": "slow"}}, "provider server error: HTTP 504 timeout_error"),
    (529, {"error": {"type": "overloaded_error", "message": "busy"}}, "provider overloaded: HTTP 529 overloaded_error"),
]


@pytest.mark.parametrize("status, reply, text", STATUSES)
def test_each_error_status_is_one_request_and_one_provider_error(server, status, reply, text):
    server.script = lambda h, b: answer(h, status, reply, headers=(("retry-after", "30"),))
    begun = time.monotonic()
    with pytest.raises(ProviderError) as caught:
        call(server)
    assert str(caught.value) == text
    assert len(server.requests) == 1 and time.monotonic() - begun < 1  # no retry and no wait on retry-after


# ---- the key

def every_failure(server):
    """Yield each exception the adapter can raise, with the server set up to cause it."""
    for status, reply, _ in STATUSES:
        server.script = lambda h, b, status=status, reply=reply: answer(h, status, reply)
        yield pytest.raises(ProviderError)
    for reply in (b"not json", {**OK, "content": []}, {**OK, "content": [], "stop_reason": "refusal"}):
        server.script = lambda h, b, reply=reply: answer(h, 200, reply)
        yield pytest.raises((BadReply, ModelRefusal))


def test_the_canary_key_appears_in_no_error_text_traceback_repr_or_log(server, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    model = model_for(server)
    seen = [repr(model), str(model)]
    for expectation in every_failure(server):
        with expectation as caught:
            model(Request(MESSAGES, SETTINGS))
        seen += [str(caught.value), repr(caught.value), "".join(traceback.format_exception(caught.value))]
    slow = Settings(model="claude-haiku-5-5", temperature=1, max_tokens=512, timeout_s=0.2)
    server.script = lambda h, b: time.sleep(0.5)
    with pytest.raises(ModelTimeout) as caught:
        model(Request(MESSAGES, slow))
    seen += [str(caught.value), "".join(traceback.format_exception(caught.value))]
    out, err = capsys.readouterr()
    seen += [out, err, caplog.text]
    assert all(CANARY not in text for text in seen) and len(seen) > 40
    assert all(request["headers"]["x-api-key"] == CANARY for request in server.requests)  # it was really sent


@pytest.mark.parametrize("value", ["", "   ", CANARY + " ", "sk-ant-\nCANARY", "sk-ant-ünicode"])
def test_a_missing_or_malformed_key_stops_the_model_being_made_without_naming_it(monkeypatch, value):
    monkeypatch.setenv(KEY_VARIABLE, value)
    with pytest.raises(ValueError) as caught:
        Anthropic(thinking="disabled")
    assert KEY_VARIABLE in str(caught.value) and (not value.strip() or value.strip() not in str(caught.value))


def test_the_key_is_read_from_the_environment_only(server, tmp_path):
    config = tmp_path.joinpath("config.json")
    config.write_text(json.dumps({"provider": "anthropic", "model": "claude-haiku-5-5", "temperature": 1,
                                  "max_tokens": 512, "timeout_s": 5,
                                  "options": {"thinking": "disabled", "base_url": server.url, "key": "x"}}))
    with pytest.raises(providers.ConfigError):  # there is no option for a key
        providers.load(config)


# ---- configuration

def write(tmp_path, options):
    path = tmp_path.joinpath("config.json")
    path.write_text(json.dumps({"provider": "anthropic", "model": "claude-haiku-5-5", "temperature": 1,
                                "max_tokens": 512, "timeout_s": 5, "options": options}))
    return path


def test_the_adapter_is_chosen_by_configuration_alone(server, tmp_path):
    model, settings = providers.load(write(tmp_path, {"thinking": "disabled", "base_url": server.url}))
    assert model(Request(MESSAGES, settings)).text == "pong"


@pytest.mark.parametrize("options", [{}, {"thinking": "adaptive"}, {"thinking": "disabled", "base_url": "https://example.com"},
                                     {"thinking": "disabled", "base_url": "http://api.anthropic.com"},
                                     {"thinking": "disabled", "base_url": "http://127.0.0.1:9/v1"}])
def test_a_wrong_option_stops_start_up(monkeypatch, tmp_path, options):
    monkeypatch.setenv(KEY_VARIABLE, CANARY)
    with pytest.raises(providers.ConfigError) as caught:
        providers.load(write(tmp_path, options))
    assert CANARY not in str(caught.value)


def test_the_default_url_is_the_anthropic_api(monkeypatch):
    monkeypatch.setenv(KEY_VARIABLE, CANARY)
    assert "https://api.anthropic.com" in repr(Anthropic(thinking="disabled"))


# ---- threads

def test_calls_from_several_threads_each_get_their_own_answer(server):
    def echo(handler, body):
        answer(handler, 200, {**OK, "content": [{"type": "text", "text": body["messages"][-1]["content"]}],
                              "usage": {"input_tokens": len(body["messages"][-1]["content"]), "output_tokens": 1}})
    server.script = echo
    model, results, errors = model_for(server), {}, []

    def worker(number):
        try:
            for index in range(5):
                prompt = f"thread {number} call {index}"
                result = model(Request([{"role": "user", "content": prompt}], SETTINGS))
                results[prompt] = (result.text, result.input_tokens)
        except Exception as error:  # noqa: BLE001 - reported below
            errors.append(error)

    threads = [threading.Thread(target=worker, args=(number,)) for number in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not errors and len(results) == 40 and len(server.requests) == 40
    assert all(text == prompt and tokens == len(prompt) for prompt, (text, tokens) in results.items())


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_a_redirect_is_a_provider_error_and_is_never_followed(server, other_server, status):
    # review round 1, T07-01: the key is sent to one host only; http.client follows no redirect
    target = other_server.url + "/v1/messages"
    server.script = lambda h, b: answer(h, status, {}, headers=(("location", target),))
    with pytest.raises(ProviderError, match=f"HTTP {status}") as caught:
        call(server)
    assert len(server.requests) == 1 and other_server.requests == [] and CANARY not in str(caught.value)
