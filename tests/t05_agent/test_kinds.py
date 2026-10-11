"""T05: a check that the failure kinds of the child and the kinds the parent accepts have not drifted apart,
for the ways of building a kind that this file can read (DEC-T05-LOG-INVARIANTS;
docs/reviews/t05-review-round-2.md, finding 3, narrowed after rounds 3 and 4).

The child's kinds are not written down here. They are read from the child's source, and then each one is
produced by the real child and must come through the parent under its own name.

The reading recognises a kind only where the child's code builds it in one of these ways:
- a text literal given to `ReplyFault(...)` or to `failure(...)` as the first argument;
- a value of `KIND_OF`, or the text fallback of `KIND_OF.get(...)`;
- the name `kind`, assigned from one of the above or from `fault.kind`.

A test below fails if one of these constructions takes a form the reader cannot follow, and a new kind found
this way that this file cannot produce also fails, until a way is added to PRODUCE. A kind that reaches a result
some other way is NOT covered and would not be noticed here: for example a result dictionary written out
directly with its own `failure_kind`, a kind passed to `failure` under another name or by keyword, or a kind
built at run time.
"""
import ast
import copy
import time
from pathlib import Path

import pytest

import baseline_agent
import baseline_agent.recommend as parent
from baseline_agent import agent
from baseline_agent.payload import build_payload
from baseline_agent.recommend import recommend
from model_interface import ModelError, ModelRefusal, BadReply, ModelTimeout, ProviderError, Settings
from model_interface.stub import Stub
from test_agent import EMPTY, ITEMS, PROVIDER_ERROR, SETTINGS, TIMEOUT, check, reply, run

PACKAGE = Path(baseline_agent.__file__).resolve().parent
CHILD_SOURCES = ("agent.py", "reply.py", "payload.py", "prompt.py")
PARENT_ONLY = {"child_timeout", "child_crash", "internal_error"}


