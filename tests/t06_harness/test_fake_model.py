"""T06: the test-only fake model answers from the prompt alone, by evidence IDs and never by call order
(DEC-T06-FAKE-MODEL)."""
import ast
import json
from collections import Counter
from pathlib import Path

import fake_model
from baseline_agent.payload import build_payload
from baseline_agent.prompt import build_messages
from framings import FRAMINGS, frame
from model_interface import ModelError, Request, Settings
from worldgen.harness_twins import load_twins
from worldgen.loader import load_alerts

SETTINGS = Settings("fake-1", 0, 512, 30)
BUNDLES = load_alerts() + load_twins()


def ids_of(alert):
    return [item["id"] for item in alert["evidence"]]


def answer(model, alert, framing):
    """What the fake does with one alert in one framing: the reply text, or the name of the error it raises."""
    try:
        return model(Request(build_messages(build_payload(frame(alert, framing))), SETTINGS)).text
    except ModelError as error:
        return type(error).__name__


def test_the_key_is_unique_across_the_600_alerts_and_the_15_twins():
    keys = [fake_model.key_of(ids_of(alert)) for alert in BUNDLES]
    assert len(keys) == 615 and len(set(keys)) == 615


def test_every_outcome_occurs_in_the_world():
    seen = Counter(fake_model.outcome_of(ids_of(alert)) for alert in BUNDLES)
    assert set(seen) == {name for name, _ in fake_model.SHARES}


def test_the_answers_do_not_follow_call_order():
    calls = [(alert, framing) for alert in BUNDLES for framing in FRAMINGS]
    forward = [answer(fake_model.Fake(), alert, framing) for alert, framing in calls]
    backward = [answer(fake_model.Fake(), alert, framing) for alert, framing in reversed(calls)]
    one_model = fake_model.Fake()
    twice = [answer(one_model, alert, framing) for alert, framing in calls + calls]
    assert forward == backward[::-1] == twice[:len(calls)] == twice[len(calls):]


def test_only_the_by_first_outcome_changes_with_the_framing():
    for alert in BUNDLES:
        answers = {answer(fake_model.Fake(), alert, framing) for framing in FRAMINGS}
        if fake_model.outcome_of(ids_of(alert)) != "by_first":
            assert len(answers) == 1, alert["id"]
    mixed = [alert["id"] for alert in BUNDLES if fake_model.outcome_of(ids_of(alert)) == "by_first"
             and len({json.loads(answer(fake_model.Fake(), alert, framing))["recommendation"] for framing in FRAMINGS}) == 2]
    assert mixed  # some alerts do get different verdicts in different framings


def test_it_reads_the_ids_from_the_prompt_as_presented():
    alert = BUNDLES[0]
    for framing in FRAMINGS:
        request = Request(build_messages(build_payload(frame(alert, framing))), SETTINGS)
        assert fake_model.evidence_ids(request) == [item["id"] for item in frame(alert, framing)]


def test_it_reports_token_counts_or_none():
    alert = next(a for a in BUNDLES if fake_model.outcome_of(ids_of(a)) == "close")
    request = Request(build_messages(build_payload(alert["evidence"])), SETTINGS)
    counted, uncounted = fake_model.Fake()(request), fake_model.Fake(tokens=False)(request)
    assert counted.input_tokens > 0 and counted.output_tokens > 0 and counted.model_id == "fake-1"
    assert uncounted.input_tokens is None and uncounted.output_tokens is None


def test_the_fake_imports_no_world_code_and_opens_no_file():
    tree = ast.parse(Path(fake_model.__file__).read_text(encoding="utf-8"))
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not {name for name in imported if name.split(".")[0] in ("worldgen", "framings", "os", "pathlib", "io")}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "open" not in names and not attributes & {"open", "read_text", "read_bytes"}


def test_the_shares_add_up_to_one_hundred_buckets():
    assert sum(share for _, share in fake_model.SHARES) == 100 == len(fake_model.BUCKETS)
