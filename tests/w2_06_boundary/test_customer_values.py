"""No customer value in a structured field (FR-15, AC-22, DEC-W2-06-CHOICES, DEC-W2-05-MODEL-ID). Every object key and
every text or number of the audit log, the run reports, the run-set index, the manifest, the items file's structured
fields and the typed error records is matched against every customer-record value of the frozen world, model names
included. The agent's reason is the one free-text field, disclosed. Planted values show the match catches a leak in
each kind of record; look-alike texts show it does not fire on hashes, IDs and timestamps."""
import copy
import hashlib
import json
from datetime import datetime, timezone

import pytest

from baseline_agent.agent import failure
from baseline_agent.recommend import KINDS, PARENT_KINDS
from conftest import REPO, lines_of
from customer_values import FIELDS, LEFT_OUT, MATCHER, customers, hits, leaves
from framings import TITLES
from framings.names import format_name
from harness import audit

AUDIT_FREE = {f".{key}" for key in audit.FREE_TEXT}  # the agent's reason
ITEMS_FREE = {".result.reason"}
COMMITTED = ("baseline", "w2-02-runs")  # the real-model runs in the repository


def run_records(out):
    """(file name, record, free-text paths) for every record an evaluation run's output folder holds."""
    for path in sorted(out.rglob("*")):
        if path.name == "audit.jsonl":
            yield from ((path.name, line, AUDIT_FREE) for line in lines_of(path))
        elif path.name == "items.jsonl":
            yield from ((path.name, line, ITEMS_FREE) for line in lines_of(path))
        elif path.suffix == ".json":
            yield path.name, json.loads(path.read_text(encoding="utf-8")), set()


def test_the_values_are_every_customer_field_but_the_shared_record_metadata():
    records = customers()
    assert len(records) == 800
    assert {key for record in records for key in record} == set(FIELDS) | set(LEFT_OUT)  # a new field fails here
    for field in LEFT_OUT:  # the same on every world record, so it says nothing about a customer
        assert len({record[field] for record in records}) == 1
    assert len(MATCHER.values) > 3400


def test_no_structured_field_of_an_evaluation_run_holds_a_customer_value(evaluation):
    seen, checked = set(), 0
    for name, record, free in run_records(evaluation["out"]):
        seen.add(name)
        checked += sum(1 for path, _ in leaves(record) if path not in free)
        assert not hits(record, free), name
    assert seen == {"index.json", "audit.jsonl", "checkpoint.json", "manifest.json", "items.jsonl", "report.json",
                    f"{evaluation['manifest']['run_set']}.json"}
    assert checked > 100_000


def test_the_reasons_left_out_are_the_agents_and_are_disclosed(evaluation):
    """The free-text field holds what the agent wrote; nothing else is left out."""
    rows = lines_of(evaluation["run_dir"].joinpath("items.jsonl"))
    logged = [line for line in lines_of(evaluation["run_dir"].joinpath(audit.LOG)) if line["event"] == "recommendation"]
    assert [line["reason"] for line in sorted(logged, key=lambda line: line["item_id"])] == [row["result"]["reason"] for row in rows]


@pytest.mark.parametrize("folder", COMMITTED)
def test_no_structured_field_of_the_committed_real_model_runs_holds_a_customer_value(folder):
    """The only records that hold real provider model names, requested and reported."""
    out, checked, models, quoting = REPO.joinpath(folder), 0, set(), 0
    for name, record, free in run_records(out):
        checked += sum(1 for path, _ in leaves(record) if path not in free)
        assert not hits(record, free), name
        if name == "manifest.json":
            models |= {record["model"]["requested"], *record["model"]["reported"]}
        if name == "items.jsonl":
            quoting += MATCHER.match(record["result"]["reason"]) is not None
    assert checked > 300_000 and models and all(model.startswith("claude-") for model in models)
    assert quoting > 0  # the same match finds the customer values the disclosed reasons quote


@pytest.mark.parametrize("kind", KINDS)
def test_no_typed_error_record_of_any_failure_kind_holds_a_customer_value(kind):
    name = PARENT_KINDS.get(kind, ("ModelTimeout",)) or ("ValueError",)
    result = failure(kind, name[0], None if kind in PARENT_KINDS else 1, 0.5, None)
    result["log"]["correlation_id"] = "ALT-0001/2"
    assert not hits(result)


