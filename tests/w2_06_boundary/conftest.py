"""Fixtures of the W2-06 boundary checks: T06's fake model registered for the session, a check that no test writes inside
the repository, and one whole evaluation run (`python -m harness run-and-score`) with the fake model, traced: every
file it opens for writing, creates, moves or removes, and every program it starts, as Python's audit hooks report them.
No test calls a real model."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1].joinpath("t06_harness")))
import fake_model  # noqa: E402  (T06's fake model and in-process agent)

from harness import run as harness_run  # noqa: E402
from harness.__main__ import main  # noqa: E402

REPO = harness_run.records.REPO
WORLD = REPO.joinpath("data", "world")
T06_FIXTURES = REPO.joinpath("tests", "t06_harness", "fixtures")
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
_TRACE = []  # (event, path or program); recorded only while _ON holds True
_ON = [False]


def _path(value):
    if isinstance(value, bytes):
        value = os.fsdecode(value)
    return str(Path(os.getcwd(), value).resolve()) if isinstance(value, (str, os.PathLike)) else None


def _hook(event, args):
    """Python's audit events for writing files and starting programs. An audit hook cannot be removed once added, so
    it records nothing unless a traced run is under way."""
    if not _ON[0]:
        return
    if event == "open":
        path, mode, flags = args
        if (isinstance(mode, str) and set(mode) & set("wax+")) or (mode is None and isinstance(flags, int) and flags & WRITE_FLAGS):
            _TRACE.append(("write", _path(path)))
    elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.truncate", "shutil.rmtree", "shutil.copyfile"):
        _TRACE.append((event, _path(args[0] if event != "shutil.copyfile" else args[1])))
    elif event in ("os.rename", "os.replace", "os.link", "os.symlink"):
        _TRACE.append((event, _path(args[1])))
    elif event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork"):
        program = args[1] if event == "subprocess.Popen" else args[0] if args else ""
        _TRACE.append(("launch", list(program) if isinstance(program, (list, tuple)) else program))


sys.addaudithook(_hook)


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


@pytest.fixture(scope="session", autouse=True)
def registered():
    with pytest.MonkeyPatch.context() as patch:
        fake_model.register(patch)
        yield


@pytest.fixture(scope="session", autouse=True)
def repository_untouched():
    """No test writes inside the repository."""
    status = lambda: subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=REPO,
                                    capture_output=True, text=True).stdout
    before = status()
    yield
    assert status() == before


@pytest.fixture(scope="session")
def evaluation(tmp_path_factory):
    """One whole evaluation run, traced: {out, run_dir, manifest, trace}. Read-only for the tests."""
    folder = tmp_path_factory.mktemp("evaluation")
    config, out = write_config(folder), folder.joinpath("out")
    _TRACE.clear()
    _ON[0] = True
    try:
        code = main(["run-and-score", str(config), str(out)])
    finally:
        _ON[0] = False
    trace = list(_TRACE)
    assert code == 0
    index = json.loads(out.joinpath("index.json").read_text(encoding="utf-8"))
    run_id, = (run["run_id"] for run in index["runs"])
    run_dir = out.joinpath(run_id)
    manifest = json.loads(run_dir.joinpath("manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "completed"
    return {"out": out, "run_dir": run_dir, "manifest": manifest, "trace": trace}
