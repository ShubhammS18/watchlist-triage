"""T06 stage 1: the manifest, the dirty flag, the run-set index, the framing code hash and what must never be
written (NFR-3, DEC-T06-MANIFEST, DEC-T06-FRAMING-HASH, DEC-T06-INFRA-INVALID, DEC-T06-NO-ENV)."""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import fake_model
from baseline_agent import prompt
from conftest import FIXTURES, SENTINEL, write_config
from harness import manifest as records
from harness import run as harness_run

REPO = Path(__file__).resolve().parents[2]
WORLD_MANIFEST = json.loads(REPO.joinpath("data", "world", "MANIFEST.json").read_text(encoding="utf-8"))
MANIFEST_KEYS = {
    "run_id", "run_set", "run_set_inputs", "state", "aborted", "rerun_cause", "agent", "world", "model", "prompt",
    "decoding", "retry_policy", "review_policies", "modelled_time", "price_table", "outputs", "git", "config_sha256",
    "cost", "timing",
    "framing_code_sha256", "python_version", "workers", "pacer_per_minute", "infra_invalid", "started_at", "ended_at",
    "items", "calls"}
RUN_SET_INPUTS = {"agent", "commit", "world_hash", "prompt_hash", "model_config", "workers", "pacer_per_minute",
                  "infra_invalid_threshold", "price_table", "modelled_time"}


def git(folder, *args):
    return subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args],
                          cwd=folder, capture_output=True, text=True, check=True).stdout


# ---- the manifest

def test_the_manifest_holds_every_nfr3_field_and_every_added_field(full_run):
    out, manifest, _ = full_run
    assert set(manifest) == MANIFEST_KEYS and manifest == json.loads(
        out.joinpath(manifest["run_id"], "manifest.json").read_text(encoding="utf-8"))
    # the NFR-3 list
    assert manifest["world"] == {"world_hash": WORLD_MANIFEST["world_hash"], "generator_version": "1", "rubric_version": "1.2"}
    assert manifest["model"]["requested"] == "fake-1" and manifest["model"]["provider"] == "fake"
    assert manifest["model"]["used"] is True
    assert set(manifest["model"]["reported"]) == {"fake-1"}
    assert manifest["prompt"] == {"text": prompt.SYSTEM + "\n" + prompt.USER, "sha256": prompt.PROMPT_SHA256}
    assert hashlib.sha256(manifest["prompt"]["text"].encode("utf-8")).hexdigest() == manifest["prompt"]["sha256"]
    assert manifest["decoding"] == {"temperature": 0, "max_tokens": 512}
    assert manifest["retry_policy"] == {"retries": 2, "timeout_s": 30, "retried_errors": ["ModelTimeout", "ProviderError"],
                                        "backoff": None}
    assert manifest["review_policies"] == ["STRICT_FOUR_EYES", "none"]
    fixture_time = json.loads(FIXTURES.joinpath("modelled_time.json").read_text(encoding="utf-8"))
    assert manifest["modelled_time"] == {"sha256": records.content_hash(fixture_time), "parameters": fixture_time}
    # what DEC-T06-MANIFEST adds
    fixture_prices = json.loads(FIXTURES.joinpath("prices.json").read_text(encoding="utf-8"))
    assert manifest["price_table"] == {"sha256": records.content_hash(fixture_prices), "table": fixture_prices}
    assert manifest["git"]["commit"] == git(REPO, "rev-parse", "HEAD").strip() and isinstance(manifest["git"]["dirty"], bool)
    assert manifest["python_version"] == platform.python_version()
    assert manifest["workers"] == 1 and manifest["pacer_per_minute"] is None and manifest["agent"] == "inprocess"
    assert manifest["state"] == "completed" and manifest["aborted"] is None and manifest["rerun_cause"] is None
    assert manifest["started_at"] <= manifest["ended_at"] and len(manifest["framing_code_sha256"]) == 64
    assert set(manifest["run_set_inputs"]) == RUN_SET_INPUTS


