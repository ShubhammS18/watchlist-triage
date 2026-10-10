"""A scripted stand-in for a model. No network, no randomness, no clock: the same script gives the same replies.

It never looks at the request to decide anything about an alert. It only plays back what it was given.
"""
from . import BadReply, ModelTimeout, ProviderError, Request, Result

MODEL_ID = "stub-1"
FAILURES = {"timeout": ModelTimeout, "empty": BadReply, "provider_error": ProviderError}


class Stub:
    """Plays `replies` in order, one per call, then `default` for every call after that.

    A step is either the reply text or {"fail": name}, where name is "timeout", "empty" or "provider_error".
    A failing step raises the matching error at once instead of returning.
    """

    def __init__(self, default="stub reply", replies=()):
        self._default = default
        self._replies = list(replies)
        for step in [default, *self._replies]:
            if not isinstance(step, str) and not (
                    isinstance(step, dict) and set(step) == {"fail"} and step["fail"] in FAILURES):
                raise ValueError(f"a stub step is reply text or {{\"fail\": one of {sorted(FAILURES)}}}, not {step!r}")

    def __call__(self, request):
        if not isinstance(request, Request):
            raise TypeError("the stub takes a Request")
        step = self._replies.pop(0) if self._replies else self._default
        if isinstance(step, dict):
            raise FAILURES[step["fail"]](f"stub scripted failure: {step['fail']}")
        return Result(text=step, model_id=MODEL_ID, input_tokens=None, output_tokens=None, latency_s=0.0)
