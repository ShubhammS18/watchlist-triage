"""Shared by the W2-08 tests. No test calls a model: every run is made in this process by a test-only candidate agent
that calls none, answers from a world's truth, and is told per run how to misbehave. Runs are made at a test-only
freeze commit in a shared clone of the repository, never in the repository; the clone only reads it.

The harness reads the commit and the committed price table from `records.REPO`, so while a run is made or a release
is checked, `records.REPO` is the clone (`at`)."""
import contextlib
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from harness import agents, audit, release
from harness import manifest as records
from harness import run as harness_run
from worldgen.truth import load_truth

REPO = records.REPO
SOURCED = {"price_table": REPO.joinpath("config", "prices.json"),
           "modelled_time": REPO.joinpath("config", "modelled_time.json")}
STUB = {"provider": "stub", "model": "stub-1", "temperature": 0, "max_tokens": 512, "timeout_s": 30}
# how the candidate behaves in the run being made; `make_runs` sets it per run
BEHAVIOUR = {}


def candidate(items, model, settings, item_id):
    """Test-only: the correct action from BEHAVIOUR's truth, citing supporting evidence on a close, unless told to
    close the first true match it sees, escalate clear false positives, fail some of them as timeouts, make one failed
    model call with no retry, or abort the run after some items."""
    b = BEHAVIOUR
    b["calls"] += 1
    if b.get("abort_after") is not None and b["calls"] > b["abort_after"] and (b["closed"] or not b.get("close_true_match")):
        raise RuntimeError("test abort")
    alert = item_id.split("/")[0]
    facts = b["truth"][alert]
    plain = facts["label"] == "CLEAR_FALSE_POSITIVE" and facts["twin"] is None and facts["twin_of"] is None
    if b.get("failed_call") and b["calls"] == 1:
        try:
            model(None)  # the stub refuses it: a call that left no token counts, with no retry
        except Exception:
            pass
    if b.get("timeouts") and plain and int(hashlib.sha256(item_id.encode()).hexdigest(), 16) % 4 == 0:
        result, sink = agents._answer("ESCALATE", items, item_id)
        result.update(system_failure=True, failure_kind="timeout", cited_ids=[], reason="Test timeout.")
        result["log"] = sink[0] = {**result["log"], "kind": "timeout"}
        return result, sink
    action = facts["correct_action"]
    if b.get("close_true_match") and facts["label"] == "TRUE_MATCH" and not b["closed"] and facts["twin_of"] is None:
        action, b["closed"] = "CLOSE", True
        result, sink = agents._answer(action, items, item_id)
    elif b.get("escalate_clear") and plain:
        result, sink = agents._answer("ESCALATE", items, item_id)
    else:
        result, sink = agents._answer(action, items, item_id)
        if action == "CLOSE":
            result["cited_ids"] = sorted(set(facts["evidence_key"]) & {item["id"] for item in items})
            assert result["cited_ids"], f"{item_id}: no supporting evidence in its bundle"
    result["reason"] = "Test candidate."
    return result, sink


def register(patch):
    patch.setitem(harness_run.AGENTS, "candidate", candidate)
    patch.setattr(harness_run, "MODEL_FREE", (*harness_run.MODEL_FREE, "candidate"))


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


@contextlib.contextmanager
def at(clone):
    """`records.REPO` is the clone while the block runs."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(records, "REPO", Path(clone))
        yield


def new_clone(folder):
    """A shared clone of the repository's HEAD with a test freeze commit on top: (clone, freeze commit)."""
    folder = Path(folder)
    subprocess.run(["git", "clone", "-q", "--shared", str(REPO), str(folder)], check=True)
    for key, value in (("user.name", "Test"), ("user.email", "test@example.invalid"), ("commit.gpgsign", "false")):
        git(folder, "config", key, value)
    git(folder, "commit", "-q", "--allow-empty", "-m", "Freeze (test)")
    git(folder, "tag", "release-1-freeze")
    return folder, git(folder, "rev-parse", "HEAD").strip()


def reset(clone, freeze):
    git(clone, "checkout", "-q", "--detach", freeze)
    git(clone, "reset", "-q", "--hard", freeze)
    git(clone, "clean", "-qfdx")