def test_the_failure_kinds_of_the_evaluation_run_are_in_its_typed_records(evaluation):
    """The fake model's scripted faults reach the item rows and the audit log as typed records."""
    kinds = {row["result"]["failure_kind"] for row in lines_of(evaluation["run_dir"].joinpath("items.jsonl"))}
    assert {"malformed_output", "missing_citations", "unknown_schema_version", "timeout", "provider_error",
            "model_refusal", "invalid_citation"} <= kinds


# ---- planted values: the match must catch each kind of value in each kind of record

def _planted_values():
    records = customers()
    with_all = next(record for record in records if all(field in record for field in FIELDS))
    nationality = min((record["nationality"] for record in records if "nationality" in record), key=len)
    titled = next(record["name"] for record in records if record["name"].split(" ")[0].rstrip(".").lower() in TITLES)
    return {"shortest nationality": nationality, "date of birth": with_all["date_of_birth"],
            "ID number": with_all["id_number"], "address": with_all["address"], "name": with_all["name"],
            "name as framing 2 writes it": format_name(titled, 2, TITLES),
            "name as framing 3 writes it": format_name(titled, 3, TITLES),
            "one name word": max(with_all["name"].split(" "), key=len), "customer ID": with_all["id"],
            "name in capitals": with_all["name"].upper(), "name inside a sentence": f"model of {with_all['name']}."}


PLANTED = _planted_values()


def _samples(evaluation):
    out, run_dir, manifest = evaluation["out"], evaluation["run_dir"], evaluation["manifest"]
    audit_lines = lines_of(run_dir.joinpath(audit.LOG))
    item = lines_of(run_dir.joinpath("items.jsonl"))[0]
    return {"audit run_started": audit_lines[0], "audit recommendation": audit_lines[1], "audit run_ended": audit_lines[-1],
            "manifest": manifest, "report": json.loads(run_dir.joinpath("report.json").read_text(encoding="utf-8")),
            "set report": json.loads(out.joinpath("sets", f"{manifest['run_set']}.json").read_text(encoding="utf-8")),
            "index": json.loads(out.joinpath("index.json").read_text(encoding="utf-8")), "item row": item,
            "typed error record": failure("child_crash", "ChildError")["log"]}


@pytest.mark.parametrize("value", PLANTED.values(), ids=PLANTED.keys())
def test_a_planted_customer_value_is_caught_in_every_kind_of_record(evaluation, value):
    assert MATCHER.match(value) is not None
    for kind, sample in _samples(evaluation).items():
        free = AUDIT_FREE if kind.startswith("audit") else ITEMS_FREE if kind == "item row" else set()
        assert not hits(sample, free), kind
        as_value, as_key = copy.deepcopy(sample), copy.deepcopy(sample)
        as_value["planted"] = value
        as_key[value] = 1
        assert hits(as_value, free) and hits(as_key, free), kind


@pytest.mark.parametrize("value", PLANTED.values(), ids=PLANTED.keys())
def test_a_customer_value_as_a_model_name_is_caught_where_it_is_kept_raw(evaluation, value):
    """DEC-W2-05-MODEL-ID: the log keeps a model name that fits the safe pattern as it is, so a customer value used as
    a model name would reach the log, and the manifest keeps every name raw. Either is caught."""
    manifest = copy.deepcopy(evaluation["manifest"])
    manifest["model"]["requested"] = value
    manifest["model"]["reported"] = {value: 1}
    assert {path for path, _ in hits(manifest)} >= {".model.requested", ".model.reported{key}"}
    started = {**lines_of(evaluation["run_dir"].joinpath(audit.LOG))[0], "requested_model": audit.model_name(value)}
    logged = audit.model_name(value)
    assert bool(hits(started)) == (not logged.startswith("sha256:"))  # caught when kept raw; a hash holds nothing


LOOK_ALIKES = [hashlib.sha256(value.encode("utf-8")).hexdigest() for value in PLANTED.values()] + [
    "20261101T060000123456Z-8f4050be", datetime.now(timezone.utc).isoformat(), "EVD-00001", "ALT-0001/2", "CUS-9999",
    "items", "review", "Thailand", "Mrs", "Rev.", "Dr", "claude-haiku-5-5", "fake-1", "1", "2026-09-30", "worldgen",
    "STRICT_FOUR_EYES", "missing_citations", "Lane", "Avenue"]


@pytest.mark.parametrize("text", LOOK_ALIKES)
def test_hashes_ids_timestamps_titles_and_address_words_do_not_match(text):
    assert MATCHER.match(text) is None
