"""Typed error records and refusals hold no customer value (AC-22, DEC-W2-06-CHOICES). A run's abort record and the
index cause keep the error type and a hash of the exception text, never the text, which can carry a customer name:
the name-format error of the framings is forced on a world whose customer name is one word. A refusal of the score
step stays readable but describes a bad value by its type and a hash, never quoting it."""
import copy
import hashlib
import json
import shutil

import pytest

from conftest import WORLD, write_config
from customer_values import MATCHER, PLANTED_NAME, hits
from framings import TITLES
from framings.names import format_name
from harness import cost as money
from harness import manifest as records
from harness import run as harness_run
from harness import schema, score

FIRST_NAME_ITEM = "EVD-00001"  # the customer's name in ALT-0001's bundle, as the frozen world holds it


def one_word_world(folder):
    """A copy of the world, without its hidden folder, in which ALT-0001's customer name is one word of that name, with
    a manifest that matches the copy. Returns (world, the one word)."""
    world = folder.joinpath("world")
    shutil.copytree(WORLD, world, ignore=shutil.ignore_patterns("hidden"))
    path = world.joinpath("agent", "evidence.jsonl")
    lines = path.read_text(encoding="utf-8").split("\n")
    item = json.loads(lines[0])
    assert item["id"] == FIRST_NAME_ITEM and item["field"] == "name" and item["kind"] == "customer_field"
    word = max(item["value"].split(" "), key=len)
    lines[0] = json.dumps({**item, "value": word}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    path.write_text("\n".join(lines), encoding="utf-8")
    listed = json.loads(world.joinpath("MANIFEST.json").read_text(encoding="utf-8"))
    listed["files"]["agent/evidence.jsonl"] = records.sha256(path.read_bytes())
    listed["world_hash"] = records.sha256("".join(f"{name}:{listed['files'][name]}\n"
                                                  for name in sorted(listed["files"])).encode("utf-8"))
    world.joinpath("MANIFEST.json").write_text(json.dumps(listed), encoding="utf-8")
    return world, word


def test_the_name_format_error_carries_the_customer_name_in_its_text():
    """The control: without the hash, this text would reach the error records."""
    word = max(PLANTED_NAME.split(" "), key=len)
    with pytest.raises(ValueError) as raised:
        format_name(word, 2, TITLES)
    assert word in str(raised.value) and MATCHER.match(str(raised.value)) is not None


def test_a_forced_name_format_error_puts_no_customer_name_in_any_error_record(tmp_path):
    world, word = one_word_world(tmp_path)
    out = tmp_path.joinpath("out")
    manifest = harness_run.run(write_config(tmp_path, world=str(world)), out)
    with pytest.raises(ValueError) as raised:  # the very error the run met, raised again for its text
        format_name(word, 2, TITLES)
    text = str(raised.value)
    assert manifest["state"] == "aborted" and manifest["items"]["total"] == 1  # framing 1 of ALT-0001 ran
    assert manifest["aborted"] == {"item_id": None, "error_type": "ValueError",
                                   "message_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    entry, = json.loads(out.joinpath("index.json").read_text(encoding="utf-8"))["runs"]
    assert entry["cause"] == f"ValueError: message sha256 {manifest['aborted']['message_sha256']}"
    done = score.score_all(out, WORLD)  # the aborted run is listed in its set report with its calls and cost
    assert done["sets"] and not done["excluded"]
    files = [path for path in out.rglob("*") if path.is_file()]
    assert {path.name for path in files} == {"index.json", "audit.jsonl", "checkpoint.json", "manifest.json",
                                             f"{manifest['run_set']}.json"}
    for path in files:
        data = path.read_text(encoding="utf-8")
        assert word.casefold() not in data.casefold(), path.name
        records_in = [json.loads(line) for line in data.split("\n") if line] if path.suffix == ".jsonl" else [json.loads(data)]
        assert not [found for record in records_in for found in hits(record, {".reason"})], path.name


@pytest.mark.parametrize("spec", [schema.COUNT, schema.FLAG, schema.HEX64, schema.TIMESTAMP, schema.literal("completed"),
                                  schema.MANIFEST, schema.INDEX_ENTRY],
                         ids=["count", "flag", "hex64", "timestamp", "literal", "manifest", "index entry"])
def test_a_schema_refusal_never_quotes_the_bad_value(spec):
    value = PLANTED_NAME if not isinstance(spec, schema.ByState) else {"state": PLANTED_NAME}
    found = schema.problem(spec, value)
    assert found and PLANTED_NAME not in found and MATCHER.match(found) is None
    assert f"a str with sha256 {hashlib.sha256(repr(PLANTED_NAME).encode('utf-8')).hexdigest()}" in found


def test_a_disagreement_between_the_index_and_the_manifest_never_quotes_either_value(evaluation):
    entry, = json.loads(evaluation["out"].joinpath("index.json").read_text(encoding="utf-8"))["runs"]
    for field in ("rerun_cause", "cause", "run_set"):
        changed = {**copy.deepcopy(entry), field: PLANTED_NAME}
        with pytest.raises((score.ScoreRefused, score.Unassigned)) as raised:
            score.validate_manifest(changed, copy.deepcopy(evaluation["manifest"]))
        assert "disagree on" in str(raised.value) and PLANTED_NAME not in str(raised.value), field
        assert MATCHER.match(str(raised.value)) is None, field


def test_a_bad_price_never_quotes_the_value(evaluation):
    table = copy.deepcopy(evaluation["manifest"]["price_table"]["table"])
    table["models"][next(iter(table["models"]))]["input"] = PLANTED_NAME
    with pytest.raises(money.TableError) as raised:
        money.check_prices(table)
    assert PLANTED_NAME not in str(raised.value) and MATCHER.match(str(raised.value)) is None


def test_a_refused_run_s_reason_never_quotes_the_bad_value(evaluation, tmp_path):
    """End to end: a damaged manifest in a copy of the evaluation's output folder, refused by the score step."""
    out = tmp_path.joinpath("out")
    shutil.copytree(evaluation["out"], out)
    path = out.joinpath(evaluation["run_dir"].name, "manifest.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["git"]["dirty"] = PLANTED_NAME
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(score.ScoreRefused) as raised:  # its one run is refused, so nothing is written
        score.score_all(out, WORLD, rescore=True)
    assert "git.dirty is not a boolean" in str(raised.value)
    assert PLANTED_NAME not in str(raised.value) and MATCHER.match(str(raised.value)) is None
