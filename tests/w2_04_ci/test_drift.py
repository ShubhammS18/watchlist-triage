"""The drift script (DEC-W2-04-CHOICES): it passes on the committed world, and catches each kind of drift, through
its own comparison and end to end on a copy of the repository in a temporary folder outside it."""
import json
import shutil
import subprocess
import sys

import pytest

from drift_common import REPO, SCRIPT, drift, environment, run_script

PINNED = "b77a6804a52b1d41650e250a31ff64a701b1d315a674a1f1242d93cb6b15c9b0"   # stated in the task outcome
COPIED = ("worldgen", "data/world", "docs/rubric.md", SCRIPT)       # what regenerating and checking needs


@pytest.fixture(scope="module")
def world():
    return drift.read_tree(REPO.joinpath("data", "world"))


def with_manifest_hash(files, value):
    manifest = json.loads(files["MANIFEST.json"])
    manifest["world_hash"] = value
    return {**files, "MANIFEST.json": (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")}


def copy_repo(folder):
    assert REPO not in folder.parents and folder != REPO                    # outside the repo
    for name in COPIED:
        source, target = REPO.joinpath(name), folder.joinpath(name)
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return folder


def test_the_script_pins_the_hash_the_outcome_states(world):
    assert drift.PINNED == PINNED
    assert drift.world_hash(world) == json.loads(world["MANIFEST.json"])["world_hash"] == PINNED


def test_the_script_passes_on_the_committed_world():
    result = run_script(REPO)
    assert result.returncode == 0, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert lines[0].startswith("Python 3.12.")
    assert lines[1] == f"seed 20260930: 11 files regenerated, 11 committed; world hash of data/world {PINNED}"
    assert lines[2:] == [f"OK: no drift; world hash {PINNED}"]


def test_the_comparison_finds_nothing_on_the_committed_world(world):
    assert drift.problems(world, dict(world)) == []


def test_a_changed_byte_in_any_regenerated_file_is_drift(world):
    for path in ("agent/alerts.jsonl", "hidden/labels.jsonl", "README.md"):
        regenerated = {**world, path: world[path][:-2] + bytes([world[path][-2] ^ 1]) + world[path][-1:]}
        assert drift.problems(world, regenerated) == [
            f"differs: {path} (committed sha256 {drift.sha(world[path])}, "
            f"regenerated sha256 {drift.sha(regenerated[path])})"]


def test_an_extra_committed_file_is_drift(world):
    extra = b"{}\n"
    committed = {**world, "agent/extra.jsonl": extra}
    assert drift.problems(committed, world) == [
        f"not regenerated: agent/extra.jsonl (committed sha256 {drift.sha(extra)})",
        f"world hash of data/world is {drift.world_hash(committed)}, not the frozen {PINNED}"]


def test_a_missing_committed_file_is_drift(world):
    committed = {path: data for path, data in world.items() if path != "hidden/twin_links.jsonl"}
    found = drift.problems(committed, world)
    assert found == [f"missing from data/world: hidden/twin_links.jsonl (regenerated sha256 "
                     f"{drift.sha(world['hidden/twin_links.jsonl'])})",
                     f"world hash of data/world is {drift.world_hash(committed)}, not the frozen {PINNED}"]


def test_a_re_seeded_world_committed_with_its_own_manifest_is_drift(world):
    """Both sides agree byte for byte, as after a seed change regenerated and committed: only the pin catches it."""
    files = {**world, "agent/alerts.jsonl": world["agent/alerts.jsonl"] + b"\n"}
    files = with_manifest_hash(files, drift.world_hash(files))
    assert drift.problems(files, dict(files)) == [
        f"world hash of data/world is {drift.world_hash(files)}, not the frozen {PINNED}",
        f"MANIFEST.json world_hash is {drift.world_hash(files)!r}, not the frozen {PINNED}"]


def test_a_committed_manifest_with_another_hash_is_drift(world):
    committed = with_manifest_hash(world, "0" * 64)
    found = drift.problems(committed, world)
    assert found[0].startswith("differs: MANIFEST.json ")
    assert found[1:] == [f"MANIFEST.json world_hash is {'0' * 64!r}, not the frozen {PINNED}"]


@pytest.mark.parametrize("manifest", [b"not json", b"[]\n", b"{}\n"], ids=["not-json", "a-list", "no-field"])
def test_an_unreadable_manifest_is_drift(world, manifest):
    files = {**world, "MANIFEST.json": manifest}
    assert drift.problems(files, dict(files)) == [f"MANIFEST.json world_hash is None, not the frozen {PINNED}"]


def test_end_to_end_a_changed_world_byte_fails_the_copied_script(tmp_path):
    folder = copy_repo(tmp_path.joinpath("repo"))
    alerts = folder.joinpath("data", "world", "agent", "alerts.jsonl")
    data = alerts.read_bytes()
    alerts.write_bytes(data[:100] + bytes([data[100] ^ 1]) + data[101:])
    result = run_script(folder)
    assert result.returncode == 1, result.stdout + result.stderr
    changed = drift.world_hash(drift.read_tree(folder.joinpath("data", "world")))
    drifts = [line for line in result.stdout.splitlines() if line.startswith("DRIFT: ")]
    assert [line.split(" (")[0] for line in drifts] == [
        "DRIFT: differs: agent/alerts.jsonl", f"DRIFT: world hash of data/world is {changed}, not the frozen {PINNED}"]
    assert result.stdout.splitlines()[-1] == "FAILED: 2 problem(s)"


def test_end_to_end_a_re_seeded_world_fails_the_copied_script(tmp_path):
    """The copy's seed is changed and its world regenerated and committed in place, so every byte agrees."""
    folder = copy_repo(tmp_path.joinpath("repo"))
    config = folder.joinpath("worldgen", "config.json")
    text = config.read_text(encoding="utf-8")
    assert text.count('"seed": 20260930') == 1
    config.write_text(text.replace('"seed": 20260930', '"seed": 1'), encoding="utf-8")
    regenerated = subprocess.run([sys.executable, "-B", "-m", "worldgen"], cwd=folder, capture_output=True, text=True,
                                 env=environment())
    assert regenerated.returncode == 0 and "seed 1)" in regenerated.stdout, regenerated.stderr
    result = run_script(folder)
    assert result.returncode == 1, result.stdout + result.stderr
    reseeded = drift.world_hash(drift.read_tree(folder.joinpath("data", "world")))
    assert reseeded != PINNED
    assert [line for line in result.stdout.splitlines() if line.startswith("DRIFT: ")] == [
        f"DRIFT: world hash of data/world is {reseeded}, not the frozen {PINNED}",
        f"DRIFT: MANIFEST.json world_hash is {reseeded!r}, not the frozen {PINNED}"]


PROBE = """\
import runpy, sys
if sys.argv[2] != "real":
    sys.version_info = (*map(int, sys.argv[2].split(".")), "final", 0)
try:
    runpy.run_path(sys.argv[1], run_name="__main__")
    code = 0
except SystemExit as stop:
    code = stop.code
imported = sorted(name for name in sys.modules if name == "worldgen" or name.startswith("worldgen."))
print("worldgen modules imported:", imported, file=sys.stderr)
sys.exit(code)
"""


def probe(version):
    """The script run with sys.version_info replaced (as if a runner had another Python), or as it is with "real";
    stderr ends with the worldgen modules imported by the time it stopped."""
    return subprocess.run([sys.executable, "-B", "-c", PROBE, SCRIPT, version], cwd=REPO, capture_output=True,
                          text=True, env=environment())


@pytest.mark.parametrize("version", ["3.11.9", "3.13.0"])
def test_any_python_but_3_12_is_refused_before_worldgen_is_imported(version):
    result = probe(version)
    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout == (f"unsupported Python {version}: this check supports Python 3.12 only. "
                             "It did not run; this is not drift.\n")
    assert result.stderr == "worldgen modules imported: []\n"


def test_the_probe_sees_worldgen_imported_when_the_python_is_supported():
    """The positive control: on Python 3.12 the same probe sees the script import worldgen and run to OK."""
    result = probe("real")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "worldgen.build" in result.stderr.splitlines()[-1]
    assert result.stdout.splitlines()[-1].startswith("OK: no drift")
