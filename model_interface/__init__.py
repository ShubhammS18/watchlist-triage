"""The one way to reach a model, for task T04 (FR-9, FR-16). Python standard library only.

A model is any callable that takes a `Request` and returns a `Result`, or raises a `ModelError`. It is called
once and never retried here: retry limits and timeout handling belong to the caller. A request carries messages
and settings and nothing else, so it has no field for tools or function-calling. A request resists normal
assignment and later edits to the caller's lists. A deliberate `__dict__` write in the same process can still
change it; that is out of scope.
"""
import json
from dataclasses import dataclass


class ModelError(Exception):
    """Any failure of a model call."""


class ModelTimeout(ModelError):
    """The model did not answer within `timeout_s`."""


class BadReply(ModelError):
    """The model answered, but the reply is empty or cannot be read."""


class ProviderError(ModelError):
    """The provider refused or failed the call."""


ERRORS = {error.__name__: error for error in (ModelError, ModelTimeout, BadReply, ProviderError)}


@dataclass(frozen=True)
class Settings:
    """Which model to ask and how it should decode."""
    model: str
    temperature: float
    max_tokens: int
    timeout_s: float

    def __post_init__(self):
        number = (int, float)
        if not isinstance(self.model, str) or not self.model:
            raise ValueError("model must be a non-empty string")
        if isinstance(self.temperature, bool) or not isinstance(self.temperature, number) or self.temperature < 0:
            raise ValueError("temperature must be a number of 0 or more")
        if isinstance(self.max_tokens, bool) or not isinstance(self.max_tokens, int) or self.max_tokens < 1:
            raise ValueError("max_tokens must be a whole number of 1 or more")
        if isinstance(self.timeout_s, bool) or not isinstance(self.timeout_s, number) or self.timeout_s <= 0:
            raise ValueError("timeout_s must be a number above 0")


@dataclass(frozen=True)
class Message:
    """One message. Its JSON form is exactly {"role": text, "content": text}."""
    role: str
    content: str

    def __post_init__(self):
        if not isinstance(self.role, str) or not isinstance(self.content, str):
            raise ValueError("role and content must be text")


@dataclass(frozen=True)
class Request:
    """Messages plus the settings for this call.

    Each message is given as {"role": text, "content": text} or as a Message. They are copied into a tuple of
    Message, so later edits to the caller's list or dictionaries do not change the request, and normal
    assignment to it is refused. A deliberate `__dict__` write in the same process can still change it.
    """
    messages: tuple
    settings: Settings

    def __post_init__(self):
        if not isinstance(self.messages, (list, tuple)) or not self.messages:
            raise ValueError("messages must be a non-empty list")
        copied = []
        for message in self.messages:
            if isinstance(message, dict):
                if set(message) != {"role", "content"}:
                    raise ValueError("every message must have exactly the keys role and content")
                message = Message(**message)
            if not isinstance(message, Message):
                raise ValueError("every message must be a Message or a dictionary with the keys role and content")
            copied.append(message)
        if not isinstance(self.settings, Settings):
            raise ValueError("settings must be a Settings")
        object.__setattr__(self, "messages", tuple(copied))


@dataclass(frozen=True)
class Result:
    """What came back. `model_id` is what the provider reported. A token count is None when it is unknown."""
    text: str
    model_id: str
    input_tokens: int | None
    output_tokens: int | None
    latency_s: float


def request_from(data):
    """Rebuild a Request from its JSON form. Anything of the wrong shape raises ValueError or TypeError.

    The form is exactly {"messages": [...], "settings": {...}}. Any other key, at any level, is refused.
    """
    if not isinstance(data, dict) or set(data) != {"messages", "settings"}:
        raise ValueError("a request must have exactly the keys messages and settings")
    if not isinstance(data["messages"], list) or not all(isinstance(message, dict) for message in data["messages"]):
        raise ValueError("messages must be a list of objects")
    if not isinstance(data["settings"], dict):
        raise ValueError("settings must be an object")
    if set(data["settings"]) != set(Settings.__dataclass_fields__):
        raise ValueError(f"settings must have exactly the keys {sorted(Settings.__dataclass_fields__)}")
    return Request(data["messages"], Settings(**data["settings"]))


def send(stream, message):
    """Write one JSON message as one line."""
    stream.write(json.dumps(message) + "\n")
    stream.flush()


def receive(stream):
    """Read one JSON message, or None when the other side has closed the pipe."""
    line = stream.readline()
    return json.loads(line) if line else None
