"""T04: one model interface, a scripted stub, and a model chosen only by configuration (FR-16, stub part of AC-14)."""
import dataclasses
import json
from dataclasses import asdict

import pytest

from model_interface import (ERRORS, BadReply, Message, ModelError, ModelTimeout, ProviderError, Request, Result,
                             Settings, providers, request_from)
from model_interface.providers import DEFAULT_CONFIG, PROVIDERS, ConfigError, load
from model_interface.runner import ChildError, run_child
from model_interface.stub import Stub

SETTINGS = Settings(model="stub-1", temperature=0, max_tokens=64, timeout_s=5)
MESSAGES = [{"role": "user", "content": "ping"}]
REQUEST = Request(MESSAGES, SETTINGS)
FAILURES = {"timeout": ModelTimeout, "empty": BadReply, "provider_error": ProviderError}
GOOD = {"provider": "stub", "model": "stub-1", "temperature": 0, "max_tokens": 64, "timeout_s": 5}


class Counting:
    """Wraps a model and counts how often it is called."""

    def __init__(self, model):
        self.model, self.calls = model, 0

    def __call__(self, request):
        self.calls += 1
        return self.model(request)


def names(cls):
    return [field.name for field in dataclasses.fields(cls)]


def write(tmp_path, config, name="config.json"):
    path = tmp_path.joinpath(name)
    path.write_text(config if isinstance(config, str) else json.dumps(config), encoding="utf-8")
    return path


def ask(config_path):
    """The one piece of calling code that every configuration test goes through. It never names a provider."""
    model, settings = load(config_path)
    return model(Request(MESSAGES, settings))


# ---- the interface

def test_request_settings_and_result_carry_exactly_the_agreed_fields():
    assert names(Request) == ["messages", "settings"]
    assert names(Settings) == ["model", "temperature", "max_tokens", "timeout_s"]
    assert names(Result) == ["text", "model_id", "input_tokens", "output_tokens", "latency_s"]


def test_the_stub_returns_its_default_reply_with_every_result_field():
    result = Stub()(REQUEST)
    assert result == Result(text="stub reply", model_id="stub-1", input_tokens=None, output_tokens=None, latency_s=0.0)
    assert isinstance(result.text, str) and isinstance(result.model_id, str) and isinstance(result.latency_s, float)


def test_the_stub_plays_its_sequence_in_order_and_then_its_default():
    stub = Stub(default="after", replies=["one", "two"])
    assert [stub(REQUEST).text for _ in range(5)] == ["one", "two", "after", "after", "after"]


def test_the_stub_is_deterministic():
    def play():
        stub = Stub(default="d", replies=["a", "b"])
        return [stub(REQUEST) for _ in range(4)]

    assert play() == play()


@pytest.mark.parametrize("mode", FAILURES)
def test_each_failure_mode_raises_its_own_named_error(mode):
    with pytest.raises(ModelError) as caught:
        Stub(replies=[{"fail": mode}])(REQUEST)
    assert type(caught.value) is FAILURES[mode]
    assert ERRORS[FAILURES[mode].__name__] is FAILURES[mode]


@pytest.mark.parametrize("mode", FAILURES)
def test_a_failure_can_be_the_default_and_then_every_call_fails(mode):
    stub = Stub(default={"fail": mode})
    for _ in range(3):
        with pytest.raises(FAILURES[mode]):
            stub(REQUEST)


@pytest.mark.parametrize("mode", FAILURES)
def test_the_stub_does_not_retry_a_failed_call(mode):
    stub = Stub(replies=[{"fail": mode}, "second"])
    with pytest.raises(FAILURES[mode]):
        stub(REQUEST)
    assert stub(REQUEST).text == "second"


@pytest.mark.parametrize("step", (None, 3, {"fail": "explode"}, {"fail": "timeout", "extra": 1}, ["text"]))
def test_the_stub_refuses_a_step_it_does_not_know(step):
    with pytest.raises(ValueError):
        Stub(replies=[step])


def test_a_request_has_no_room_for_tools():
    with pytest.raises(ValueError):
        Request([{"role": "user", "content": "x", "tools": []}], SETTINGS)
    with pytest.raises(ValueError):
        Request([{"role": "user", "content": {"type": "tool_use"}}], SETTINGS)
    with pytest.raises(ValueError):
        Request([], SETTINGS)
    with pytest.raises(TypeError):
        Settings(model="m", temperature=0, max_tokens=1, timeout_s=1, tools=[])
    with pytest.raises(TypeError):
        Request(MESSAGES, SETTINGS, tools=[])


