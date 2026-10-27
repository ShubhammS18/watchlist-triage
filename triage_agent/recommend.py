"""Parent side of the upgraded agent: one alert's evidence items in, one result out, never an exception for a fault
(FR-8). The rules decide here, in the harness's process, with no model and no child process, as the reference
agents do. Everything else is the baseline agent's own `recommend`, unchanged: its child process, prompt and checks.
"""
import copy

from baseline_agent.agent import failure
from baseline_agent.payload import build_payload
from baseline_agent.recommend import recommend as ask_model

from .rules import decide


def recommend(items, model, settings, sink=None, retries=2, correlation_id=None):
    """The result for one alert's evidence items, in the baseline agent's result shape; a copy of its log record is
    appended to `sink`, if one is given. A fault in the rules gives a SYSTEM_FAILURE escalation, never a CLOSE."""
    try:
        decided = decide(build_payload(items)["items"])
    except Exception as error:  # anything wrong with the items: fail closed, as the baseline does
        result = failure("internal_error", type(error).__name__)
    else:
        if decided is None:
            return ask_model(items, model, settings, sink=sink, retries=retries, correlation_id=correlation_id)
        recommendation, reason, cited = decided
        result = {"recommendation": recommendation, "reason": reason, "cited_ids": cited, "system_failure": False,
                  "failure_kind": None, "citation_invalid": False,
                  "log": {"kind": "ok", "error_name": None, "attempts": 0, "attempt_log": [], "latency_s": 0.0,
                          "model_id": None}}
    result["log"]["correlation_id"] = correlation_id
    if sink is not None:
        sink.append(copy.deepcopy(result["log"]))
    return result
