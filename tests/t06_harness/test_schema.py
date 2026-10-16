"""The shared schema of the run step's outputs (harness/schema.py, DEC-T06-MANIFEST): everything the writer produces
fits it, and a key the writer adds that the schema does not name is refused, so the two cannot drift apart."""
import copy
import json

import pytest

import fake_model
from conftest import FIXTURES, write_config
from framings import frame
from harness import manifest as records
from harness import run as harness_run
from harness import schema, score
from model_interface import Result, Settings, providers
from worldgen.loader import load_alerts

import test_score as micro  # its small in-memory runs; a module, so its tests are not collected here again


def rows_of(out, run_id):
    text = out.joinpath(run_id, "items.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.split("\n") if line]


def test_everything_the_writer_produces_fits_the_shared_schema(three_runs, tmp_path, monkeypatch):
    def exploding(items, model, settings, item_id):
        raise RuntimeError("boom")

    monkeypatch.setitem(harness_run.AGENTS, "exploding", exploding)
    out = tmp_path.joinpath("out")
    close = harness_run.run(write_config(tmp_path, agent="always_close"), out)  # a run that calls no model
    aborted = harness_run.run(write_config(tmp_path, agent="exploding"), out)
    records.supersede(out, aborted["run_set"], close["run_set"], "a written cause")
    model, settings = providers.load(FIXTURES.joinpath("model_fake.json"))
    alert = load_alerts()[0]
    item = {"item_id": f"{alert['id']}/1", "alert_id": alert["id"], "framing": 1, "twin": False, "evidence": frame(alert, 1)}
    parent_built = []  # the failure kinds only the parent builds, through the real child

    def broken(request):
        raise RuntimeError("the model object itself broke")

    for model_object in (broken, lambda request: Result("not json", 123, 1, 1, 0.0)):
        harness_run.hand_off([item], harness_run.AGENTS["baseline"], model_object, Settings("fake-1", 0, 512, 30), parent_built)
    assert {line["result"]["failure_kind"] for line in parent_built} == {"internal_error", "child_crash"}

    old = three_runs[0]  # three completed in-process runs, through the real fixture
    found = []
    for folder in (old, out):
        index = records.read_index(folder)
        found += [schema.problem(schema.INDEX_ENTRY, entry) for entry in index["runs"]]
        found += [schema.problem(schema.SUPERSEDED, record) for record in index["sets"].values()]
        found += [schema.problem(schema.HEX64, name) for name in index["sets"]]
        for entry in index["runs"]:
            manifest = json.loads(folder.joinpath(entry["run_id"], "manifest.json").read_text(encoding="utf-8"))
            found.append(schema.problem(schema.MANIFEST, manifest))
            if manifest["state"] == "completed":
                found += [schema.problem(schema.ITEM_ROW, row) for row in rows_of(folder, entry["run_id"])]
    found += [schema.problem(schema.ITEM_ROW, json.loads(json.dumps(line))) for line in parent_built]
    assert [one for one in found if one] == []  # nothing the writer produced is refused, nothing is unnamed
    assert {entry["state"] for entry in records.read_index(out)["runs"]} == {"completed", "aborted"}
    assert len(records.read_index(out)["sets"]) == 1


def test_a_key_the_writer_adds_that_the_schema_does_not_name_is_refused(three_runs):
    out, run_id = three_runs[0], three_runs[1][0]
    manifest = json.loads(out.joinpath(run_id, "manifest.json").read_text(encoding="utf-8"))
    entry, = [one for one in records.read_index(out)["runs"] if one["run_id"] == run_id]
    row = rows_of(out, run_id)[0]
    cases = [(schema.MANIFEST, manifest, ("new_field",)), (schema.MANIFEST, manifest, ("timing", "new_field")),
             (schema.MANIFEST, manifest, ("cost", "known_cost", "new_field")), (schema.INDEX_ENTRY, entry, ("new_field",)),
             (schema.ITEM_ROW, row, ("result", "log", "new_field")), (schema.ITEM_ROW, row, ("attempts", 0, "new_field"))]
    for spec, value, path in cases:
        assert schema.problem(spec, value) is None
        changed = copy.deepcopy(value)
        place = changed
        for key in path[:-1]:
            place = place[key]
        place[path[-1]] = 1
        assert "a key the schema does not name: new_field" in schema.problem(spec, changed), path


# ---- hostile values: every place the shared schema describes, each hostile value, and nothing may raise

HOSTILE = ([], {}, None, True, float("nan"), float("inf"), 10 ** 400, "", "x" * 10000)


def places(spec, value, path=()):
    """Every place inside `value` that `spec` describes, as a path of keys and list indexes, found by walking the
    schema along the value's own shape; inside an embedded table, every key of the table."""
    found = []
    if isinstance(spec, schema.ByState):
        return places(spec.specs[value["state"]], value, path)
    if isinstance(spec, schema.Either):
        spec = next(inner for inner in spec.specs if schema.problem(inner, value) is None)
        return places(spec, value, path)
    if isinstance(spec, dict):
        children = [(key, inner) for key, inner in spec.items()]
    elif isinstance(spec, schema.ListOf):
        children = [(0, spec.spec)] if value else []
    elif isinstance(spec, schema.MapOf):
        children = [(key, spec.spec) for key in value]
    elif spec is schema.TABLE:
        children = [(key, schema.TABLE if isinstance(item, dict) else None) for key, item in value.items()]
    else:
        return found
    for key, inner in children:
        found.append(path + (key,))
        if inner is not None:
            found += places(inner, value[key], path + (key,))
    return found


def put(value, path, new):
    value = copy.deepcopy(value)
    place = value
    for key in path[:-1]:
        place = place[key]
    place[path[-1]] = new
    return value


def test_no_validator_raises_on_a_hostile_value_in_any_place_the_schema_describes():
    entry, manifest, items = micro.micro_run()
    aborted_entry, aborted = micro.micro_aborted()
    started = {**entry, "state": "started", "infra_invalid": None, "calls": None, "cost": None}
    superseded = {"superseded_by": "a" * 64, "cause": "a written cause", "at": "2026-10-15T00:00:00+00:00"}
    cases = []  # (what, the value with a hostile substitution, how to check it)
    for spec, base, check in (
            (schema.MANIFEST, manifest, lambda value: score.validate_run(entry, value, items)),
            (schema.MANIFEST, aborted, lambda value: score.validate_run(aborted_entry, value, None)),
            (schema.ITEM_ROW, items[0], lambda value: score.validate_run(entry, manifest, [value, items[1]])),
            (schema.INDEX_ENTRY, entry, lambda value: (score.check_index({"runs": [value], "sets": {}}),
                                                       score.validate_run(value, manifest, items))),
            (schema.INDEX_ENTRY, aborted_entry, lambda value: (score.check_index({"runs": [value], "sets": {}}),
                                                               score.validate_run(value, aborted, None))),
            (schema.INDEX_ENTRY, started, lambda value: score.check_index({"runs": [value], "sets": {}})),
            (schema.SUPERSEDED, superseded, lambda value: score.check_index({"runs": [], "sets": {"a" * 64: value}}))):
        paths = places(spec, base)
        assert paths, spec
        cases += [(path, put(base, path, hostile), check) for path in paths for hostile in HOSTILE]
    raised = []
    for path, value, check in cases:
        try:
            check(value)
        except score.ScoreRefused:
            pass  # a problem, named: that is the expected way to say no
        except Exception as error:  # anything else is a validator that raised
            raised.append((path, type(error).__name__, str(error)[:80]))
    assert raised == [], raised[:5]
    assert len(cases) > 2000  # every place, each hostile value; its time is measured in the design document


def test_the_note_of_each_embedded_table_is_text_of_at_most_500_characters_or_null():
    from harness import cost as money
    prices = json.loads(FIXTURES.joinpath("prices.json").read_text(encoding="utf-8"))
    times = json.loads(FIXTURES.joinpath("modelled_time.json").read_text(encoding="utf-8"))
    for check, table, name in ((money.check_prices, prices, "the price table"), (money.check_times, times, "the modelled-time file")):
        for note in (None, "a short note", "x" * money.NOTE_LIMIT):
            check({**table, "note": note})  # accepted
        check({key: value for key, value in table.items() if key != "note"})  # and a note may be left out
        for note in ([{"hidden": "value"}], {"a": 1}, 5, True, "x" * (money.NOTE_LIMIT + 1)):
            with pytest.raises(money.TableError, match=f"{name}'s note must be text of at most 500 characters, or null"):
                check({**table, "note": note})
