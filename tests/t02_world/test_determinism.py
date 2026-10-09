"""Regeneration is byte-identical (NFR-2, AC-10). Everything is written to a temp folder outside the repo."""
import hashlib
import json
import subprocess
import sys

from conftest import WORLD_DIR, TABLES
from worldgen import ROOT, load_config
from worldgen.build import generate, rubric_version, write

REPO = ROOT.parent


def committed():
    return {p.relative_to(WORLD_DIR).as_posix(): p.read_bytes() for p in sorted(WORLD_DIR.rglob("*")) if p.is_file()}


def world_hash(files):
    lines = sorted(f"{path}:{hashlib.sha256(data).hexdigest()}" for path, data in files.items() if path != "MANIFEST.json")
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def test_the_temp_folder_is_outside_the_repo(tmp_path):
    assert REPO not in tmp_path.parents and tmp_path != REPO


def test_regenerating_in_a_temp_folder_gives_the_committed_bytes(tmp_path):
    files, summary = generate()
    write(files, tmp_path)
    regenerated = {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in sorted(tmp_path.rglob("*")) if p.is_file()}
    assert regenerated == committed()
    assert json.loads(regenerated["MANIFEST.json"])["world_hash"] == json.loads(committed()["MANIFEST.json"])["world_hash"]
    assert summary["alerts"] == 600 and summary["matcher_alerts"] == 600


def test_two_runs_agree():
    first, _ = generate()
    second, _ = generate()
    assert first == second


def test_the_command_line_writes_the_committed_world(tmp_path):
    out = tmp_path.joinpath("cli")
    result = subprocess.run([sys.executable, "-m", "worldgen", "--out", str(out)], cwd=REPO, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "seed 20260930" in result.stdout
    written = {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}
    assert written == committed()


def test_a_different_seed_gives_a_different_valid_world():
    other, summary = generate(1)                     # the build itself checks the matcher and the rubric
    assert summary["alerts"] == 600 and summary["matcher_alerts"] == 600
    assert other["MANIFEST.json"] != committed()["MANIFEST.json"]
    assert json.loads(other["MANIFEST.json"])["seed"] == 1
    assert other["agent/alerts.jsonl"] != committed()["agent/alerts.jsonl"]


def test_the_manifest_is_complete_and_its_world_hash_follows_the_stated_definition():
    files = committed()
    manifest = json.loads(files["MANIFEST.json"])
    others = {p: d for p, d in files.items() if p != "MANIFEST.json"}
    assert manifest["files"] == {p: hashlib.sha256(d).hexdigest() for p, d in sorted(others.items())}
    assert set(others) == set(TABLES.values()) | {"README.md"}
    assert manifest["world_hash"] == world_hash(files)
    assert "relative_path:file_sha256" in manifest["header_comment"] and "MANIFEST.json" in manifest["header_comment"]
    assert manifest["generator_version"] == load_config()["version"]
    assert manifest["rubric_version"] == rubric_version() == "1.2"
    assert manifest["seed"] == load_config()["seed"] and manifest["as_of_date"] == load_config()["as_of_date"]
    assert files["MANIFEST.json"].endswith(b"\n")
