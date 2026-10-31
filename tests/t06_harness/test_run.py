"""T06 stage 1: the run step. Configuration, the agent-side world check, one bundle per call, the token wrapper,
harness faults, the real child against the in-process path, and hidden/ left alone.

Expected numbers are counted here from the world and the fake model, never with harness code.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

import fake_model
from conftest import FIXTURES, write_config
from framings import FRAMINGS, frame
from harness import run as harness_run
from model_interface import ModelTimeout, Result, providers
from worldgen.harness_twins import load_twins
from worldgen.loader import load_alerts

REPO = Path(__file__).resolve().parents[2]
WORLD = REPO.joinpath("data", "world")
ALERTS, TWINS = load_alerts(), load_twins()
IDS_OF = {alert["id"]: sorted(item["id"] for item in alert["evidence"]) for alert in ALERTS + TWINS}
LINE_KEYS = {"item_id", "alert_id", "framing", "twin", "sent_ids", "result", "wall_s", "queue_s", "attempts"}


def python(code, *args):
    """Run `code` in a fresh interpreter at the repository root, and return what it printed as JSON."""
    done = subprocess.run([sys.executable, "-B", "-c", code, *args], cwd=REPO, capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": str(REPO)})
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


# ---- configuration

def test_the_fixture_configuration_loads():
    config = harness_run.load_config(FIXTURES.joinpath("run.json"))
    assert config["agent"] == "baseline" and config["world"] == WORLD and config["threshold"] == "0.05"
    assert config["settings"].model == "fake-1" and isinstance(config["model"], fake_model.Fake)


def test_the_shipped_agent_registry_holds_exactly_four_agents_and_never_the_in_process_one():
    shipped = python("import json; from harness.run import AGENTS; print(json.dumps(sorted(AGENTS)))")
    assert shipped == ["always_close", "always_escalate", "baseline", "triage"] and "inprocess" not in shipped  # W2-02
    assert "inprocess" in harness_run.AGENTS  # here it is, but only because these tests registered it


@pytest.mark.parametrize("key", harness_run.CONFIG_KEYS)
def test_a_missing_key_is_refused(tmp_path, key):
    config = json.loads(write_config(tmp_path).read_text(encoding="utf-8"))
    del config[key]
    tmp_path.joinpath("run.json").write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(harness_run.ConfigError, match=key):
        harness_run.load_config(tmp_path.joinpath("run.json"))


@pytest.mark.parametrize("changes, message", [
    ({"extra": 1}, "unknown"),
    ({"agent": "no-such-agent"}, "unknown agent"),
    ({"workers": 0}, "workers must be a whole number from 1 to 64"),
    ({"workers": 65}, "workers must be a whole number from 1 to 64"),
    ({"workers": True}, "workers must be a whole number"),
    ({"workers": "2"}, "workers must be a whole number"),
    ({"workers": 2.0}, "workers must be a whole number"),
    ({"pacer_per_minute": 0}, "pacer_per_minute must be null"),
    ({"pacer_per_minute": -5}, "pacer_per_minute must be null"),
    ({"pacer_per_minute": 1.5}, "pacer_per_minute must be null"),
    ({"pacer_per_minute": "60"}, "pacer_per_minute must be null"),
    ({"pacer_per_minute": True}, "pacer_per_minute must be null"),
    ({"infra_invalid_threshold": 0.05}, "decimal string"),
    ({"infra_invalid_threshold": "1.5"}, "decimal string"),
    ({"infra_invalid_threshold": "NaN"}, "decimal string"),
    ({"infra_invalid_threshold": "a lot"}, "decimal string"),
    ({"price_table": None}, "price_table must be a path"),
    ({"price_table": "no-such-file.json"}, "cannot read"),
    ({"model_config": "no-such-file.json"}, "cannot read"),
    ({"modelled_time": None}, "every run needs the modelled-time parameter file"),
    ({"modelled_time": "no-such-file.json"}, "cannot read"),
    ({"modelled_time": 5}, "every run needs the modelled-time parameter file"),
    ({"modelled_time": ""}, "every run needs the modelled-time parameter file"),
])
def test_a_wrong_configuration_is_refused(tmp_path, changes, message):
    with pytest.raises(harness_run.ConfigError, match=message):
        harness_run.load_config(write_config(tmp_path, **changes))


def test_an_unknown_provider_is_refused(tmp_path):
    model = tmp_path.joinpath("model.json")
    model.write_text(json.dumps({"provider": "nobody", "model": "m", "temperature": 0, "max_tokens": 1, "timeout_s": 1}))
    with pytest.raises(harness_run.ConfigError, match="unknown provider"):
        harness_run.load_config(write_config(tmp_path, model_config=str(model)))


@pytest.mark.parametrize("agent", ["inprocess", "baseline", "always_escalate", "always_close"])
def test_every_run_needs_the_parameter_file_the_stub_and_the_reference_agents_too(tmp_path, agent):
    stub = str(REPO.joinpath("model_interface", "config.json"))
    with pytest.raises(harness_run.ConfigError, match="every run needs the modelled-time parameter file"):
        harness_run.run(write_config(tmp_path, agent=agent, model_config=stub, modelled_time=None), tmp_path.joinpath("out"))
    assert not tmp_path.joinpath("out").exists()  # refused before anything was started
    config = harness_run.load_config(write_config(tmp_path, agent=agent, model_config=stub))
    assert config["model_config"]["provider"] == "stub" and config["modelled_time"]["unit"] == "minutes"


def test_an_output_folder_inside_the_repository_is_refused(tmp_path):
    for inside in (REPO.joinpath("runs"), REPO.joinpath("tests", "t06_harness", "out"), REPO):
        with pytest.raises(harness_run.ConfigError, match="outside the repository"):
            harness_run.run(write_config(tmp_path), inside)
    assert not REPO.joinpath("runs").exists() and not REPO.joinpath("tests", "t06_harness", "out").exists()


# ---- the agent-side world check

def copy_world(folder):
    """A copy of the world without its hidden folder, which the run step must never need."""
    world = folder.joinpath("world")
    shutil.copytree(WORLD, world, ignore=shutil.ignore_patterns("hidden"))
    return world


def test_the_world_check_passes_on_the_committed_world_and_never_reads_hidden(tmp_path):
    listed = json.loads(WORLD.joinpath("MANIFEST.json").read_text(encoding="utf-8"))
    harness_run.check_world(WORLD, listed)
    harness_run.check_world(copy_world(tmp_path), listed)  # no hidden folder there at all


@pytest.mark.parametrize("name", ["agent/customers.jsonl", "agent/evidence.jsonl", "agent/twin_alerts.jsonl", "README.md"])
def test_a_changed_world_file_aborts_the_run_before_any_call(tmp_path, name):
    world = copy_world(tmp_path)
    with world.joinpath(name).open("ab") as file:
        file.write(b" ")
    manifest = harness_run.run(write_config(tmp_path, world=str(world)), tmp_path.joinpath("out"))
    assert manifest["state"] == "aborted" and manifest["outputs"] is None
    assert manifest["aborted"] == {"item_id": None, "error_type": "WorldMismatch",
                                   "message": f"{name} does not match the world manifest"}
    assert manifest["calls"]["attempts"] == 0 and manifest["items"]["total"] == 0


def test_a_manifest_that_contradicts_itself_aborts_the_run(tmp_path):
    world = copy_world(tmp_path)
    listed = json.loads(world.joinpath("MANIFEST.json").read_text(encoding="utf-8"))
    listed["world_hash"] = "0" * 64
    world.joinpath("MANIFEST.json").write_text(json.dumps(listed), encoding="utf-8")
    manifest = harness_run.run(write_config(tmp_path, world=str(world)), tmp_path.joinpath("out"))
    assert manifest["state"] == "aborted" and manifest["aborted"]["error_type"] == "WorldMismatch"
    assert "world_hash" in manifest["aborted"]["message"]


# ---- one bundle per call, and what a run holds

def test_every_call_carries_exactly_one_bundle(tmp_path, monkeypatch):
    seen = []

    def recording(items, model, settings, item_id):
        seen.append((item_id, sorted(item["id"] for item in items)))
        return fake_model.inprocess(items, model, settings, item_id)

    monkeypatch.setitem(harness_run.AGENTS, "recording", recording)
    manifest = harness_run.run(write_config(tmp_path, agent="recording"), tmp_path.joinpath("out"))
    assert manifest["state"] == "completed" and len(seen) == 615 * 3
    for item_id, ids in seen:
        alert_id, framing = item_id.split("/")
        assert ids == IDS_OF[alert_id] and int(framing) in FRAMINGS  # the IDs of that one alert and nothing else
    assert Counter(item_id for item_id, _ in seen) == Counter(f"{alert_id}/{framing}" for alert_id in IDS_OF
                                                              for framing in FRAMINGS)


def test_a_run_holds_1800_main_items_and_45_twin_items(full_run):
    _, manifest, lines = full_run
    assert manifest["items"] == {"main": 1800, "twin": 45, "total": 1845} == {
        "main": sum(not line["twin"] for line in lines), "twin": sum(line["twin"] for line in lines), "total": len(lines)}
    assert {line["alert_id"] for line in lines if line["twin"]} == {twin["id"] for twin in TWINS}
    assert {line["alert_id"] for line in lines if not line["twin"]} == {alert["id"] for alert in ALERTS}
    assert all(line["alert_id"].startswith("TWN-") == line["twin"] for line in lines)


def test_the_items_file_is_sorted_and_every_line_has_its_shape(full_run):
    _, _, lines = full_run
    ids = [line["item_id"] for line in lines]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    for line in lines:
        assert set(line) == LINE_KEYS and line["item_id"] == f"{line['alert_id']}/{line['framing']}"
        assert line["sent_ids"] == IDS_OF[line["alert_id"]] and line["wall_s"] >= 0
        assert line["result"]["log"]["correlation_id"] == line["item_id"]


def test_the_results_are_what_the_fake_was_scripted_to_give(full_run):
    """Counted here from the fake's own table, with no harness code."""
    _, _, lines = full_run
    kind_of = {"timeout": "timeout", "provider_error": "provider_error", "refusal": "model_refusal",
               "empty": "malformed_output", "not_json": "malformed_output", "no_citations": "missing_citations",
               "wrong_version": "unknown_schema_version", "close_unknown_id": "invalid_citation"}
    expected = Counter()
    for alert_id, ids in IDS_OF.items():
        expected[kind_of.get(fake_model.outcome_of(ids))] += len(FRAMINGS)
    assert Counter(line["result"]["failure_kind"] for line in lines) == expected
    assert sum(line["result"]["citation_invalid"] for line in lines) == 3 * sum(
        fake_model.outcome_of(ids) == "escalate_unknown_id" for ids in IDS_OF.values())


