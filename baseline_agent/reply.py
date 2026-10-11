"""Reading a model reply (DEC-T05-OUTPUT, DEC-T05-CITATIONS, DEC-T05-FAULTS). Python standard library only.

A reply is used only if it is exactly the one JSON object the prompt asks for. Anything else is a named fault,
and the caller turns every fault into ESCALATE with the SYSTEM_FAILURE flag.
"""
import json

from .payload import SCHEMA_VERSION

KEYS = {"schema_version", "recommendation", "reason", "cited_ids"}
RECOMMENDATIONS = ("CLOSE", "ESCALATE")


class ReplyFault(Exception):
    """The reply cannot be used. `kind` names why."""

    def __init__(self, kind):
        super().__init__(kind)
        self.kind = kind


def parse_reply(text, item_ids):
    """The recommendation in `text`, checked against the evidence ids of the alert, or a ReplyFault.

    A CLOSE must cite only ids from the bundle. An ESCALATE that cites an unknown id stays an ESCALATE and is
    marked `citation_invalid`, because turning it into a failure would change nothing about the action.
    """
    try:
        reply = json.loads(text)
    except (TypeError, ValueError, RecursionError):
        raise ReplyFault("malformed_output") from None
    if isinstance(reply, dict) and "schema_version" in reply and reply["schema_version"] != SCHEMA_VERSION:
        raise ReplyFault("unknown_schema_version")
    if (not isinstance(reply, dict) or set(reply) != KEYS or reply["recommendation"] not in RECOMMENDATIONS
            or not isinstance(reply["reason"], str) or not isinstance(reply["cited_ids"], list)
            or not all(isinstance(cited, str) for cited in reply["cited_ids"])):
        raise ReplyFault("malformed_output")
    if not reply["reason"].strip() or not reply["cited_ids"]:
        raise ReplyFault("missing_citations")
    unknown = any(cited not in item_ids for cited in reply["cited_ids"])
    if unknown and reply["recommendation"] == "CLOSE":
        raise ReplyFault("invalid_citation")
    return {"recommendation": reply["recommendation"], "reason": reply["reason"], "cited_ids": reply["cited_ids"],
            "citation_invalid": unknown}
