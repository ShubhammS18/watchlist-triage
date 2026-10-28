"""Parent side of the upgraded agent: one alert's evidence items in, one result out, never an exception for a fault
(FR-8). The rules decide here, in the harness's process, with no model and no child process, as the reference agents
do. For the rest the group C question goes to the guarded child process (`child`), and the verdict and its citations
are built here from the answer: only NO_LINK closes, citing the conflicting decisive items as a rule close does; LINK
escalates citing the linking notes; UNSURE, an unreadable answer and any failure escalate.
"""
import copy
import time
from dataclasses import asdict

from baseline_agent.agent import failure
from baseline_agent.payload import build_payload
from baseline_agent.recommend import MARGIN_S, _valid, _valid_log
from model_interface.runner import ChildError, ChildTimeout, run_child

from .prompt import ANSWERS, SCHEMA_VERSION, build_messages
from .rules import SIDES, close_citation, decide

MODULE = "triage_agent.child"
NAME_FIELDS = ("name", "alias")
ANSWER_KEYS = {"answer", "reason", "note_ids", "log"}


def question(payload):
    """The group C question payload: the recorded names and every item that is not a field, never the identifiers."""
    names = [item for item in payload["items"] if item["kind"] in SIDES and item["field"] in NAME_FIELDS]
    notes = [{"id": item["id"], "value": item["value"]} for item in payload["items"] if item["kind"] not in SIDES]
    return {"schema_version": SCHEMA_VERSION, "names": names, "notes": notes, "item_count": len(names) + len(notes)}


def messages_for(payload):
    """The messages the model would get for this payload, or None when the rules decide it. For the cost bound."""
    return None if decide(payload["items"]) is not None else build_messages(question(payload))


def _answered(answer, note_ids, max_attempts):
    """Whether `answer` is one the child may return for these notes (checked again here, as the baseline does)."""
    return (isinstance(answer, dict) and set(answer) == ANSWER_KEYS and answer["answer"] in ANSWERS
            and isinstance(answer["reason"], str) and bool(answer["reason"].strip())
            and isinstance(answer["note_ids"], list) and all(one in note_ids for one in answer["note_ids"])
            and (answer["answer"] != "LINK" or bool(answer["note_ids"]))
            and _valid_log(answer["log"], "ok", max_attempts))


def ask(payload, model, settings, retries):
    """The result for a group C payload: the child's answer turned into a verdict, or a failure."""
    begun = time.monotonic()
    job = {"payload": question(payload), "settings": asdict(settings), "retries": retries}
    note_ids = {note["id"] for note in job["payload"]["notes"]}
    try:
        answer = run_child(MODULE, job, model, limit_s=(1 + retries) * settings.timeout_s + MARGIN_S)
    except ChildTimeout:
        return failure("child_timeout", "ChildTimeout", latency_s=time.monotonic() - begun)
    except ChildError:
        return failure("child_crash", "ChildError", latency_s=time.monotonic() - begun)
    if isinstance(answer, dict) and answer.get("system_failure") is True and _valid(answer, set(), 1 + retries):
        return answer
    if not _answered(answer, note_ids, 1 + retries):
        return failure("child_crash", "BadResult", latency_s=time.monotonic() - begun)
    if answer["answer"] == "NO_LINK":
        cited, why = close_citation(payload["items"])
        recommendation, reason = "CLOSE", f"Rubric rule: {why}; the model found no note linking the customer to " \
                                          f"the listed person: {answer['reason']}"
    else:
        cited = answer["note_ids"] or sorted(note_ids)
        recommendation, reason = "ESCALATE", f"Model answer {answer['answer']}: {answer['reason']}"
    return {"recommendation": recommendation, "reason": reason, "cited_ids": cited, "system_failure": False,
            "failure_kind": None, "citation_invalid": False, "log": answer["log"]}


def recommend(items, model, settings, sink=None, retries=2, correlation_id=None):
    """The result for one alert's evidence items, in the baseline agent's result shape; a copy of its log record is
    appended to `sink`, if one is given. A fault anywhere gives a SYSTEM_FAILURE escalation, never a CLOSE."""
    try:
        payload = build_payload(items)
        decided = decide(payload["items"])
        if decided is None:
            result = ask(payload, model, settings, retries)
        else:
            recommendation, reason, cited = decided
            result = {"recommendation": recommendation, "reason": reason, "cited_ids": cited, "system_failure": False,
                      "failure_kind": None, "citation_invalid": False,
                      "log": {"kind": "ok", "error_name": None, "attempts": 0, "attempt_log": [], "latency_s": 0.0,
                              "model_id": None}}
    except Exception as error:  # anything wrong with the items: fail closed, as the baseline does
        result = failure("internal_error", type(error).__name__)
    result["log"]["correlation_id"] = correlation_id
    if sink is not None:
        sink.append(copy.deepcopy(result["log"]))
    return result