# ---- the token wrapper

def test_the_token_wrapper_notes_every_attempt_and_passes_errors_on():
    replies = [ModelTimeout("slow"), Result("text", "m-1", 7, 3, 0.0), Result("text", "m-1", None, None, 0.0)]

    def model(request):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    tokens = harness_run.Tokens(model)
    with pytest.raises(ModelTimeout):
        tokens(None)
    assert tokens(None).input_tokens == 7 and tokens(None).input_tokens is None
    assert tokens.attempts == [  # prompt_bytes: W2-02; None here, since the request carries no messages
        {"error": "ModelTimeout", "input_tokens": None, "output_tokens": None, "model_id": None, "prompt_bytes": None},
        {"error": None, "input_tokens": 7, "output_tokens": 3, "model_id": "m-1", "prompt_bytes": None},
        {"error": None, "input_tokens": None, "output_tokens": None, "model_id": "m-1", "prompt_bytes": None}]
    assert harness_run._calls(tokens.attempts) == {"attempts": 3, "without_token_counts": 2, "input_tokens": 7,
                                                   "output_tokens": 3}


def test_every_item_has_its_own_attempts_retries_and_failures_included(full_run):
    _, manifest, lines = full_run
    retried = ("timeout", "provider_error")  # the two faults of the fake that T05 retries
    for line in lines:
        outcome = fake_model.outcome_of(line["sent_ids"])
        tries = 3 if outcome in retried else 1
        assert len(line["attempts"]) == tries == line["result"]["log"]["attempts"], line["item_id"]
        failed = outcome in fake_model.FAULTS
        assert all((one["input_tokens"] is None) == failed and (one["error"] is not None) == failed
                   for one in line["attempts"])
    attempts = sum(3 if fake_model.outcome_of(ids) in retried else 1 for ids in IDS_OF.values()) * 3
    without = sum({"timeout": 3, "provider_error": 3, "refusal": 1, "empty": 1}.get(fake_model.outcome_of(ids), 0)
                  for ids in IDS_OF.values()) * 3
    assert manifest["calls"]["attempts"] == attempts and manifest["calls"]["without_token_counts"] == without
    assert manifest["calls"]["input_tokens"] == sum(one["input_tokens"] or 0 for line in lines for one in line["attempts"])
    assert manifest["model"]["reported"] == {"fake-1": attempts - without}


