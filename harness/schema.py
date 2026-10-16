"""The shape of everything the run step writes, shared by the writer and the score step (DEC-T06-MANIFEST): the
manifest, each run-set index entry, the index's record of superseded sets, and each item row. Python standard
library only. The run step writes these in harness/run.py and harness/manifest.py; the score step checks every
index entry against INDEX_ENTRY before it groups runs into sets, and every manifest and item row against MANIFEST
and ITEM_ROW when it loads a run. Strict: every key is required, a key the schema does not name is refused, and
every value has a type and a range. tests/t06_harness/test_schema.py fails if the writer produces anything this
schema refuses, or a key it does not name.

A spec is one of: a Rule (a named test of one value); a dict (an object with exactly these keys); ListOf(spec);
MapOf(spec) (an object with any text keys, each value of that spec); Either(spec, ...) (the first that fits); or
ByState(specs) (the spec for the object's own "state").
"""
import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from baseline_agent.recommend import KINDS


class Rule:
    def __init__(self, name, test):
        self.name, self.test = name, test

    def __repr__(self):
        return self.name


class ListOf:
    def __init__(self, spec):
        self.spec = spec


class MapOf:
    def __init__(self, spec):
        self.spec = spec


class Either:
    def __init__(self, *specs):
        self.specs = specs


class ByState:
    def __init__(self, specs):
        self.specs = specs


def _decimal(value, low, high):
    try:
        return type(value) is str and low <= Decimal(value) <= high and Decimal(value).is_finite()
    except InvalidOperation:
        return False


def _timestamp(value):
    try:
        return type(value) is str and datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


NULL = Rule("null", lambda value: value is None)
FLAG = Rule("a boolean", lambda value: type(value) is bool)  # never 0 or 1
COUNT = Rule("a whole number of 0 or more", lambda value: type(value) is int and value >= 0)
POSITIVE = Rule("a whole number of 1 or more", lambda value: type(value) is int and value >= 1)
WORKERS = Rule("a whole number from 1 to 64", lambda value: type(value) is int and 1 <= value <= 64)
def _finite(value):
    """math.isfinite, except that a whole number too large for a float is not finite here instead of raising."""
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


SECONDS = Rule("a finite number of 0 or more", lambda value: type(value) in (int, float) and _finite(value) and value >= 0)
TEXT = Rule("text", lambda value: type(value) is str)
NONEMPTY = Rule("non-empty text", lambda value: type(value) is str and value.strip() != "")
HEX64 = Rule("64 lowercase hex digits", lambda value: type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None)
HEX40 = Rule("40 lowercase hex digits", lambda value: type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) is not None)
TIMESTAMP = Rule("an ISO date and time with its offset", _timestamp)
THRESHOLD = Rule("a decimal text from 0 to 1", lambda value: _decimal(value, 0, 1))
SHARE = Rule("a decimal text from 0 to 1", lambda value: _decimal(value, 0, 1))
DECIMAL_TEXT = Rule("a decimal text of 0 or more", lambda value: _decimal(value, 0, Decimal("Infinity")))
FRAMING = Rule("one of the framings 1, 2 and 3", lambda value: type(value) is int and value in (1, 2, 3))
VERDICT = Rule("CLOSE or ESCALATE", lambda value: value in ("CLOSE", "ESCALATE") and type(value) is str)
FAILURE_KIND = Rule(f"null or one of the failure kinds {list(KINDS)}", lambda value: value is None or (type(value) is str and value in KINDS))
REVIEW_POLICY = Rule("STRICT_FOUR_EYES or none", lambda value: value in ("STRICT_FOUR_EYES", "none") and type(value) is str)
ITEMS_FILE = Rule("items.jsonl", lambda value: value == "items.jsonl")


def literal(value):
    return Rule(repr(value), lambda other, value=value: type(other) is type(value) and other == value)


def maybe(spec):
    return Either(NULL, spec)


