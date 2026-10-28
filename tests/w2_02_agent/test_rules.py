"""W2-02: the rules against the rubric's own statements (docs/rubric.md v1.2), on hand-made items, and the agent's
way of using them: a rule decision calls no model, everything else goes to the baseline's model call unchanged."""
import pytest

from triage_agent import recommend as agent
from triage_agent import record
from triage_agent.rules import decide

from conftest import REPO


def items(customer=(), watchlist=(), snippets=0, other=()):
    made = [{"id": f"C-{field}", "kind": "customer_field", "field": field, "value": value} for field, value in customer]
    made += [{"id": f"W-{field}", "kind": "watchlist_field", "field": field, "value": value} for field, value in watchlist]
    made += [{"id": f"S-{n}", "kind": "snippet", "field": "snippet", "value": "a note"} for n in range(snippets)]
    return made + list(other)


DOB, OTHER_DOB, ID, OTHER_ID = ("date_of_birth", "1970-01-01"), ("date_of_birth", "1980-02-02"), ("id_number", "A1"), ("id_number", "B2")
NAT, OTHER_NAT = ("nationality", "AA"), ("nationality", "BB")


@pytest.mark.parametrize("given, recommendation, cited", [
    # close: a decisive identifier conflicts, none agrees, no snippet
    (items([DOB], [OTHER_DOB]), "CLOSE", ["C-date_of_birth", "W-date_of_birth"]),
    (items([DOB, ID], [OTHER_DOB, OTHER_ID]), "CLOSE", ["C-date_of_birth", "C-id_number", "W-date_of_birth", "W-id_number"]),
    (items([ID, NAT], [OTHER_ID, NAT]), "CLOSE", ["C-id_number", "W-id_number"]),  # nationality agreeing decides nothing
    # escalate: identity is not ruled out
    (items([DOB, ID], [OTHER_DOB, ID]), "ESCALATE", None),  # a decisive identifier agrees beside the conflict
    (items([DOB, ID], [DOB, ID]), "ESCALATE", None),  # the clean pattern
    (items([NAT], [OTHER_NAT]), "ESCALATE", None),  # a nationality conflict on its own never closes
    (items([DOB], []), "ESCALATE", ["C-date_of_birth"]),  # unavailable: one side lacks it
    (items([], [], snippets=1), "ESCALATE", None),  # nothing to compare; a snippet never closes on its own
    (items([DOB, NAT], [DOB, OTHER_NAT], snippets=2), "ESCALATE", None),  # agreeing date of birth; snippets cannot close
])
def test_what_the_fields_settle(given, recommendation, cited):
    found, reason, ids = decide(given)
    assert found == recommendation and reason.startswith("Rubric rule: ") and ids
    assert set(ids) <= {item["id"] for item in given}
    if cited is not None:
        assert ids == cited


@pytest.mark.parametrize("given", [
    items([DOB], [OTHER_DOB], snippets=1),  # condition 3 needs the snippet read
    items([DOB], [OTHER_DOB], other=[{"id": "X-1", "kind": "note", "field": "note", "value": "text"}]),  # unknown kind: text
    items([DOB, ("date_of_birth", "1990-03-03")], [OTHER_DOB]),  # two dates of birth on one side
])
def test_what_the_fields_do_not_settle_goes_to_the_model(given):
    assert decide(given) is None


def bundle(given):
    return [{**item, "as_of_date": "2026-09-30"} for item in given]


def test_a_rule_decision_calls_no_model_and_a_snippet_case_goes_to_the_question(monkeypatch):
    asked = []

    def ask(payload, model, settings, retries):
        asked.append([item["id"] for item in payload["items"]])
        return {"asked": True, "log": {}}
    monkeypatch.setattr(agent, "ask", ask)
    never = lambda request: pytest.fail("a rule decision called the model")
    sink = []
    result = agent.recommend(bundle(items([DOB], [OTHER_DOB])), never, None, sink=sink, correlation_id="a/1")
    assert result["recommendation"] == "CLOSE" and result["log"]["attempts"] == 0 and sink == [result["log"]]
    assert result["log"]["correlation_id"] == "a/1" and not result["system_failure"]
    assert agent.recommend(bundle(items([DOB], [OTHER_DOB], snippets=1)), never, None)["asked"] is True
    assert asked == [["C-date_of_birth", "W-date_of_birth", "S-0"]]


def test_items_that_cannot_be_read_fail_closed():
    result = agent.recommend([{"id": "E-1"}], None, None, correlation_id="b/2")
    assert result["recommendation"] == "ESCALATE" and result["system_failure"] and result["failure_kind"] == "internal_error"


def test_the_rule_code_hash_covers_the_rules_the_verdicts_and_the_answer_reading():
    import hashlib
    digest = hashlib.sha256()
    for name in ("rules.py", "recommend.py", "child.py"):
        digest.update(name.encode() + b"\0" + REPO.joinpath("triage_agent", name).read_bytes() + b"\0")
    assert record.PROMPT["rule_code_sha256"] == digest.hexdigest() == record.rule_code_sha256()