# ---- harness faults

def test_an_exception_from_the_agent_aborts_the_run_and_names_the_item(tmp_path, monkeypatch):
    states = []

    def exploding(items, model, settings, item_id):
        if item_id == "ALT-0001/3":
            index = json.loads(tmp_path.joinpath("out", "index.json").read_text(encoding="utf-8"))
            states.append([run["state"] for run in index["runs"]])
            raise RuntimeError("boom in the agent")
        return fake_model.inprocess(items, model, settings, item_id)

    monkeypatch.setitem(harness_run.AGENTS, "exploding", exploding)
    manifest = harness_run.run(write_config(tmp_path, agent="exploding"), tmp_path.joinpath("out"))
    assert states == [["started"]]  # the run was listed before it finished
    assert manifest["state"] == "aborted" and manifest["outputs"] is None
    assert manifest["aborted"] == {"item_id": "ALT-0001/3", "error_type": "RuntimeError", "message": "boom in the agent"}
    assert manifest["items"]["total"] == 2 and manifest["infra_invalid"]["marked"] is None
    run_dir = tmp_path.joinpath("out", manifest["run_id"])
    assert sorted(path.name for path in run_dir.iterdir()) == ["audit.jsonl", "checkpoint.json", "manifest.json"]  # no items
    entry, = json.loads(tmp_path.joinpath("out", "index.json").read_text(encoding="utf-8"))["runs"]
    assert entry["state"] == "aborted" and entry["cause"] == "RuntimeError: boom in the agent"
    assert entry["calls"] == manifest["calls"] and entry["calls"]["attempts"] >= 2


