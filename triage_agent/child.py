"""The upgraded agent's model call, in the child process: one group C question in, one answer out (FR-8). It follows
the baseline agent's rules for retries, faults and the log record, and reuses its code for them. Python standard
library only; it opens no files.

The answer is {answer, reason, note_ids, log}, or the baseline's failure result for any fault. A reply is used only if
it is exactly the JSON object the prompt asks for; LINK must cite a note, and every cited id must be a note shown.
"""
import json
import time

from baseline_agent.agent import KIND_OF, RETRIED, failure
from baseline_agent.reply import ReplyFault
from model_interface import ModelError, Request, Settings

from .prompt import ANSWERS, SCHEMA_VERSION, build_messages

KEYS = {"schema_version", "answer", "reason", "note_ids"}


def parse_answer(text, note_ids):
    """The answer in `text`, checked against the ids of the notes shown, or a ReplyFault."""
    try:
        reply = json.loads(text)
    except (TypeError, ValueError, RecursionError):
        raise ReplyFault("malformed_output") from None
    if isinstance(reply, dict) and "schema_version" in reply and reply["schema_version"] != SCHEMA_VERSION:
        raise ReplyFault("unknown_schema_version")
    if (not isinstance(reply, dict) or set(reply) != KEYS or reply["answer"] not in ANSWERS
            or not isinstance(reply["reason"], str) or not reply["reason"].strip()
            or not isinstance(reply["note_ids"], list) or not all(isinstance(one, str) for one in reply["note_ids"])):
        raise ReplyFault("malformed_output")
    if reply["answer"] == "LINK" and not reply["note_ids"]:
        raise ReplyFault("missing_citations")
    if any(one not in note_ids for one in reply["note_ids"]):
        raise ReplyFault("invalid_citation")
    return {"answer": reply["answer"], "reason": reply["reason"], "note_ids": reply["note_ids"]}


def main(model, job):
    """`job` is {"payload": the question payload, "settings": the four Settings fields, "retries": n}. A timeout or a
    provider error is tried again, up to `retries` more times; nothing else is."""
    payload = job["payload"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        return failure("unknown_schema_version", attempts=0)
    if payload.get("item_count") != len(payload["names"]) + len(payload["notes"]):
        return failure("truncated_evidence", attempts=0)
    request = Request(build_messages(payload), Settings(**job["settings"]))
    note_ids = {item["id"] for item in payload["notes"]}
    model_id, attempt_log = None, []
    begun = time.monotonic()
    for attempt in range(1, job["retries"] + 2):
        started = time.monotonic()
        fields = error_name = None
        try:
            reply = model(request)
            model_id = reply.model_id
            fields = parse_answer(reply.text, note_ids)
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
    return {**fields, "log": {"kind": "ok", "error_name": None, "attempts": attempt, "attempt_log": attempt_log,
                              "latency_s": time.monotonic() - begun, "model_id": model_id}}