AMOUNT = {"numerator": COUNT, "denominator": POSITIVE, "not_applicable": FLAG, "decimal": DECIMAL_TEXT, "rounded": FLAG}
CALLS = {"attempts": COUNT, "without_token_counts": COUNT, "input_tokens": COUNT, "output_tokens": COUNT}
COST = {"known_cost": AMOUNT, "currency": NONEMPTY, "attempts": COUNT, "attempts_without_token_counts": COUNT,
        "attempts_without_price": COUNT, "at_least": FLAG, "statement": NONEMPTY}
RUN_SET_INPUTS = {"agent": NONEMPTY, "commit": maybe(HEX40), "world_hash": HEX64, "prompt_hash": HEX64,
                  "model_config": HEX64, "workers": WORKERS, "pacer_per_minute": maybe(POSITIVE),
                  "infra_invalid_threshold": THRESHOLD, "price_table": HEX64, "modelled_time": HEX64}
# the two embedded tables are checked whole by the run step's own checks (harness/cost.py); here only their place
TABLE = Rule("an object", lambda value: isinstance(value, dict))

_MANIFEST_COMMON = {
    "run_id": NONEMPTY, "run_set": HEX64, "run_set_inputs": RUN_SET_INPUTS, "rerun_cause": maybe(NONEMPTY),
    "agent": NONEMPTY,
    "world": {"world_hash": HEX64, "generator_version": TEXT, "rubric_version": TEXT},
    "model": {"used": FLAG, "provider": maybe(NONEMPTY), "requested": maybe(NONEMPTY), "reported": MapOf(COUNT)},
    "prompt": maybe({"text": NONEMPTY, "sha256": HEX64}),
    "decoding": maybe({"temperature": SECONDS, "max_tokens": POSITIVE}),
    "retry_policy": maybe({"retries": COUNT, "timeout_s": SECONDS, "retried_errors": ListOf(NONEMPTY), "backoff": NULL}),
    "review_policies": ListOf(REVIEW_POLICY),
    "modelled_time": {"sha256": HEX64, "parameters": TABLE},
    "price_table": {"sha256": HEX64, "table": TABLE},
    "git": {"commit": maybe(HEX40), "dirty": FLAG},
    "config_sha256": HEX64, "framing_code_sha256": HEX64, "python_version": NONEMPTY,
    "workers": WORKERS, "pacer_per_minute": maybe(POSITIVE),
    "started_at": TIMESTAMP, "ended_at": TIMESTAMP,
    "timing": {"duration_s": SECONDS, "queue_s": SECONDS},
    "items": {"main": COUNT, "twin": COUNT, "total": COUNT},
    "calls": CALLS, "cost": COST,
}
MANIFEST = ByState({
    "completed": {**_MANIFEST_COMMON, "state": literal("completed"), "aborted": NULL,
                  "outputs": {"items_file": ITEMS_FILE, "sha256": HEX64},
                  "infra_invalid": {"threshold": THRESHOLD, "transient_items": COUNT, "transient_share": SHARE,
                                    "marked": FLAG}},
    "aborted": {**_MANIFEST_COMMON, "state": literal("aborted"),
                "aborted": {"item_id": maybe(NONEMPTY), "error_type": NONEMPTY, "message": TEXT},
                "outputs": NULL,
                "infra_invalid": {"threshold": THRESHOLD, "transient_items": COUNT, "transient_share": maybe(SHARE),
                                  "marked": NULL}},
})

_INDEX_COMMON = {"run_id": NONEMPTY, "run_set": HEX64, "dirty": FLAG, "rerun_cause": maybe(NONEMPTY),
                 "started_at": TIMESTAMP}
INDEX_ENTRY = ByState({
    "started": {**_INDEX_COMMON, "state": literal("started"), "infra_invalid": NULL, "cause": NULL, "calls": NULL,
                "cost": NULL},
    "completed": {**_INDEX_COMMON, "state": literal("completed"), "infra_invalid": FLAG, "cause": NULL,
                  "calls": CALLS, "cost": COST},
    "aborted": {**_INDEX_COMMON, "state": literal("aborted"), "infra_invalid": NULL, "cause": NONEMPTY,
                "calls": CALLS, "cost": COST},
})
SUPERSEDED = {"superseded_by": HEX64, "cause": NONEMPTY, "at": TIMESTAMP}  # index["sets"][old run set]

