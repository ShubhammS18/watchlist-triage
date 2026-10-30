"""Shared fixtures of the W2-03 tests: T06's fake model and in-process agent, and helpers for runs made in temporary
folders, never in the repository. No test calls a real model."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1].joinpath("t06_harness")))
import fake_model  # noqa: E402

from harness import run as harness_run  # noqa: E402

REPO = harness_run.records.REPO
WORLD = REPO.joinpath("data", "world")
T06_FIXTURES = REPO.joinpath("tests", "t06_harness", "fixtures")
SOURCED = {"price_table": REPO.joinpath("config", "prices.json"),
           "modelled_time": REPO.joinpath("config", "modelled_time.json")}
FIXTURE = {"price_table": T06_FIXTURES.joinpath("prices.json"),
           "modelled_time": T06_FIXTURES.joinpath("modelled_time.json")}


@pytest.fixture(scope="session", autouse=True)
def registered():
    with pytest.MonkeyPatch.context() as patch:
        fake_model.register(patch)
        yield


def write_config(folder, model=None, **changes):
    """A run configuration in `folder`: the in-process baseline agent, the fake model and the T06 fixture tables,
    with absolute paths, changed by `changes`. `model` changes the model configuration. Returns its path."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    model_config = {**json.loads(T06_FIXTURES.joinpath("model_fake.json").read_text(encoding="utf-8")), **(model or {})}
    folder.joinpath("model.json").write_text(json.dumps(model_config), encoding="utf-8")
    config = {"agent": "inprocess", "world": str(WORLD), "model_config": str(folder.joinpath("model.json")),
              "workers": 1, "pacer_per_minute": None, "infra_invalid_threshold": "0.05",
              "price_table": str(FIXTURE["price_table"]), "modelled_time": str(FIXTURE["modelled_time"])}
    config.update({key: str(value) if isinstance(value, Path) else value for key, value in changes.items()})
    folder.joinpath("run.json").write_text(json.dumps(config), encoding="utf-8")
    return folder.joinpath("run.json")


def read_lines(out, run_id):
    text = Path(out).joinpath(run_id, "items.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.split("\n") if line]
