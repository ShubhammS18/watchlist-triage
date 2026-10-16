"""Shared fixtures of the T06 tests. Every run here writes to a temporary folder outside the repository."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import fake_model
from harness import run as harness_run

FIXTURES = Path(__file__).resolve().parent.joinpath("fixtures")
CLEAN = {"commit": "c" * 40, "dirty": False}  # what a report says when the scoring code was one clean commit
SENTINEL = ("T06_SENTINEL_VARIABLE", "sentinel-value-4f1c9a7e-not-a-secret")


@pytest.fixture(scope="session", autouse=True)
def registered():
    """The fake provider and the in-process agent, for the whole test session, plus one environment variable
    whose value no output may contain."""
    with pytest.MonkeyPatch.context() as patch:
        fake_model.register(patch)
        patch.setenv(*SENTINEL)
        yield


@pytest.fixture(scope="session", autouse=True)
def repository_untouched():
    """No test may write inside the repository: `git status` is the same after the session as before it, and
    there is no runs/ folder."""
    def status():  # None where this is no git repository, as in the copies the mutation proofs run in
        done = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=harness_run.records.REPO,
                              capture_output=True, text=True)
        return done.stdout if done.returncode == 0 else None
    before = status()
    yield
    assert status() == before
    assert before is None or not harness_run.records.REPO.joinpath("runs").exists()


SHARED = {}  # every shared output folder and what it held when it was made


def tree_digest(folder):
    digest = hashlib.sha256()
    for path in sorted(Path(folder).rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(folder).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def share(folder):
    """Mark an output folder as shared between tests. Shared folders are read-only: `shared_untouched` fails
    the session if any of them changed. A test that changes data works on its own copy."""
    SHARED[Path(folder)] = tree_digest(folder)
    return Path(folder)


@pytest.fixture(scope="session", autouse=True)
def shared_untouched():
    yield
    changed = [str(folder) for folder, digest in SHARED.items() if tree_digest(folder) != digest]
    assert not changed, f"a test changed a shared, read-only folder: {changed}"


def write_config(folder, **changes):
    """A run configuration in `folder`, built from the fixture one with absolute paths. Returns its path."""
    config = json.loads(FIXTURES.joinpath("run.json").read_text(encoding="utf-8"))
    config.update(agent="inprocess", world=str(harness_run.records.REPO.joinpath("data", "world")),
                  model_config=str(FIXTURES.joinpath("model_fake.json")),
                  price_table=str(FIXTURES.joinpath("prices.json")),
                  modelled_time=str(FIXTURES.joinpath("modelled_time.json")))
    config.update(changes)
    path = Path(folder).joinpath("run.json")
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


@pytest.fixture(scope="session")
def full_run(tmp_path_factory):
    """One whole run, in-process, with the fake model: (output folder, manifest, the lines of items.jsonl)."""
    folder = tmp_path_factory.mktemp("full")
    out = folder.joinpath("out")
    manifest = harness_run.run(write_config(folder), out)
    assert manifest["state"] == "completed", manifest["aborted"]
    text = out.joinpath(manifest["run_id"], "items.jsonl").read_text(encoding="utf-8")
    return share(out), manifest, [json.loads(line) for line in text.split("\n") if line]


def set_validity(out, run_id, dirty=False, marked=False):
    """Rewrite a run in a temporary output folder so that it is, or is not, a valid run, consistently: the manifest
    and the index entry agree, and an infrastructure-invalid mark follows from the item rows, as the score step
    checks. The tests need this because the real tree is dirty for as long as T06 is uncommitted. For marked=True,
    enough rows become timeouts for the share of transient failures to pass the threshold; the items file is
    rehashed."""
    run_dir = Path(out).joinpath(run_id)
    manifest = json.loads(run_dir.joinpath("manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in run_dir.joinpath("items.jsonl").read_text(encoding="utf-8").split("\n") if line]
    mark = manifest["infra_invalid"]
    transient = lambda: sum(1 for row in rows if row["result"]["failure_kind"] in harness_run.TRANSIENT)
    for row in rows:  # only for marked=True: turn plain results into timeouts until the mark follows
        if harness_run.infra_invalid(transient(), len(rows), mark["threshold"]) == marked:
            break
        if marked and row["result"]["failure_kind"] is None:
            row["result"].update(recommendation="ESCALATE", cited_ids=[], system_failure=True, citation_invalid=False,
                                 failure_kind="timeout", reason="System failure: timeout")
    assert harness_run.infra_invalid(transient(), len(rows), mark["threshold"]) == marked
    text = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows)
    run_dir.joinpath("items.jsonl").write_text(text, encoding="utf-8")
    manifest["outputs"]["sha256"] = harness_run.records.sha256(text.encode("utf-8"))
    manifest["git"]["dirty"], mark["marked"], mark["transient_items"] = dirty, marked, transient()
    run_dir.joinpath("manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    index = json.loads(Path(out).joinpath("index.json").read_text(encoding="utf-8"))
    for entry in index["runs"]:
        if entry["run_id"] == run_id:
            entry["dirty"], entry["infra_invalid"] = dirty, marked
    Path(out).joinpath("index.json").write_text(json.dumps(index), encoding="utf-8")


@pytest.fixture(scope="session")
def three_runs(tmp_path_factory):
    """Three whole runs of one run set, in-process, all made valid, not yet scored: (output folder, run ids)."""
    folder = tmp_path_factory.mktemp("three")
    out, config = folder.joinpath("out"), write_config(folder)
    ids = [harness_run.run(config, out)["run_id"] for _ in range(3)]
    for run_id in ids:
        set_validity(out, run_id)
    return share(out), ids


@pytest.fixture(scope="session")
def scored(three_runs, tmp_path_factory):
    """A copy of `three_runs`, scored: (output folder, run ids, what score_all returned)."""
    from harness import score
    out = tmp_path_factory.mktemp("scored").joinpath("out")
    shutil.copytree(three_runs[0], out)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(score, "scoring_state", lambda out: dict(CLEAN))
        done = score.score_all(out, harness_run.records.REPO.joinpath("data", "world"))
    return share(out), three_runs[1], done


@pytest.fixture
def clean_scoring(monkeypatch):
    """Score as if the scoring code were one clean commit. The real tree is dirty while T06 is uncommitted."""
    from harness import score
    monkeypatch.setattr(score, "scoring_state", lambda out: dict(CLEAN))
