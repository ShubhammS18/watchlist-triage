"""The proven cost bound (DEC-W2-01-ELIGIBILITY-2). A call that failed and left no token counts is bounded: its input
is the input tokens of the successful retry of the same request or, with no successful retry, its recorded prompt bytes
at one token per byte, trusted only if no successful call in the set used more input tokens than its prompt bytes; its
answer counts at the full answer limit. A call that can be bounded neither way leaves the set not eligible. The cost
target is judged on the known cost plus the bound."""
import json
from fractions import Fraction

from harness import release_check

from conftest import SOURCED

PRICES = json.loads(SOURCED["price_table"].read_text(encoding="utf-8"))  # claude-haiku-5-5: 0.10 in, 0.50 out per million
MANIFEST = {"model": {"requested": "claude-haiku-5-5"}, "decoding": {"max_tokens": 512}}
FAILED = {"error": "ProviderError", "input_tokens": None, "output_tokens": None, "model_id": None}


def ok(input_tokens, prompt_bytes=None):
    one = {"error": None, "input_tokens": input_tokens, "output_tokens": 40, "model_id": "claude-haiku-5-5"}
    return one if prompt_bytes is None else {**one, "prompt_bytes": prompt_bytes}


def line(*attempts, twin=False, item="A/1"):
    return {"item_id": item, "twin": twin, "attempts": list(attempts)}


def bound(lines, valid=("r1",)):
    return release_check.cost_bound({"r1": (MANIFEST, lines)}, list(valid), PRICES)


def usd(input_tokens):
    return (input_tokens * Fraction(1, 10) + 512 * Fraction(1, 2)) / 1_000_000


def test_a_failed_try_is_bounded_by_its_successful_retry():
    found, problems = bound([line(FAILED, ok(600))])
    assert problems == [] and found == {"tries": 1, "main": usd(600)}


def test_a_failed_try_with_no_retry_is_bounded_by_its_prompt_bytes():
    found, problems = bound([line({**FAILED, "prompt_bytes": 1000}), line(ok(600, 1500), item="B/1")])
    assert problems == [] and found == {"tries": 1, "main": usd(1000)}


def test_the_prompt_bytes_bound_is_untrusted_when_a_call_used_more_tokens_than_bytes_or_has_no_size():
    for success in (ok(1600, 1500), ok(600)):
        _, problems = bound([line({**FAILED, "prompt_bytes": 1000}), line(success, item="B/1")])
        assert len(problems) == 1 and problems[0].startswith("the prompt-size bound cannot be trusted: 1 successful")


def test_tokens_above_bytes_do_not_matter_when_no_bound_rests_on_bytes():
    assert bound([line(FAILED, ok(600)), line(ok(1600, 1500), item="B/1")])[1] == []


def test_a_failed_try_with_neither_a_retry_nor_a_size_cannot_be_bounded():
    _, problems = bound([line(FAILED, FAILED)])
    assert problems == ["2 calls left no token counts, no successful retry and no recorded prompt size, so their cost "
                        "cannot be bounded (first: r1 A/1)"]


def test_only_main_items_of_valid_runs_add_to_the_cost_target_but_every_try_must_be_bounded():
    found, problems = bound([line(FAILED, ok(600), twin=True)])
    assert problems == [] and found == {"tries": 1, "main": 0}
    found, problems = bound([line(FAILED, ok(600))], valid=())
    assert problems == [] and found == {"tries": 1, "main": 0}


def test_the_cost_target_is_judged_on_the_known_cost_plus_the_bound(oracle_set, monkeypatch):
    main_items = 3 * 1800  # the oracle set's valid runs
    under = Fraction(1, 5) * main_items - Fraction(1, 1_000_000)  # just under USD 0.20 per main item
    monkeypatch.setattr(release_check, "cost_bound", lambda loaded, valid, prices: ({"tries": 2, "main": under}, []))
    result = release_check.check(oracle_set[0], oracle_set[1])
    cost = result["targets"]["cost_per_alert"]
    assert result["result"] == "PASS" and cost["result"] == "pass" and cost["failed_tries_bounded"] == 2
    assert cost["known_per_alert"]["numerator"] == 0 and cost["console"] == "the Console figure is checked at review"
    assert Fraction(cost["value"]["numerator"], cost["value"]["denominator"]) == under / main_items
    monkeypatch.setattr(release_check, "cost_bound", lambda loaded, valid, prices: ({"tries": 1, "main": Fraction(1, 5) * main_items + 1}, []))
    over = release_check.check(oracle_set[0], oracle_set[1])
    assert over["result"] == "FAIL" and over["failed"] == ["cost_per_alert"]
