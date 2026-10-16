"""The two reference agents (FR-24, AC-7, DEC-T06-REFERENCE). Python standard library only.

They are plain functions in the harness's own process: no model, no child process, no cost. Each returns a
result of the same shape as the baseline agent's, and cites the lowest evidence ID in sorted order, so that it
behaves the same in every framing.
"""


def _answer(recommendation, items, item_id):
    log = {"kind": "ok", "error_name": None, "attempts": 0, "attempt_log": [], "latency_s": 0.0, "model_id": None,
           "correlation_id": item_id}
    result = {"recommendation": recommendation, "reason": f"Reference agent: always {recommendation}.",
              "cited_ids": [min(item["id"] for item in items)], "system_failure": False, "failure_kind": None,
              "citation_invalid": False, "log": log}
    return result, [dict(log)]


def always_escalate(items, model, settings, item_id):
    return _answer("ESCALATE", items, item_id)


def always_close(items, model, settings, item_id):
    return _answer("CLOSE", items, item_id)