def read_child_kinds():
    """(kinds, surprises): every failure kind written in the child's source, and anything not understood."""
    kinds, surprises = set(agent.KIND_OF.values()), []
    for name in CHILD_SOURCES:
        for node in ast.walk(ast.parse(PACKAGE.joinpath(name).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("ReplyFault", "failure"):
                first = node.args[0] if node.args else None
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    kinds.add(first.value)
                elif not (isinstance(first, ast.Name) and first.id == "kind"):
                    surprises.append(f"{name}:{node.lineno} a kind that is neither a literal nor the name kind")
            elif isinstance(node, ast.Assign) and [getattr(t, "id", None) for t in node.targets] == ["kind"]:
                value = node.value
                if isinstance(value, ast.Constant) and value.value == "ok":
                    continue
                if isinstance(value, ast.Attribute) and value.attr == "kind":  # kind = fault.kind
                    continue
                if (isinstance(value, ast.Call) and ast.unparse(value.func) == "KIND_OF.get" and len(value.args) == 2
                        and isinstance(value.args[1], ast.Constant) and isinstance(value.args[1].value, str)):
                    kinds.add(value.args[1].value)
                    continue
                surprises.append(f"{name}:{node.lineno} kind is assigned in a way this test does not know")
    return kinds, surprises


def raises_plain_model_error(request):
    raise ModelError("a model error with no name of its own")


def damaged_payload(monkeypatch, change):
    def build(items):
        payload = build_payload(items)
        change(payload)
        return payload
    monkeypatch.setattr(parent, "build_payload", build)
    return run()[0]


# kind -> every way known here of making the real child end with it. Each takes pytest's monkeypatch.
PRODUCE = {
    "malformed_output": [lambda m: run("not JSON")[0], lambda m: run(EMPTY)[0]],
    "missing_citations": [lambda m: run(reply(reason=""))[0], lambda m: run(reply("ESCALATE", []))[0]],
    "invalid_citation": [lambda m: run(reply("CLOSE", ["EVD-99999"]))[0]],
    "unknown_schema_version": [lambda m: run(reply(schema_version="2"))[0],
                               lambda m: damaged_payload(m, lambda payload: payload.update(schema_version="2"))],
    "truncated_evidence": [lambda m: damaged_payload(m, lambda payload: payload["items"].pop())],
    "model_refusal": [lambda m: run({"fail": "refusal"})[0], lambda m: run(TIMEOUT, {"fail": "refusal"})[0]],
    "timeout": [lambda m: run(default=TIMEOUT)[0], lambda m: run(default=TIMEOUT, retries=0)[0]],
    "provider_error": [lambda m: run(TIMEOUT, default=PROVIDER_ERROR)[0]],
    "model_error": [lambda m: recommend(ITEMS, raises_plain_model_error, SETTINGS)],
}


def test_the_child_source_has_the_shape_this_reading_relies_on():
    kinds, surprises = read_child_kinds()
    assert not surprises
    assert len(kinds) >= 9 and "ok" not in kinds


def test_every_kind_the_child_can_emit_is_known_to_the_parent_and_nothing_else_is():
    kinds, _ = read_child_kinds()
    assert kinds <= set(parent.KINDS), f"the parent does not know {sorted(kinds - set(parent.KINDS))}"
    assert set(parent.KINDS) == kinds | PARENT_ONLY
    assert set(parent.PAYLOAD_KINDS) | set(parent.REPLY_KINDS) | set(agent.KIND_OF.values()) | {"model_error"} == kinds
    assert set(agent.RETRIED) <= set(agent.KIND_OF)


def test_there_is_a_way_to_produce_every_kind_the_child_can_emit():
    assert set(PRODUCE) == read_child_kinds()[0]


@pytest.mark.parametrize("kind, number", [(kind, n) for kind, ways in PRODUCE.items() for n in range(len(ways))])
def test_the_real_child_emits_the_kind_and_the_parent_lets_it_through_under_its_own_name(monkeypatch, kind, number):
    result = PRODUCE[kind][number](monkeypatch)
    check(result)
    assert (result["recommendation"], result["system_failure"], result["failure_kind"]) == ("ESCALATE", True, kind)
    assert result["log"]["error_name"] != "BadResult"


# ---- no false rejection: everything the real child and the parent produce passes the parent's own rules

IDS = {item["id"] for item in ITEMS}


def recheck(result, retries=2):
    """Apply the parent's check once more to a result that `recommend` returned."""
    check(result)
    raw = copy.deepcopy(result)
    del raw["log"]["correlation_id"]
    assert parent._valid(raw, IDS, 1 + retries), result
    assert result["log"]["error_name"] != "BadResult"
    assert all(entry["latency_s"] <= result["log"]["latency_s"] for entry in result["log"]["attempt_log"])
    return result


def raise_(error):
    raise error


ENDINGS = {  # how the last model call ends -> what the result must be
    "a valid close": (lambda request: Stub(default=reply("CLOSE"))(request), "ok"),
    "a valid escalate": (lambda request: Stub(default=reply("ESCALATE"))(request), "ok"),
    "an escalate citing an unknown id": (lambda request: Stub(default=reply("ESCALATE", ["EVD-99999"]))(request), "ok"),
    "not JSON": (lambda request: Stub(default="not JSON")(request), "malformed_output"),
    "an empty reason": (lambda request: Stub(default=reply(reason=""))(request), "missing_citations"),
    "a close citing an unknown id": (lambda request: Stub(default=reply("CLOSE", ["EVD-99999"]))(request), "invalid_citation"),
    "schema version 2": (lambda request: Stub(default=reply(schema_version="2"))(request), "unknown_schema_version"),
    "an empty reply": (lambda request: raise_(BadReply("empty")), "malformed_output"),
    "a refusal": (lambda request: raise_(ModelRefusal("no")), "model_refusal"),
    "a plain model error": (lambda request: raise_(ModelError("other")), "model_error"),
}


@pytest.mark.parametrize("retries", [0, 1, 2, 3])
def test_every_ending_after_every_number_of_slow_retried_errors_passes_the_parents_rules(retries):
    for ending, (last_call, expected) in ENDINGS.items():
        for errors_first in range(retries + 2):  # one more than can be retried: the run then ends on the error
            calls = []

            def model(request):
                calls.append(1)
                time.sleep(0.002)  # so that every attempt has a latency above zero
                if len(calls) <= errors_first:
                    raise (ModelTimeout, ProviderError)[len(calls) % 2]("slow and then failed")
                return last_call(request)

            result = recheck(recommend(ITEMS, model, SETTINGS, retries=retries), retries)
            where = f"{ending}, {errors_first} errors first, {retries} retries"
            if errors_first > retries:
                expected_here = ("timeout", "provider_error")[len(calls) % 2]
                assert len(calls) == retries + 1, where
            else:
                expected_here = expected
                assert len(calls) == errors_first + 1, where
            assert result["log"]["kind"] == expected_here and result["log"]["attempts"] == len(calls), where
            assert result["log"]["latency_s"] >= 0.002 * len(calls), where


@pytest.mark.parametrize("kind, number", [(kind, n) for kind, ways in PRODUCE.items() for n in range(len(ways))])
def test_every_way_of_producing_a_child_kind_passes_the_parents_rules(monkeypatch, kind, number):
    result = PRODUCE[kind][number](monkeypatch)
    retries = 0 if result["log"]["attempts"] == 1 and kind == "timeout" else 2
    assert recheck(result, retries)["failure_kind"] == kind


def test_the_three_kinds_the_parent_builds_pass_its_own_rules(monkeypatch):
    broken = recommend(ITEMS, lambda request: raise_(RuntimeError("a bug in the adapter")), SETTINGS)
    assert recheck(broken)["failure_kind"] == "internal_error"
    monkeypatch.setattr(parent, "MARGIN_S", 0.3)
    slow = recommend(ITEMS, lambda request: time.sleep(3), Settings("stub-1", 0, 512, 0.1), retries=0)
    assert recheck(slow, 0)["failure_kind"] == "child_timeout"
    monkeypatch.setattr(parent, "MODULE", "baseline_agent.no_such_module")
    assert recheck(run()[0])["failure_kind"] == "child_crash"


def test_all_twelve_kinds_were_covered_by_the_runs_above():
    produced = set(PRODUCE) | {expected for _, expected in ENDINGS.values()} - {"ok"} | PARENT_ONLY
    assert produced == set(parent.KINDS)
