"""Parent side of the baseline agent: one alert's evidence items in, one result out, and never an exception
for a fault of the model or the agent process (FR-8, DEC-T05-FAILCLOSED).

The agent runs in the guarded child process. Whatever goes wrong there, or on the way there, comes back as
ESCALATE with the SYSTEM_FAILURE flag, in the same shape as any other result (see baseline_agent.agent).
"""
import copy
import time
from dataclasses import asdict

from model_interface.runner import ChildError, ChildTimeout, run_child

from .agent import KIND_OF, RETRIED, failure
from .payload import build_payload

MODULE = "baseline_agent.agent"
MARGIN_S = 10  # added to the time the model calls may take, for starting the child and reading the reply
RESULT_KEYS = {"recommendation", "reason", "cited_ids", "system_failure", "failure_kind", "citation_invalid", "log"}
CHILD_LOG_KEYS = {"kind", "error_name", "attempts", "attempt_log", "latency_s", "model_id"}  # correlation_id is added here
KINDS = ("malformed_output", "missing_citations", "model_refusal", "timeout", "provider_error", "truncated_evidence",
         "unknown_schema_version", "invalid_citation", "model_error", "child_timeout", "child_crash", "internal_error")


def _name(value):
    return value is None or isinstance(value, str)


def _seconds(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value < float("inf")


# How a log record must agree with the result it belongs to (DEC-T05-LOG-INVARIANTS). `KIND_OF` and `RETRIED`
# are the child's own tables, read from baseline_agent.agent, so the two sides cannot drift apart on them.
PAYLOAD_KINDS = ("unknown_schema_version", "truncated_evidence")  # the payload was refused: no model call
REPLY_KINDS = ("malformed_output", "missing_citations", "invalid_citation", "unknown_schema_version")  # the last call
#                                                                         returned a reply that could not be used
PARENT_KINDS = {"child_timeout": ("ChildTimeout",), "child_crash": ("ChildError", "BadResult"), "internal_error": None}


def _count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_log(log, kind, max_attempts):
    """Whether `log` is a record the child can have written for a result of this `kind` ("ok" for a success).

    The rules, in the order they are checked:
    1. Exactly the six keys; `kind` is the result's kind; names are text or null; times are finite and 0 or more;
       every attempt entry is {error_name, latency_s}; and no attempt took longer than the record's total time.
    2. A kind that only the parent produces has unknown attempts, no entries, no model id and its own error name.
    3. `attempts` is a whole number, equal to the number of entries, and at most 1 + retries.
    4. No attempts at all is only possible when the payload was refused; there is then no error, no model id
       and a total time of 0.
    5. Otherwise the last entry's error is the record's `error_name`; every earlier entry is an error that is
       retried; and a record that ends on a retried error used every attempt it was allowed.
    6. A record with no error means the last call returned a reply: the kind is "ok" or a fault of the reply,
       and the model id is text. So a success has at least one attempt, no error name, and no error at the end.
    7. A record with an error has exactly the kind that error maps to, and no model id.
    """
    if not isinstance(log, dict) or set(log) != CHILD_LOG_KEYS:
        return False
    error, attempts, entries, model_id = log["error_name"], log["attempts"], log["attempt_log"], log["model_id"]
    if not (log["kind"] == kind and _name(error) and _name(model_id) and _seconds(log["latency_s"])
            and isinstance(entries, list)
            and all(isinstance(entry, dict) and set(entry) == {"error_name", "latency_s"}
                    and _name(entry["error_name"]) and _seconds(entry["latency_s"]) for entry in entries)):
        return False
    if any(entry["latency_s"] > log["latency_s"] for entry in entries):
        return False
    if kind in PARENT_KINDS:
        return (attempts is None and not entries and model_id is None and isinstance(error, str)
                and (PARENT_KINDS[kind] is None or error in PARENT_KINDS[kind]))
    if not _count(attempts) or len(entries) != attempts or attempts > max_attempts:
        return False
    if attempts == 0:
        return kind in PAYLOAD_KINDS and error is None and model_id is None and log["latency_s"] == 0
    errors = [entry["error_name"] for entry in entries]
    if errors[-1] != error or any(name not in RETRIED for name in errors[:-1]) or (error in RETRIED and attempts != max_attempts):
        return False
    if error is None:
        return kind in ("ok", *REPLY_KINDS) and isinstance(model_id, str)
    return kind == KIND_OF.get(error, "model_error") and model_id is None


def _valid(result, item_ids, max_attempts):
    """Whether `result` is one the agent may return for an alert with these evidence ids (DEC-T05-PARENT-VALIDATION).

    The child applies the same rules before it answers. They are checked again here because the parent is the
    last place a CLOSE passes through, and it must not depend on the child having behaved.
    """
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        return False
    recommendation, reason, cited, kind = (result[key] for key in ("recommendation", "reason", "cited_ids", "failure_kind"))
    failed, invalid = result["system_failure"], result["citation_invalid"]
    if not (recommendation in ("CLOSE", "ESCALATE") and isinstance(reason, str) and isinstance(cited, list)
            and all(isinstance(one, str) for one in cited) and isinstance(failed, bool) and isinstance(invalid, bool)
            and (kind is None or kind in KINDS)):
        return False
    if failed:  # a failure is an ESCALATE with its kind, the fixed reason and nothing cited
        consistent = (recommendation == "ESCALATE" and kind is not None and reason == f"System failure: {kind}"
                      and not cited and not invalid)
    else:  # a reason, at least one cited id, and a CLOSE cites only ids of this alert
        unknown = any(one not in item_ids for one in cited)
        consistent = (kind is None and bool(reason.strip()) and bool(cited) and invalid == unknown
                      and not (recommendation == "CLOSE" and unknown))
    return consistent and _valid_log(result["log"], kind or "ok", max_attempts)


def recommend(items, model, settings, sink=None, retries=2, correlation_id=None):
    """The agent's result for one alert's evidence items. A copy of its log record is appended to `sink`, if one
    is given: the sink gets an independent deep copy, so nothing it does to the record can change the result
    returned here. The one exception is an opaque `correlation_id` whose `__deepcopy__` returns itself: that
    object stays shared between the result and the sink's record. Both it and the sink are the caller's code.

    `correlation_id` is the caller's own name for this call. It is written into the log record here, in the
    parent, and nowhere else: it is not sent to the agent process or to the model.

    The child may run for `(1 + retries) * settings.timeout_s + MARGIN_S` seconds. `timeout_s` itself is kept
    by the model, not here. No fault of the model, the agent process or its result raises. Two things do: a bad
    `retries`, which is a mistake in the caller, and an exception from `sink.append`, which is passed on as it
    is so that a log record is never lost quietly. Neither can produce a CLOSE.
    """
    if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
        raise ValueError("retries must be a whole number of 0 or more")
    begun = time.monotonic()
    try:
        job = {"payload": build_payload(items), "settings": asdict(settings), "retries": retries}
        item_ids = {item["id"] for item in job["payload"]["items"]}
        result = run_child(MODULE, job, model, limit_s=(1 + retries) * settings.timeout_s + MARGIN_S)
        if not _valid(result, item_ids, 1 + retries):
            result = failure("child_crash", "BadResult", latency_s=time.monotonic() - begun)
    except ChildTimeout:
        result = failure("child_timeout", "ChildTimeout", latency_s=time.monotonic() - begun)
    except ChildError:
        result = failure("child_crash", "ChildError", latency_s=time.monotonic() - begun)
    except Exception as error:  # anything else, such as a fault inside the model object itself
        result = failure("internal_error", type(error).__name__, latency_s=time.monotonic() - begun)
    result["log"]["correlation_id"] = correlation_id
    if sink is not None:
        sink.append(copy.deepcopy(result["log"]))
    return result