# ---- the interface across the pipe: one call in, one call out, no retry

def test_a_result_crosses_the_pipe_unchanged_after_exactly_one_call():
    expected = Result(text="answer", model_id="other-9", input_tokens=3, output_tokens=5, latency_s=0.25)
    model = Counting(lambda request: expected)
    report = run_child("model_interface.probe_child", {"request": asdict(REQUEST)}, model)
    assert report == {"result": asdict(expected)}
    assert model.calls == 1


def test_the_parent_model_receives_the_request_the_child_sent():
    seen = []
    run_child("model_interface.probe_child", {"request": asdict(REQUEST)}, lambda request: seen.append(request) or Stub()(request))
    assert seen == [REQUEST]


@pytest.mark.parametrize("mode", FAILURES)
def test_a_failure_crosses_the_pipe_as_the_same_named_error_after_exactly_one_call(mode):
    model = Counting(Stub(replies=[{"fail": mode}, "second"]))
    report = run_child("model_interface.probe_child", {"request": asdict(REQUEST)}, model)
    assert report == {"model_error": FAILURES[mode].__name__}
    assert model.calls == 1


# ---- a request resists normal assignment and later edits to the caller's lists (a deliberate __dict__ write in
# ---- the same process can still change it, which is out of scope), and the pipe accepts exactly one shape

def test_a_request_keeps_its_own_copy_of_the_messages():
    messages = [{"role": "user", "content": "ping"}]
    request = Request(messages, SETTINGS)
    messages[0]["tools"] = []
    messages[0]["content"] = "changed"
    messages.append({"role": "user", "content": "more"})
    assert request.messages == (Message("user", "ping"),)
    assert asdict(request)["messages"] == ({"role": "user", "content": "ping"},)
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.messages[0].content = "changed"
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.messages = ()


def test_a_request_survives_the_trip_to_json_and_back():
    assert request_from(json.loads(json.dumps(asdict(REQUEST)))) == REQUEST


def forged(**changes):
    return {**json.loads(json.dumps(asdict(REQUEST))), **changes}


def forged_settings(**changes):
    settings = {**asdict(SETTINGS), **changes}
    return forged(settings={key: value for key, value in settings.items() if value != "<absent>"})


FORGED_SETTINGS = {
    "unknown field": forged_settings(tools=[]),
    "missing field": forged_settings(timeout_s="<absent>"),
    "max_tokens is text": forged_settings(max_tokens="many"),
    "temperature is a list": forged_settings(temperature=[0]),
    "model is a number": forged_settings(model=7),
    "settings is a list": forged(settings=["stub-1", 0, 64, 5]),
    "settings is null": forged(settings=None),
}
FORGED_REQUESTS = {
    "a tools key": forged(tools=[]),
    "a tool_choice key": forged(tool_choice="auto"),
    "a tools key inside a message": forged(messages=[{"role": "user", "content": "ping", "tools": []}]),
    "messages is text": forged(messages="ping"),
    "a message is text": forged(messages=["ping"]),
    "no messages key": {"settings": asdict(SETTINGS)},
    "not an object": [asdict(SETTINGS)],
}


def refused_at_the_pipe(call):
    """Send `call` up the pipe from the agent process. Returns the parent's error and how often the model ran."""
    model = Counting(Stub())
    with pytest.raises(ChildError) as caught:
        run_child("tests.t04_model_interface.t04_probes", {"forged_call": call}, model)
    return str(caught.value), model.calls


def test_a_forged_call_with_a_tools_key_is_refused_and_never_reaches_the_model():
    with pytest.raises(ValueError):
        request_from(forged(tools=[]))
    message, calls = refused_at_the_pipe(forged(tools=[]))
    assert "wrong shape" in message and "exactly the keys messages and settings" in message
    assert calls == 0


@pytest.mark.parametrize("case", [name for name in FORGED_REQUESTS if name != "not an object"])
def test_a_forged_call_of_the_wrong_shape_is_refused_at_the_pipe(case):
    message, calls = refused_at_the_pipe(FORGED_REQUESTS[case])
    assert "wrong shape" in message and calls == 0


@pytest.mark.parametrize("case", FORGED_REQUESTS)
def test_a_request_of_the_wrong_shape_is_a_value_error(case):
    with pytest.raises(ValueError):
        request_from(FORGED_REQUESTS[case])


@pytest.mark.parametrize("case", FORGED_SETTINGS)
def test_forged_settings_are_a_value_error_and_not_a_raw_type_error(case):
    with pytest.raises(ValueError):
        request_from(FORGED_SETTINGS[case])


