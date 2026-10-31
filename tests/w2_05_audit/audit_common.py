"""Shared by the W2-05 tests: the frozen world, a run configuration with T06's fake model, and a JSON-lines reader.
Runs are made in temporary folders, never in the repository. No test calls a real model."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1].joinpath("t06_harness")))
import fake_model  # noqa: E402,F401  (T06's fake model and in-process agent)

from harness import run as harness_run  # noqa: E402

REPO = harness_run.records.REPO
WORLD = REPO.joinpath("data", "world")
T06_FIXTURES = REPO.joinpath("tests", "t06_harness", "fixtures")


def write_config(folder, **changes):
    """A run configuration in `folder`: the in-process baseline agent, the fake model, the frozen world and the T06
    fixture tables, with absolute paths, changed by `changes`. Returns its path."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    config = {"agent": "inprocess", "world": str(WORLD), "model_config": str(T06_FIXTURES.joinpath("model_fake.json")),
              "workers": 1, "pacer_per_minute": None, "infra_invalid_threshold": "0.05",
              "price_table": str(T06_FIXTURES.joinpath("prices.json")),
              "modelled_time": str(T06_FIXTURES.joinpath("modelled_time.json")), **changes}
    folder.joinpath("run.json").write_text(json.dumps(config), encoding="utf-8")
    return folder.joinpath("run.json")


def lines_of(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").split("\n") if line]