def make_runs(folder, world, behaviours, truth, workers=1):
    """Runs of the candidate on `world` into `folder`/out, one per behaviour, at the clone's HEAD (records.REPO must be
    the clone). Returns (out folder, run IDs)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    folder.joinpath("model.json").write_text(json.dumps(STUB), encoding="utf-8")
    config = {"agent": "candidate", "world": str(world), "model_config": str(folder.joinpath("model.json")),
              "workers": workers, "pacer_per_minute": None, "infra_invalid_threshold": "0.05",
              "price_table": str(SOURCED["price_table"]), "modelled_time": str(SOURCED["modelled_time"])}
    folder.joinpath("run.json").write_text(json.dumps(config), encoding="utf-8")
    out, ids = folder.joinpath("out"), []
    for behaviour in behaviours:
        BEHAVIOUR.clear()
        BEHAVIOUR.update(truth=truth, calls=0, closed=False, **behaviour)
        ids.append(harness_run.run(folder.joinpath("run.json"), out)["run_id"])
    return out, ids


def assemble(pool, names, folder, also=()):
    """A run-output folder holding the named runs of `pool`, in that order, then the runs `also` names as (pool, name)
    pairs, with an index of just those runs. Returns (out folder, {name: run id})."""
    out = Path(folder).joinpath("out")
    out.mkdir(parents=True)
    picked = [(pool, name) for name in names] + list(also)
    chosen = {name: one[name] for one, name in picked}  # makes any run not made yet
    entries = []
    for one, name in picked:
        shutil.copytree(one["out"].joinpath(one[name]), out.joinpath(one[name]))
        entries += [entry for entry in records.read_index(one["out"])["runs"] if entry["run_id"] == one[name]]
    records.write_json(out.joinpath("index.json"), {"runs": entries, "sets": {}})
    return out, chosen


def read_records(run_dir):
    return [json.loads(line) for line in Path(run_dir, audit.LOG).read_bytes().split(b"\n") if line]


def write_records(run_dir, found, checkpoint=True):
    """Write these records as the run's log, chained again so every hash holds, and its checkpoint to match."""
    head, data = audit.START, b""
    for seq, record in enumerate(found):
        record = {**record, "seq": seq, "prev": head}
        record["hash"] = audit.record_hash(record)
        head, data = record["hash"], data + audit.canonical(record) + b"\n"
    Path(run_dir, audit.LOG).write_bytes(data)
    if checkpoint:
        Path(run_dir, audit.CHECKPOINT).write_bytes(audit.canonical(audit.checkpoint(Path(run_dir).name, len(found), head)) + b"\n")


def kill(out, run_id):
    """Make a finished run look like one whose process was killed: no manifest, no checkpoint, no end record, and an
    index entry that still says started."""
    run_dir = Path(out, run_id)
    found = [record for record in read_records(run_dir) if record["event"] != "run_ended"]
    for name in ("manifest.json", audit.CHECKPOINT, "items.jsonl", "report.json"):
        run_dir.joinpath(name).unlink(missing_ok=True)
    write_records(run_dir, found, checkpoint=False)
    index = records.read_index(out)
    for entry in index["runs"]:
        if entry["run_id"] == run_id:
            entry.update(state="started", infra_invalid=None, cause=None, calls=None, cost=None)
    records.write_json(Path(out, "index.json"), index)


def set_dirty(out, run_id):
    """Mark a run as made from a dirty tree, in its manifest and its index entry alike."""
    path = Path(out, run_id, "manifest.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["git"]["dirty"] = True
    path.write_text(json.dumps(manifest), encoding="utf-8")
    index = records.read_index(out)
    for entry in index["runs"]:
        if entry["run_id"] == run_id:
            entry["dirty"] = True
    records.write_json(Path(out, "index.json"), index)


def sums(folder):
    folder = Path(folder)
    lines = [f"{records.sha256(p.read_bytes())}  {p.relative_to(folder).as_posix()}"
             for p in sorted(folder.rglob("*")) if p.is_file() and p.name != "SHA256SUMS"]
    folder.joinpath("SHA256SUMS").write_text("".join(line + "\n" for line in lines), encoding="utf-8")


def publish(clone, freeze, outs, generation=None, skip_checkpoints=(), before_commit=None):
    """Reset the clone to the freeze commit, then commit what the release commits: each world's run output copied in
    with its SHA256SUMS, each run's checkpoint under audit/checkpoints (except `skip_checkpoints`) and the generation
    record. `before_commit(clone)` may change anything first. The commit is the publish commit: HEAD."""
    reset(clone, freeze)
    for world, out in outs.items():
        target = Path(clone, "release", world)
        shutil.copytree(out, target)
        for run_dir in sorted(p for p in target.iterdir() if p.is_dir() and p.name != "sets"):
            point = run_dir.joinpath(audit.CHECKPOINT)
            if point.is_file() and run_dir.name not in skip_checkpoints:
                Path(clone, "audit", "checkpoints").mkdir(parents=True, exist_ok=True)
                shutil.copyfile(point, Path(clone, "audit", "checkpoints", f"{run_dir.name}.json"))
        sums(target)
    if generation is not None:
        Path(clone, "release").mkdir(exist_ok=True)
        Path(clone, release.GENERATION).write_text(json.dumps(generation, indent=2, sort_keys=True) + "\n",
                                                   encoding="utf-8")
    if before_commit is not None:
        before_commit(Path(clone))
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "--allow-empty", "-m", "Publish (test)")


def fresh_truth(world):
    return load_truth(Path(world, "hidden"))
