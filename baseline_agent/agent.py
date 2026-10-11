"""The agent itself: one alert in, one recommendation out (FR-6, FR-8, DEC-T05-FAILCLOSED, DEC-T05-RETRIES).

This module runs inside the agent process: `model_interface.runner.run_child` calls `main(model, job)`. It asks
the model once per attempt and never returns a CLOSE that it could not check. Python standard library only.

Every result has the same shape, whether it is a recommendation or a failure:
    recommendation    "CLOSE" or "ESCALATE"
    reason            the model's reason, or "System failure: <kind>"
    cited_ids         the evidence ids cited; empty on a failure
    system_failure    true when a fault produced this result; the recommendation is then always ESCALATE
    failure_kind      the name of the fault, or null
    citation_invalid  true when an ESCALATE cites an id that is not in the bundle
    log               {kind, error_name, attempts, attempt_log, latency_s, model_id}; it holds no evidence values

`attempt_log` has one {error_name, latency_s} per model call, in order; `error_name` is null for a call that
returned a reply. The parent adds `correlation_id` to the log; this module never sees it.
"""
import time

from model_interface import ModelError, Request, Settings

from .payload import SCHEMA_VERSION
from .prompt import build_messages
from .reply import ReplyFault, parse_reply


# Model errors by name, as they cross the pipe. A ModelError with any other name is "model_error".
KIND_OF = {"ModelTimeout": "timeout", "ProviderError": "provider_error", "BadReply": "malformed_output",
           "ModelRefusal": "model_refusal"}
RETRIED = ("ModelTimeout", "ProviderError")


def failure(kind, error_name=None, attempts=None, latency_s=0.0, model_id=None, attempt_log=()):
    """The result for any fault. `attempts` is None when the number of model calls is not known."""
    return {"recommendation": "ESCALATE", "reason": f"System failure: {kind}", "cited_ids": [],
            "system_failure": True, "failure_kind": kind, "citation_invalid": False,
            "log": {"kind": kind, "error_name": error_name, "attempts": attempts, "attempt_log": list(attempt_log),
                    "latency_s": latency_s, "model_id": model_id}}


def main(model, job):
    """`job` is {"payload": what build_payload returns, "settings": the four Settings fields, "retries": n}.

    A timeout or a provider error is tried again, up to `retries` more times, with no wait in between. A reply
    that cannot be used, a refusal and any other model error are not tried again.
    """
    payload = job["payload"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        return failure("unknown_schema_version", attempts=0)
    if payload.get("item_count") != len(payload["items"]):
        return failure("truncated_evidence", attempts=0)
    request = Request(build_messages(payload), Settings(**job["settings"]))
    item_ids = {item["id"] for item in payload["items"]}
    model_id, attempt_log = None, []
    begun = time.monotonic()
    for attempt in range(1, job["retries"] + 2):
        started = time.monotonic()
        fields = error_name = None
        try:
            reply = model(request)
            model_id = reply.model_id
            fields = parse_reply(reply.text, item_ids)
            kind = "ok"
        except ModelError as error:
            error_name = type(error).__name__
            kind = KIND_OF.get(error_name, "model_error")
        except ReplyFault as fault:
            kind = fault.kind
        attempt_log.append({"error_name": error_name, "latency_s": time.monotonic() - started})
        if error_name not in RETRIED:
            break
    if fields is None:
        return failure(kind, error_name, attempt, time.monotonic() - begun, model_id, attempt_log)
    return {**fields, "system_failure": False, "failure_kind": None,
            "log": {"kind": "ok", "error_name": None, "attempts": attempt, "attempt_log": attempt_log,
                    "latency_s": time.monotonic() - begun, "model_id": model_id}}