@pytest.mark.parametrize("records", [[], "two", "changed"])
def test_a_wrong_log_hand_over_aborts_the_run(tmp_path, monkeypatch, records):
    def careless(items, model, settings, item_id):
        result, sink = fake_model.inprocess(items, model, settings, item_id)
        if records == "two":
            return result, sink * 2
        if records == "changed":
            return result, [{**sink[0], "kind": "something else"}]
        return result, []

    monkeypatch.setitem(harness_run.AGENTS, "careless", careless)
    manifest = harness_run.run(write_config(tmp_path, agent="careless"), tmp_path.joinpath("out"))
    assert manifest["state"] == "aborted" and manifest["aborted"]["item_id"] == "ALT-0001/1"
    assert manifest["aborted"]["error_type"] == "ValueError" and "one log record" in manifest["aborted"]["message"]


def test_the_failing_items_own_attempts_are_counted_in_an_aborted_run(tmp_path, monkeypatch):
    def late(items, model, settings, item_id):
        result, sink = fake_model.inprocess(items, model, settings, item_id)
        if item_id == "ALT-0001/2":
            raise RuntimeError("after the model was called")
        return result, sink

    monkeypatch.setitem(harness_run.AGENTS, "late", late)
    manifest = harness_run.run(write_config(tmp_path, agent="late"), tmp_path.joinpath("out"))
    first = 3 if fake_model.outcome_of(IDS_OF["ALT-0001"]) in ("timeout", "provider_error") else 1  # calls per item
    assert manifest["items"]["total"] == 1 and manifest["calls"]["attempts"] == 2 * first


# ---- the real child against the in-process path

def without_timings(line):
    line = copy.deepcopy(line)
    del line["wall_s"], line["queue_s"]
    line["result"]["log"]["latency_s"] = None
    for attempt in line["result"]["log"]["attempt_log"]:
        attempt["latency_s"] = None
    return line


