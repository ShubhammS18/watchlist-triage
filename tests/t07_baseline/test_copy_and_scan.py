"""T07: the copy into baseline/ (DEC-T07-BASELINE-DIR) and the gitleaks helper (DEC-T07-RUN-SET)."""
import hashlib
import json
import subprocess

import pytest

from baseline_run import copy_step, gitleaks
from harness.manifest import REPO


@pytest.fixture
def source(tmp_path):
    out = tmp_path.joinpath("out")
    for name, data in (("r1/manifest.json", b'{"a": 1}\n'), ("r1/items.jsonl", b'{"x": "\xc3\xa9"}\r\n'),
                       ("r1/report.json", b"{}"), ("r2/manifest.json", b'{"aborted": true}'),
                       ("sets/abc.json", b'{"set": 1}'), ("notes.txt", b"not run output")):
        out.joinpath(name).parent.mkdir(parents=True, exist_ok=True)
        out.joinpath(name).write_bytes(data)
    out.joinpath("index.json").write_text(json.dumps({"runs": [{"run_id": "r1"}, {"run_id": "r2"}], "sets": {}}))
    return out


def test_the_copy_is_byte_for_byte_with_a_hash_list_that_sha256sum_accepts(tmp_path, source):
    dest = tmp_path.joinpath("repo", "baseline")
    listed = copy_step.copy_baseline(source, dest)
    names = ["index.json", "sets/abc.json", "r1/items.jsonl", "r1/manifest.json", "r1/report.json", "r2/manifest.json"]
    assert list(listed) == names  # notes.txt is not run output, so it is not copied
    for name in names:
        assert dest.joinpath(name).read_bytes() == source.joinpath(name).read_bytes()
        assert listed[name] == hashlib.sha256(source.joinpath(name).read_bytes()).hexdigest()
    assert dest.joinpath("SHA256SUMS").read_text() == "".join(f"{listed[n]}  {n}\n" for n in names)
    assert not dest.joinpath("notes.txt").exists()
    check = subprocess.run(["sha256sum", "-c", "--strict", "SHA256SUMS"], cwd=dest, capture_output=True, text=True)
    assert check.returncode == 0, check.stdout + check.stderr


def test_the_copy_refuses_a_baseline_folder_that_has_content(tmp_path, source):
    dest = tmp_path.joinpath("baseline")
    dest.mkdir()
    dest.joinpath("old.json").write_text("kept")
    with pytest.raises(ValueError, match="already has content"):
        copy_step.copy_baseline(source, dest)
    assert [p.name for p in dest.iterdir()] == ["old.json"] and dest.joinpath("old.json").read_text() == "kept"


def test_the_copy_refuses_a_source_inside_the_repository_or_a_listed_run_that_is_missing(tmp_path, source):
    with pytest.raises(ValueError, match="outside the repository"):
        copy_step.copy_baseline(REPO.joinpath("data"), tmp_path.joinpath("b1"))
    source.joinpath("index.json").write_text(json.dumps({"runs": [{"run_id": "r9"}], "sets": {}}))
    with pytest.raises(ValueError, match="r9 that index.json lists is missing"):
        copy_step.copy_baseline(source, tmp_path.joinpath("b2"))


def test_the_copy_finds_a_copied_file_that_differs(tmp_path, source, monkeypatch):
    real = copy_step.shutil.copyfile
    monkeypatch.setattr(copy_step.shutil, "copyfile",
                        lambda a, b: real(a, b) and (b.write_bytes(b"changed") if b.name == "report.json" else None))
    with pytest.raises(ValueError, match="r1/report.json in .* does not match its listed SHA-256"):
        copy_step.copy_baseline(source, tmp_path.joinpath("b"))


def test_gitleaks_runs_the_recorded_command(tmp_path, monkeypatch):
    monkeypatch.setenv("GITLEAKS_CONFIG", "/somewhere/else.toml")
    folder, reports = tmp_path.joinpath("trial-out"), tmp_path.joinpath("scratch")
    folder.mkdir()
    assert gitleaks.command(folder, reports, "/bin/gitleaks") == [
        "env", "-u", "GITLEAKS_CONFIG", "-u", "GITLEAKS_CONFIG_TOML", "/bin/gitleaks", "dir", str(folder),
        "--no-banner", "--redact", "--verbose", "--ignore-gitleaks-allow", "-i", "/tmp/gitleaks-noignore",
        "--report-format", "json", "--report-path", str(reports.joinpath("gitleaks-trial-out.json"))]
    fake = tmp_path.joinpath("fake-gitleaks")
    fake.write_text('#!/bin/sh\necho "$@" > "$(dirname "$0")/argv"; [ -z "$GITLEAKS_CONFIG" ] && exit 1\n')
    fake.chmod(0o755)
    assert gitleaks.scan(folder, reports, str(fake)) == 1  # findings, and GITLEAKS_CONFIG was unset
    assert tmp_path.joinpath("argv").read_text().startswith(f"dir {folder} --no-banner")


def test_gitleaks_refuses_a_folder_holding_a_gitleaks_config(tmp_path):
    tmp_path.joinpath("run", "sub").mkdir(parents=True)
    tmp_path.joinpath("run", "sub", ".gitleaks.toml").write_text("")
    with pytest.raises(ValueError, match="holds a gitleaks config"):
        gitleaks.scan(tmp_path.joinpath("run"), tmp_path, "/bin/false")