def test_the_items_file_hash_is_in_the_manifest(full_run):
    out, manifest, _ = full_run
    data = out.joinpath(manifest["run_id"], manifest["outputs"]["items_file"]).read_bytes()
    assert manifest["outputs"] == {"items_file": "items.jsonl", "sha256": hashlib.sha256(data).hexdigest()}
    assert data.endswith(b"\n") and b"\r" not in data


def test_no_environment_variable_reaches_any_output(full_run):
    out, _, _ = full_run
    assert os.environ[SENTINEL[0]] == SENTINEL[1]  # it was set while the run was made
    files = [path for path in out.rglob("*") if path.is_file()]
    assert len(files) == 5  # index.json, manifest.json, items.jsonl, audit.jsonl, checkpoint.json (W2-05)
    for path in files:
        data = path.read_bytes()
        assert SENTINEL[1].encode() not in data and SENTINEL[0].encode() not in data
        for name in ("HOME", "USER", "PATH"):
            value = os.environ.get(name, "")
            assert len(value) < 4 or path.name == "items.jsonl" or value.encode() not in data, name


def test_a_rerun_cause_is_recorded(tmp_path):
    manifest = harness_run.run(write_config(tmp_path), tmp_path.joinpath("out"), rerun_cause="the first attempt was aborted")
    assert manifest["rerun_cause"] == "the first attempt was aborted"
    entry, = json.loads(tmp_path.joinpath("out", "index.json").read_text(encoding="utf-8"))["runs"]
    assert entry["rerun_cause"] == "the first attempt was aborted"


# ---- the infrastructure-invalid mark

def transient_items():
    """Counted from the fake's own table: three framings of every bundle scripted to time out or fail."""
    from worldgen.harness_twins import load_twins
    from worldgen.loader import load_alerts
    return 3 * sum(fake_model.outcome_of([item["id"] for item in alert["evidence"]]) in ("timeout", "provider_error")
                   for alert in load_alerts() + load_twins())


@pytest.mark.parametrize("transient, total, threshold, marked", [
    (1, 20, "0.05", False),        # exactly on the threshold: not marked
    (1, 20, "0.050", False),
    (1, 20, "0.0499999999999999999999999999", True),
    (1, 20, "0.0500000000000000000000000001", False),
    (2, 20, "0.05", True),
    (0, 20, "0", False),           # no transient failure never marks a run, even at threshold 0
    (1, 1845, "0", True),
    (3, 30, "0.1", False),         # 0.1 is not exact as a float; 3/30 == 0.1 exactly here
    (1, 3, "0.3333333333333333", True),   # one third is above any finite decimal written with threes
    (20, 20, "1", False),
])
def test_the_mark_is_strictly_above_the_threshold_in_exact_arithmetic(transient, total, threshold, marked):
    assert harness_run.infra_invalid(transient, total, threshold) is marked


def test_the_marking_function_uses_no_float():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(harness_run.infra_invalid))
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id == "float"]
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, float)]
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Div)]  # no "/" on numbers: Fraction only
    assert 3 * 0.1 != 0.3 and harness_run.infra_invalid(3, 10, "0.3") is False  # where floats would get it wrong


def test_a_run_below_the_threshold_is_not_marked(full_run):
    _, manifest, _ = full_run
    count = transient_items()
    assert 0 < count / 1845 < 0.05  # the fixture threshold is above this run's share
    assert manifest["infra_invalid"]["transient_items"] == count and manifest["infra_invalid"]["marked"] is False
    assert manifest["infra_invalid"]["threshold"] == "0.05"
    assert abs(float(manifest["infra_invalid"]["transient_share"]) - count / 1845) < 1e-12