@pytest.mark.parametrize("case", FORGED_SETTINGS)
def test_forged_settings_are_refused_at_the_pipe_and_never_reach_the_model(case):
    message, calls = refused_at_the_pipe(FORGED_SETTINGS[case])
    assert "wrong shape" in message and "TypeError" not in message
    assert calls == 0


# ---- the model is chosen by configuration only (AC-14)

def test_the_default_configuration_selects_the_stub_and_holds_no_secret():
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    assert config["provider"] == "stub"
    assert set(config) <= set(providers.REQUIRED) | set(providers.OPTIONAL)
    model, settings = load()
    assert isinstance(model, Stub) and isinstance(settings, Settings)
    assert ask(DEFAULT_CONFIG).text == "stub reply"


def test_two_configuration_files_drive_the_same_code_to_different_replies(tmp_path):
    first = write(tmp_path, {**GOOD, "options": {"default": "reply from A"}}, "a.json")
    second = write(tmp_path, {**GOOD, "model": "stub-b", "temperature": 0.5, "max_tokens": 9, "timeout_s": 2.5,
                              "options": {"replies": ["reply from B"]}}, "b.json")
    assert ask(first).text == "reply from A"
    assert ask(second).text == "reply from B"
    assert load(first)[1] == Settings("stub-1", 0, 64, 5)
    assert load(second)[1] == Settings("stub-b", 0.5, 9, 2.5)


def test_two_configuration_files_drive_the_same_child_process_to_different_replies(tmp_path):
    replies = []
    for name, text in (("a.json", "child reply A"), ("b.json", "child reply B")):
        model, settings = load(write(tmp_path, {**GOOD, "options": {"default": text}}, name))
        report = run_child("model_interface.probe_child", {"request": asdict(Request(MESSAGES, settings))}, model)
        replies.append(report["result"]["text"])
    assert replies == ["child reply A", "child reply B"]


def test_a_configured_failure_reaches_the_same_calling_code(tmp_path):
    with pytest.raises(ProviderError):
        ask(write(tmp_path, {**GOOD, "options": {"default": {"fail": "provider_error"}}}))


def test_a_new_provider_is_one_registry_entry_and_no_change_to_the_calling_code(tmp_path, monkeypatch):
    def other(prefix="other"):
        return lambda request: Result(f"{prefix}: {request.settings.model}", "other-1", 1, 2, 0.0)

    monkeypatch.setitem(PROVIDERS, "other", other)
    path = write(tmp_path, {**GOOD, "provider": "other", "model": "m-7", "options": {"prefix": "hello"}})
    assert ask(path) == Result("hello: m-7", "other-1", 1, 2, 0.0)


def test_only_the_stub_is_registered():
    assert PROVIDERS == {"stub": Stub}


def test_an_unknown_provider_fails_clearly(tmp_path):
    with pytest.raises(ConfigError) as caught:
        load(write(tmp_path, {**GOOD, "provider": "nonesuch"}))
    assert "unknown provider 'nonesuch'" in str(caught.value) and "stub" in str(caught.value)


INVALID = {
    "not JSON": "{provider: stub",
    "not an object": ["stub"],
    "missing key": {key: value for key, value in GOOD.items() if key != "timeout_s"},
    "unknown key": {**GOOD, "api_key": "x"},
    "provider is not text": {**GOOD, "provider": ["stub"]},
    "empty model": {**GOOD, "model": ""},
    "temperature is text": {**GOOD, "temperature": "hot"},
    "temperature below zero": {**GOOD, "temperature": -1},
    "max_tokens is zero": {**GOOD, "max_tokens": 0},
    "max_tokens is a fraction": {**GOOD, "max_tokens": 1.5},
    "max_tokens is true": {**GOOD, "max_tokens": True},
    "timeout is zero": {**GOOD, "timeout_s": 0},
    "options is a list": {**GOOD, "options": ["default"]},
    "unknown stub option": {**GOOD, "options": {"temperature": 1}},
    "unknown stub step": {**GOOD, "options": {"replies": [{"fail": "explode"}]}},
}


@pytest.mark.parametrize("case", INVALID)
def test_an_invalid_configuration_fails_clearly(tmp_path, case):
    with pytest.raises(ConfigError):
        load(write(tmp_path, INVALID[case]))


def test_a_missing_configuration_file_fails_clearly(tmp_path):
    with pytest.raises(ConfigError) as caught:
        load(tmp_path.joinpath("absent.json"))
    assert "absent.json" in str(caught.value)
