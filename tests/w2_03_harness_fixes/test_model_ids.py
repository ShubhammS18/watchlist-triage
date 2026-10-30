"""W2-03, T06 known issue 2 and the non-finite case of known issue 3 (DEC-W2-03-CHOICES).

A provider that reports model IDs as numbers and as text in one run no longer breaks the manifest: the summary keys
a number as "number:<value>", while each attempt keeps its ID as reported (DEC-T06-MANIFEST-9). A non-finite
reported ID cannot be refused at start: the real adapter turns every ID into text, and a run that holds one anyway
is still refused when it is scored.
"""
import json
import math

import pytest

import fake_model
from conftest import WORLD, read_lines, write_config
from harness import run as harness_run
from harness import schema, score
from model_interface import Result, anthropic_api


class Mixed(fake_model.Fake):
    """The fake, but a bundle in one of the fake's buckets reports a number as its model ID, and one in another a
    non-finite number. Which bundles do depends only on their evidence IDs, as the fake's answers do."""

    def __call__(self, request):
        result = super().__call__(request)
        bucket = fake_model._number(fake_model.evidence_ids(request)) % 7
        model_id = {0: 123, 1: math.nan}.get(bucket, result.model_id)
        return Result(result.text, model_id, result.input_tokens, result.output_tokens, result.latency_s)


@pytest.fixture(scope="module")
def mixed_run(tmp_path_factory):
    folder = tmp_path_factory.mktemp("mixed")
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(harness_run.providers.PROVIDERS, "mixed", Mixed)
        patch.setattr(harness_run, "NOT_REAL", harness_run.NOT_REAL | {"mixed"})
        out = folder.joinpath("out")
        manifest = harness_run.run(write_config(folder, model={"provider": "mixed"}), out)
    return out, manifest, read_lines(out, manifest["run_id"])


def test_a_run_whose_model_reports_numbers_and_text_writes_its_manifest(mixed_run):
    out, manifest, lines = mixed_run
    assert manifest["state"] == "completed", manifest["aborted"]
    written = json.loads(out.joinpath(manifest["run_id"], "manifest.json").read_text(encoding="utf-8"))
    assert written == json.loads(json.dumps(manifest))  # the file holds what run() returned
    entry = [one for one in json.loads(out.joinpath("index.json").read_text(encoding="utf-8"))["runs"]
             if one["run_id"] == manifest["run_id"]]
    assert [one["state"] for one in entry] == ["completed"]


def test_the_summary_keys_numbers_apart_from_text_and_counts_every_reported_attempt(mixed_run):
    _, manifest, lines = mixed_run
    reported = [attempt["model_id"] for line in lines for attempt in line["attempts"] if attempt["model_id"] is not None]
    texts = sum(1 for one in reported if type(one) is str)
    numbers = sum(1 for one in reported if one == 123)
    nans = sum(1 for one in reported if type(one) is float and math.isnan(one))
    assert texts and numbers and nans and texts + numbers + nans == len(reported)
    assert manifest["model"]["reported"] == {"fake-1": texts, "number:123": numbers, "number:nan": nans}
    assert schema.problem(schema.MANIFEST, json.loads(json.dumps(manifest))) is None


def test_each_attempt_keeps_its_model_id_as_reported(mixed_run):
    _, _, lines = mixed_run
    kinds = {type(attempt["model_id"]) for line in lines for attempt in line["attempts"]} - {type(None)}
    assert kinds == {str, int, float}  # text, 123 and NaN, none of them turned into text


def test_a_run_holding_a_non_finite_model_id_is_still_refused_when_scored(mixed_run):
    out, manifest, _ = mixed_run
    with pytest.raises(score.ScoreRefused, match="model_id"):  # the run is the folder's only one: nothing is written
        score.score_all(out, WORLD)
    assert not out.joinpath(manifest["run_id"], "report.json").exists()


@pytest.mark.parametrize("reported, expected", [(123, "123"), (1.5, "1.5"), (math.nan, "nan"), (math.inf, "inf"),
                                                (-math.inf, "-inf"), ("claude-haiku-5-5", "claude-haiku-5-5")])
def test_the_real_adapter_turns_every_reported_model_id_into_text(reported, expected):
    reply = {"model": reported, "content": [{"type": "text", "text": "{}"}], "usage": {"input_tokens": 1, "output_tokens": 1}}
    result = anthropic_api._result(reply, 0.0)
    assert type(result.model_id) is str and result.model_id == expected
