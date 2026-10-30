"""W2-03, T06 known issue 3 (DEC-W2-03-CHOICES): the run step checks the part of the manifest its inputs decide
against the shared schema before any call, so it refuses at start what the score step would refuse later. A refusal
leaves no run folder and no index entry."""
import json
import shutil

import pytest

from conftest import REPO, WORLD, read_lines, write_config
from harness import run as harness_run
from harness import schema

CASES = {
    "a blank re-run cause": ({}, {}, ""),
    "a re-run cause of only spaces": ({}, {}, "   "),
    "a model name of only spaces": ({"model": "   "}, {}, None),
    "an infinite temperature": ({"temperature": float("inf")}, {}, None),
    "a timeout that is not a number": ({"timeout_s": float("nan")}, {}, None),
    "an infinite timeout": ({"timeout_s": float("inf")}, {}, None),
}


class NeverCalled:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, request):
        raise AssertionError("a model was called before the refusal")


def refused(config, out, rerun_cause=None):
    with pytest.raises(harness_run.ConfigError, match="the score step would refuse this run") as caught:
        harness_run.run(config, out, rerun_cause=rerun_cause)
    assert not out.exists()  # no run folder and no index entry: nothing was written
    return str(caught.value)


@pytest.mark.parametrize("case", sorted(CASES))
def test_an_input_the_schema_refuses_is_refused_before_any_call(tmp_path, monkeypatch, case):
    model, _, rerun_cause = CASES[case]
    monkeypatch.setitem(harness_run.providers.PROVIDERS, "fake", NeverCalled)
    config = write_config(tmp_path, model=model)  # json.dumps writes Infinity and NaN, which json.loads reads back
    refused(config, tmp_path.joinpath("out"), rerun_cause)


@pytest.mark.parametrize("field, value", [("rubric_version", 1.2), ("generator_version", None)])
def test_a_world_manifest_field_the_schema_refuses_is_refused_before_any_call(tmp_path, monkeypatch, field, value):
    world = tmp_path.joinpath("world")
    shutil.copytree(WORLD, world)
    listed = json.loads(world.joinpath("MANIFEST.json").read_text(encoding="utf-8"))
    listed[field] = value  # neither field is part of the world hash, so the world check would not notice
    world.joinpath("MANIFEST.json").write_text(json.dumps(listed), encoding="utf-8")
    monkeypatch.setitem(harness_run.providers.PROVIDERS, "fake", NeverCalled)
    message = refused(write_config(tmp_path, world=world), tmp_path.joinpath("out"))
    assert f"manifest.world.{field}" in message


def test_a_plain_run_is_not_refused_and_writes_the_same_manifest_shape(tmp_path):
    out = tmp_path.joinpath("out")
    manifest = harness_run.run(write_config(tmp_path), out, rerun_cause="a written cause")
    assert manifest["state"] == "completed" and manifest["rerun_cause"] == "a written cause"
    assert schema.problem(schema.MANIFEST, json.loads(json.dumps(manifest))) is None
    assert len(read_lines(out, manifest["run_id"])) == manifest["items"]["total"] == 1845


@pytest.mark.parametrize("folder", ["baseline", "w2-02-runs"])
def test_every_committed_manifest_still_passes_the_schema_the_start_check_uses(folder):
    manifests = sorted(REPO.joinpath(folder).glob("2*/manifest.json"))
    assert len(manifests) == 3
    for path in manifests:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert schema.problem(schema.MANIFEST, manifest) is None, path


@pytest.mark.parametrize("value", ["1.5", "-0.1", "NaN", "Infinity", "not a number", 0.05])
def test_a_threshold_the_schema_refuses_is_refused_before_any_call(tmp_path, monkeypatch, value):
    """load_config refuses these too; here it is made to hand one over, as if its own check had drifted, to show
    that the start check stops the run anyway."""
    real = harness_run.load_config
    monkeypatch.setattr(harness_run, "load_config", lambda path: {**real(path), "threshold": value})
    monkeypatch.setitem(harness_run.providers.PROVIDERS, "fake", NeverCalled)
    message = refused(write_config(tmp_path), tmp_path.joinpath("out"))
    assert "threshold" in message


def test_the_manifest_records_the_threshold_that_was_checked(tmp_path):
    manifest = harness_run.run(write_config(tmp_path, infra_invalid_threshold="0.25"), tmp_path.joinpath("out"))
    assert manifest["infra_invalid"]["threshold"] == manifest["run_set_inputs"]["infra_invalid_threshold"] == "0.25"