def test_a_run_strictly_above_the_threshold_is_marked_and_still_written(tmp_path):
    assert transient_items() / 1845 > 0.03
    manifest = harness_run.run(write_config(tmp_path, infra_invalid_threshold="0.03"), tmp_path.joinpath("out"))
    assert manifest["infra_invalid"]["marked"] is True and manifest["state"] == "completed"
    assert manifest["outputs"] is not None and manifest["items"]["total"] == 1845
    entry, = json.loads(tmp_path.joinpath("out", "index.json").read_text(encoding="utf-8"))["runs"]
    assert entry["infra_invalid"] is True and entry["state"] == "completed"


def test_model_caused_failures_never_mark_a_run(tmp_path):
    """The T04 stub's fixed reply is not JSON, so every item is malformed_output: all failures, none transient."""
    stub = str(REPO.joinpath("model_interface", "config.json"))
    manifest = harness_run.run(write_config(tmp_path, model_config=stub, infra_invalid_threshold="0"),
                               tmp_path.joinpath("out"))
    assert manifest["state"] == "completed" and manifest["model"]["provider"] == "stub"
    assert manifest["infra_invalid"] == {"threshold": "0", "transient_items": 0, "transient_share": "0", "marked": False}
    assert manifest["calls"]["without_token_counts"] == manifest["calls"]["attempts"] == 1845


# ---- the dirty flag

