"""Shared fixtures of the W2-01 tests: run sets made in temporary folders, never in the repository.

A run set here is three whole runs on the frozen world by an agent that calls no model: a reference agent, or the
test-only oracle, which answers from the truth. The runs are then marked clean, as T06's tests do, because the
working tree may be dirty while the tests run.
"""
import json
import shutil
from pathlib import Path

import pytest

from harness import agents, release_check
from harness import run as harness_run
from worldgen.truth import load_truth

REPO = harness_run.records.REPO
WORLD = REPO.joinpath("data", "world")
SOURCED = {"price_table": REPO.joinpath("config", "prices.json"),
           "modelled_time": REPO.joinpath("config", "modelled_time.json")}
FIXTURES = {"price_table": REPO.joinpath("tests", "t06_harness", "fixtures", "prices.json"),
            "modelled_time": REPO.joinpath("tests", "t06_harness", "fixtures", "modelled_time.json")}
STUB = {"provider": "stub", "model": "stub-1", "temperature": 0, "max_tokens": 512, "timeout_s": 30}
TRUTH = load_truth()


def oracle(items, model, settings, item_id):
    """Test-only: the correct action from the truth, citing the supporting evidence on a close."""
    facts = TRUTH[item_id.split("/")[0]]
    result, sink = agents._answer(facts["correct_action"], items, item_id)
    if facts["correct_action"] == "CLOSE":
        result["cited_ids"] = sorted(set(facts["evidence_key"]) & {item["id"] for item in items})
        assert result["cited_ids"], f"{item_id}: no supporting evidence in its bundle"
    result["reason"] = "Test oracle."
    return result, sink


@pytest.fixture(scope="session", autouse=True)
def registered():
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(harness_run.AGENTS, "oracle", oracle)
        patch.setattr(harness_run, "MODEL_FREE", (*harness_run.MODEL_FREE, "oracle"))
        yield


def rewrite(out, run_id, change=None, dirty=False, rehash=True):
    """Change a run in a temporary output folder consistently: `change(rows)` edits its item rows in place, the
    items file is rewritten and, with `rehash`, its hash and item counts in the manifest follow; the run is marked dirty or clean
    in the manifest and the index alike."""
    run_dir = Path(out).joinpath(run_id)
    manifest = json.loads(run_dir.joinpath("manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in run_dir.joinpath("items.jsonl").read_text(encoding="utf-8").split("\n") if line]
    if change:
        change(rows)
    text = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows)
    run_dir.joinpath("items.jsonl").write_text(text, encoding="utf-8")
    if rehash:
        manifest["outputs"]["sha256"] = harness_run.records.sha256(text.encode("utf-8"))
        twins = sum(row["twin"] for row in rows)
        manifest["items"].update(total=len(rows), main=len(rows) - twins, twin=twins)
    manifest["git"]["dirty"] = dirty
    run_dir.joinpath("manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    index = json.loads(Path(out).joinpath("index.json").read_text(encoding="utf-8"))
    for entry in index["runs"]:
        if entry["run_id"] == run_id:
            entry["dirty"] = dirty
    Path(out).joinpath("index.json").write_text(json.dumps(index), encoding="utf-8")


def make_set(folder, agent, runs=3, **files):
    """`runs` clean runs of one run set by `agent`, with the sourced price and time files unless `files` names
    others. Returns (output folder, run set, run ids)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    folder.joinpath("model.json").write_text(json.dumps(STUB), encoding="utf-8")
    paths = {**SOURCED, **files}
    config = {"agent": agent, "world": str(WORLD), "model_config": str(folder.joinpath("model.json")), "workers": 1,
              "pacer_per_minute": None, "infra_invalid_threshold": "0.05",
              "price_table": str(paths["price_table"]), "modelled_time": str(paths["modelled_time"])}
    folder.joinpath("run.json").write_text(json.dumps(config), encoding="utf-8")
    out = folder.joinpath("out")
    made = [harness_run.run(folder.joinpath("run.json"), out) for _ in range(runs)]
    assert all(manifest["state"] == "completed" for manifest in made)
    for manifest in made:
        rewrite(out, manifest["run_id"], rehash=False)
    return out, made[0]["run_set"], [manifest["run_id"] for manifest in made]


def copy_set(made, folder):
    """A copy of a made run set to change: (output folder, run set, run ids)."""
    out, run_set, ids = made
    shutil.copytree(out, Path(folder).joinpath("out"))
    return Path(folder).joinpath("out"), run_set, ids


@pytest.fixture(scope="session")
def oracle_set(tmp_path_factory):
    """Three valid oracle runs and a fourth that is invalid (a dirty tree): (output folder, run set, run ids)."""
    out, run_set, ids = make_set(tmp_path_factory.mktemp("oracle"), "oracle", runs=4)
    rewrite(out, ids[3], dirty=True)
    return out, run_set, ids


@pytest.fixture(scope="session")
def oracle_result(oracle_set):
    return release_check.check(oracle_set[0], oracle_set[1])
