"""What a run leaves behind besides its items: hashes, the git state, the run-set ID and the run-set index
(NFR-3, DEC-T06-MANIFEST, DEC-T06-FRAMING-HASH, DEC-T06-FAULTS). Python standard library only.

Nothing here reads an environment variable (DEC-T06-NO-ENV).
"""
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Every file the framings package imports or reads, traced on 2026-10-12. A test fails if importing framings
# loads a repository file outside this list.
FRAMING_FILES = (
    "framings/__init__.py", "framings/names.py", "framings/order.py", "framings/recognise.py", "framings/wording.py",
    "worldgen/__init__.py", "worldgen/matcher.py", "worldgen/names/titles.txt", "worldgen/snippets.py",
    "worldgen/textutil.py")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def content_hash(value):
    """SHA-256 of a JSON value in one canonical form, so the spacing and key order of a file do not matter."""
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def framing_hash(repo=REPO):
    """SHA-256 over the bytes of FRAMING_FILES, in sorted path order."""
    digest = hashlib.sha256()
    for name in sorted(FRAMING_FILES):
        digest.update(Path(repo).joinpath(name).read_bytes())
    return digest.hexdigest()


def git_state(repo, out_dir):
    """(commit, dirty). The tree is dirty when a tracked file is modified or an untracked file lies outside
    `out_dir`. If git cannot answer, the commit is None and the tree counts as dirty."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout
    try:
        commit = git("rev-parse", "HEAD").strip()
        entries = git("status", "--porcelain", "--untracked-files=all", "-z").split("\0")
    except (OSError, subprocess.CalledProcessError):
        return None, True
    top, out = Path(repo).resolve(), Path(out_dir).resolve()
    dirty, skip = False, False
    for entry in entries:
        if skip or not entry:  # the second path of a rename or copy
            skip = False
            continue
        status, name = entry[:2], entry[3:]
        skip = status[0] in "RC"
        if status != "??" or not top.joinpath(name).resolve().is_relative_to(out):
            dirty = True
    return commit, dirty


def write_json(path, value):
    """Write `value` as JSON through a temporary file, so a reader never sees half a file."""
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def read_index(out_dir):
    """The run-set index of `out_dir`: every run ever started there, and which run sets were superseded."""
    path = Path(out_dir).joinpath("index.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"runs": [], "sets": {}}


def index_update(out_dir, entry):
    """Add `entry` to the run-set index of `out_dir`, or replace the entry with the same run_id."""
    index = read_index(out_dir)
    index["runs"] = [run for run in index["runs"] if run["run_id"] != entry["run_id"]] + [entry]
    write_json(Path(out_dir).joinpath("index.json"), index)


def supersede(out_dir, old, new, cause):
    """Record that run set `old` is superseded by run set `new`, for the written `cause`. This is a human action:
    nothing in the harness calls it. A superseded set takes no more runs and can never be a baseline."""
    if not isinstance(cause, str) or not cause.strip():
        raise ValueError("superseding a run set needs a written cause")
    index = read_index(out_dir)
    known = {run["run_set"] for run in index["runs"]}
    if old not in known or new not in known:
        raise ValueError("both run sets must have a run in the index; give the full run-set IDs")
    if old == new:
        raise ValueError("a run set cannot supersede itself")
    if old in index["sets"] or new in index["sets"]:
        raise ValueError("a superseded run set cannot be superseded again, and cannot supersede another")
    index["sets"][old] = {"superseded_by": new, "cause": cause.strip(), "at": datetime.now(timezone.utc).isoformat()}
    write_json(Path(out_dir).joinpath("index.json"), index)