def test_the_dirty_flag(tmp_path):
    repo, out = tmp_path.joinpath("repo"), tmp_path.joinpath("repo", "runs")
    repo.mkdir()
    git(repo, "init", "-q")
    repo.joinpath("tracked.txt").write_text("one\n", encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-q", "-m", "first")
    commit = git(repo, "rev-parse", "HEAD").strip()
    assert records.git_state(repo, out) == (commit, False)
    out.joinpath("some-run").mkdir(parents=True)
    out.joinpath("some-run", "items.jsonl").write_text("{}\n", encoding="utf-8")
    assert records.git_state(repo, out) == (commit, False)  # untracked files inside the output folder do not count
    assert records.git_state(repo, tmp_path.joinpath("elsewhere")) == (commit, True)  # the same files do, from outside
    repo.joinpath("stray.txt").write_text("x", encoding="utf-8")
    assert records.git_state(repo, out) == (commit, True)  # an untracked file outside it
    repo.joinpath("stray.txt").unlink()
    repo.joinpath("tracked.txt").write_text("two\n", encoding="utf-8")
    assert records.git_state(repo, out) == (commit, True)  # a modified tracked file
    git(repo, "add", "tracked.txt")
    assert records.git_state(repo, out) == (commit, True)  # staged counts too
    git(repo, "commit", "-q", "-m", "second")
    git(repo, "mv", "tracked.txt", "renamed.txt")
    assert records.git_state(repo, out)[1] is True  # a rename
    assert records.git_state(tmp_path, out) == (None, True)  # not a repository: no commit, and dirty


# ---- the run-set index

def test_the_index_lists_every_run_and_groups_them_by_their_inputs(tmp_path):
    out = tmp_path.joinpath("out")
    first = harness_run.run(write_config(tmp_path), out)
    second = harness_run.run(write_config(tmp_path), out)
    other = harness_run.run(write_config(tmp_path, infra_invalid_threshold="0.5"), out)
    model = tmp_path.joinpath("model.json")
    model.write_text(json.dumps({**json.loads(FIXTURES.joinpath("model_fake.json").read_text()), "max_tokens": 256}))
    another = harness_run.run(write_config(tmp_path, model_config=str(model)), out)
    runs = json.loads(out.joinpath("index.json").read_text(encoding="utf-8"))["runs"]
    assert [run["run_id"] for run in runs] == [first["run_id"], second["run_id"], other["run_id"], another["run_id"]]
    assert first["run_set"] == second["run_set"] and first["run_id"] != second["run_id"]
    assert len({first["run_set"], other["run_set"], another["run_set"]}) == 3
    assert first["run_set_inputs"] == second["run_set_inputs"]
    assert {key for key in RUN_SET_INPUTS if first["run_set_inputs"][key] != other["run_set_inputs"][key]} == {
        "infra_invalid_threshold"}
    assert {key for key in RUN_SET_INPUTS if first["run_set_inputs"][key] != another["run_set_inputs"][key]} == {
        "model_config"}
    for run, manifest in zip(runs, (first, second, other, another)):
        assert run["state"] == "completed" and run["run_set"] == manifest["run_set"] and run["calls"] == manifest["calls"]
        assert run["dirty"] == manifest["git"]["dirty"] and run["run_id"].endswith(manifest["run_set"][:8])
        assert out.joinpath(run["run_id"], "manifest.json").is_file()


def test_the_agent_name_is_a_run_set_input(tmp_path, monkeypatch, full_run, three_runs):
    monkeypatch.setitem(harness_run.AGENTS, "another", fake_model.inprocess)
    other = harness_run.run(write_config(tmp_path, agent="another"), tmp_path.joinpath("out"))
    # a run of the same configuration made elsewhere: one of the three shared runs, read and not made again
    same = json.loads(three_runs[0].joinpath(three_runs[1][0], "manifest.json").read_text(encoding="utf-8"))
    first = full_run[1]
    assert other["run_set"] != first["run_set"] == same["run_set"]
    assert {key for key in RUN_SET_INPUTS if other["run_set_inputs"][key] != first["run_set_inputs"][key]} == {"agent"}
    assert first["run_set_inputs"]["agent"] == "inprocess" and len(RUN_SET_INPUTS) == 10


def test_the_run_set_id_is_the_hash_of_the_ten_inputs_and_ignores_file_spacing(tmp_path, full_run):
    _, manifest, _ = full_run
    canonical = json.dumps(manifest["run_set_inputs"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert manifest["run_set"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    spaced = tmp_path.joinpath("prices.json")
    spaced.write_text(json.dumps(json.loads(FIXTURES.joinpath("prices.json").read_text()), indent=8, sort_keys=True))
    config = harness_run.load_config(write_config(tmp_path, price_table=str(spaced)))
    assert records.content_hash(config["price_table"]) == manifest["run_set_inputs"]["price_table"]


# ---- the framing code hash

FRAMING_PROBE = """
import json, sys
from pathlib import Path
repo, read = Path.cwd(), set()
def hook(event, args):
    if event == "open" and isinstance(args[0], str):
        path = Path(args[0]).resolve()
        if path.is_relative_to(repo) and path.suffix not in (".py", ".pyc") and ".venv" not in path.parts:
            read.add(path.relative_to(repo).as_posix())
sys.addaudithook(hook)
import framings
modules = {Path(module.__file__).resolve() for module in list(sys.modules.values()) if getattr(module, "__file__", None)}
loaded = {path.relative_to(repo).as_posix() for path in modules if path.is_relative_to(repo) and ".venv" not in path.parts}
print(json.dumps(sorted(loaded | read)))
"""


def test_the_framing_file_list_is_exactly_what_importing_framings_loads():
    done = subprocess.run([sys.executable, "-B", "-c", FRAMING_PROBE], cwd=REPO, capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": str(REPO)})
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == sorted(records.FRAMING_FILES)


@pytest.mark.parametrize("name", records.FRAMING_FILES)
def test_the_framing_hash_changes_when_any_listed_file_changes(tmp_path, name, full_run):
    for listed in records.FRAMING_FILES:
        tmp_path.joinpath(listed).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO.joinpath(listed), tmp_path.joinpath(listed))
    assert records.framing_hash(tmp_path) == records.framing_hash() == full_run[1]["framing_code_sha256"]
    with tmp_path.joinpath(name).open("ab") as file:
        file.write(b"\n")
    assert records.framing_hash(tmp_path) != records.framing_hash()