# the model ID of an attempt is what the provider reported, kept as it came: a provider may report a number, which
# the cost step then counts as without a price (tests/t06_harness/test_child.py); a list or an object is refused
REPORTED_ID = Rule("text, a number or null, as the provider reported it",
                   lambda value: value is None or type(value) is str or (type(value) in (int, float) and _finite(value)))
ATTEMPT = {"error": maybe(NONEMPTY), "input_tokens": maybe(COUNT), "output_tokens": maybe(COUNT), "model_id": REPORTED_ID}
ITEM_ROW = {
    "item_id": NONEMPTY, "alert_id": NONEMPTY, "framing": FRAMING, "twin": FLAG, "sent_ids": ListOf(NONEMPTY),
    "wall_s": SECONDS, "queue_s": SECONDS, "attempts": ListOf(ATTEMPT),
    "result": {
        "recommendation": VERDICT, "reason": TEXT, "cited_ids": ListOf(TEXT), "system_failure": FLAG,
        "failure_kind": FAILURE_KIND, "citation_invalid": FLAG,
        "log": {"kind": NONEMPTY, "error_name": maybe(NONEMPTY), "attempts": maybe(COUNT),
                "attempt_log": ListOf({"error_name": maybe(NONEMPTY), "latency_s": SECONDS}),
                "latency_s": SECONDS, "model_id": maybe(NONEMPTY), "correlation_id": NONEMPTY},
    },
}


def _shown(value):
    """The value as a refusal shows it, never raising: a whole number too long to print is described instead."""
    try:
        return repr(value)[:200]
    except ValueError:
        return "a whole number too long to show"


def problem(spec, value, path="it"):
    """What is wrong with `value` against `spec`, naming the field, or None."""
    if isinstance(spec, Rule):
        return None if spec.test(value) else f"{path} is not {spec.name}: {_shown(value)}"
    if isinstance(spec, dict):
        if not isinstance(value, dict):
            return f"{path} is not an object"
        missing, unknown = sorted(set(spec) - set(value)), sorted(set(value) - set(spec))
        if missing:
            return f"{path} lacks {missing[0]}"
        if unknown:
            return f"{path} has a key the schema does not name: {unknown[0]}"
        for key, inner in spec.items():
            found = problem(inner, value[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(spec, ListOf):
        if not isinstance(value, list):
            return f"{path} is not a list"
        for number, item in enumerate(value):
            found = problem(spec.spec, item, f"{path}[{number}]")
            if found:
                return found
        return None
    if isinstance(spec, MapOf):
        if not isinstance(value, dict) or not all(type(key) is str for key in value):
            return f"{path} is not an object with text keys"
        for key, item in value.items():
            found = problem(spec.spec, item, f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(spec, Either):
        found = [problem(inner, value, path) for inner in spec.specs]
        return None if None in found else found[-1]
    if isinstance(spec, ByState):
        state = value.get("state") if isinstance(value, dict) else None
        if not isinstance(value, dict) or type(state) is not str or state not in spec.specs:  # a list is not hashable
            return f"{path}.state is not one of {sorted(spec.specs)}: {_shown(state)}"
        return problem(spec.specs[state], value, path)
    raise TypeError(f"not a spec: {spec!r}")


def keys(spec, prefix=""):
    """Every key path the spec names, for the tests: 'a.b', 'a.list[].c', 'a.map{}'."""
    if isinstance(spec, dict):
        out = set()
        for key, inner in spec.items():
            out |= {f"{prefix}{key}"} | keys(inner, f"{prefix}{key}.")
        return out
    if isinstance(spec, ListOf):
        return keys(spec.spec, prefix[:-1] + "[]." if prefix else "[].")
    if isinstance(spec, Either):
        return set().union(*(keys(inner, prefix) for inner in spec.specs))
    if isinstance(spec, ByState):
        return set().union(*(keys(inner, prefix) for inner in spec.specs.values()))
    return set()