def test_the_real_child_and_the_in_process_path_give_identical_results():
    """One alert for every outcome of the fake, in all three framings, through the guarded child process."""
    chosen = {}
    for alert in ALERTS:
        chosen.setdefault(fake_model.outcome_of(IDS_OF[alert["id"]]), alert)
    assert set(chosen) == {name for name, _ in fake_model.SHARES}
    items = [{"item_id": f"{alert['id']}/{framing}", "alert_id": alert["id"], "framing": framing, "twin": False,
              "evidence": frame(alert, framing)} for alert in chosen.values() for framing in FRAMINGS]
    model, settings = providers.load(FIXTURES.joinpath("model_fake.json"))
    child, inside = [], []
    harness_run.hand_off(items, harness_run.AGENTS["baseline"], model, settings, child)
    harness_run.hand_off(items, fake_model.inprocess, model, settings, inside)
    assert len(child) == len(items) == 36
    assert [without_timings(line) for line in child] == [without_timings(line) for line in inside]
    kinds = {line["result"]["failure_kind"] for line in child}
    assert kinds == {None, "timeout", "provider_error", "model_refusal", "malformed_output", "missing_citations",
                     "unknown_schema_version", "invalid_citation"}
    assert {line["result"]["recommendation"] for line in child} == {"CLOSE", "ESCALATE"}


# ---- hidden/ is left alone

HIDDEN_PROBE = """
import json, sys
opened = []
sys.addaudithook(lambda event, args: opened.append(str(args[0])) if event == "open" and "/hidden/" in str(args[0]) else None)
sys.path.insert(0, sys.argv[1])
import pytest, fake_model, conftest
from harness import run
with pytest.MonkeyPatch.context() as patch:
    fake_model.register(patch)
    manifest = run.run(conftest.write_config(sys.argv[2]), sys.argv[2] + "/out")
before = list(opened)
open(sys.argv[2] + "/hidden/control.txt").close()   # the control: the hook does see an open under a hidden folder
print(json.dumps({"state": manifest["state"], "total": manifest["items"]["total"], "before": before,
                  "after": opened, "truth": "worldgen.truth" in sys.modules}))
"""


RUN_AND_SCORE = """
import contextlib, io, json, sys
sys.path.insert(0, sys.argv[1])
import pytest, fake_model, conftest
from harness import __main__ as cli
seen = {}
def watched_run(*arguments, **options):
    manifest = run(*arguments, **options)
    seen["truth_after_the_run"] = "worldgen.truth" in sys.modules
    seen["score_after_the_run"] = "harness.score" in sys.modules
    return manifest
run = cli.run
with pytest.MonkeyPatch.context() as patch:
    fake_model.register(patch)
    patch.setattr(cli, "run", watched_run)
    with contextlib.redirect_stdout(io.StringIO()) as said:  # what the command prints is checked below
        seen["code"] = cli.main(["run-and-score", str(conftest.write_config(sys.argv[2])), sys.argv[2] + "/out"])
seen["said"] = said.getvalue().split("\\n")[1]
seen["truth_at_the_end"] = "worldgen.truth" in sys.modules
print(json.dumps(seen))
"""


def test_run_and_score_runs_then_scores_and_the_run_step_never_loads_the_truth(tmp_path):
    seen = python(RUN_AND_SCORE, str(Path(__file__).resolve().parent), str(tmp_path))
    assert seen == {"code": 0, "truth_after_the_run": False, "score_after_the_run": False, "truth_at_the_end": True,
                    "said": "wrote 1 reports, kept 0, for 1 run sets"}
    index = json.loads(tmp_path.joinpath("out", "index.json").read_text(encoding="utf-8"))
    entry, = index["runs"]
    assert entry["state"] == "completed"
    report = json.loads(tmp_path.joinpath("out", entry["run_id"], "report.json").read_text(encoding="utf-8"))
    assert report["run_id"] == entry["run_id"] and report["figures"]["overall"] and report["manifest"]["run_id"] == entry["run_id"]
    assert tmp_path.joinpath("out", "sets", entry["run_set"] + ".json").is_file()


def test_a_whole_run_opens_nothing_under_hidden_and_never_imports_the_truth(tmp_path):
    tmp_path.joinpath("hidden").mkdir()
    tmp_path.joinpath("hidden", "control.txt").write_text("control", encoding="utf-8")
    seen = python(HIDDEN_PROBE, str(Path(__file__).resolve().parent), str(tmp_path))
    assert seen["state"] == "completed" and seen["total"] == 1845
    assert seen["before"] == [] and seen["truth"] is False
    assert len(seen["after"]) == 1 and seen["after"][0].endswith("hidden/control.txt")
