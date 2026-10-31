"""Structured fields hold no customer-record values (FR-15, AC-22, DEC-W2-05-CHOICES): every field is typed, the
agent's reason is the one free-text field, and no structured string of a real fake-model log holds any customer
value of the world."""
import json

import pytest

from audit_common import WORLD, lines_of
from harness import audit

CUSTOMER_VALUES = ("name", "address", "date_of_birth", "id_number", "nationality")


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for one in value:
            yield from strings(one)


def test_no_structured_string_of_a_run_log_holds_a_customer_value(log_bytes):
    values = {customer[key] for customer in lines_of(WORLD.joinpath("agent", "customers.jsonl"))
              for key in CUSTOMER_VALUES if key in customer}
    assert len(values) > 1000
    structured = {text for line in log_bytes.decode("utf-8").split("\n") if line
                  for key, value in json.loads(line).items() if key not in audit.FREE_TEXT for text in strings(value)}
    assert structured and not [(text, value) for text in structured for value in values if value in text]


def test_the_reason_is_the_one_free_text_field():
    free = sorted(f"{event}.{key}" for event, fields in audit.FIELDS.items() for key, check in fields.items()
                  if check(" a sentence, with a customer's name: Rev Tadrenä Tresketîs. "))
    assert free == ["recommendation.reason"] and audit.FREE_TEXT == {"reason"}


def test_the_types_refuse_free_text_floats_bools_and_unknown_fields(log_bytes):
    record = json.loads(log_bytes.split(b"\n")[900])
    assert audit.problem(record) is None
    for key, bad in (("alert_id", "Rev Tadrenä Tresketîs"), ("cited_ids", ["1985-05-18"]), ("framing", 1.0),
                     ("framing", True), ("attempts", 1.0), ("failure_kind", "Polish"), ("input_sha256", "x" * 64)):
        assert audit.problem({**record, key: bad}) == f"these fields do not have their type: ['{key}']", key
    assert "unknown ['note']" in audit.problem({**record, "note": "anything"})
    assert "missing ['reason']" in audit.problem({k: v for k, v in record.items() if k != "reason"})
    assert audit.problem({**record, "event": "decision"}) == "unknown event 'decision'"


@pytest.mark.parametrize("event", sorted(audit.FIELDS))
def test_every_event_of_a_run_log_fits_its_types(log_bytes, event):
    records = [json.loads(line) for line in log_bytes.split(b"\n") if line]
    assert [audit.problem(r) for r in records if r["event"] == event] == [None] * sum(
        1 for r in records if r["event"] == event) != []
