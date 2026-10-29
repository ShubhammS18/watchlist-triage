"""T06 stage 3: model cost and modelled review time (NFR-6, FR-22, AC-24, DEC-T06-COST, DEC-T06-MODELLED-TIME).
Expected values are literals worked out by hand, or counted here from the fake model's own token rule."""
import json
from fractions import Fraction
from pathlib import Path

import pytest

import fake_model
import micro_case
from baseline_agent.payload import build_payload
from baseline_agent.prompt import build_messages
from conftest import FIXTURES, write_config
from framings import FRAMINGS, frame
from harness import cost as money
from harness import run as harness_run
from harness import score
from model_interface import Settings
from worldgen.harness_twins import load_twins
from worldgen.loader import load_alerts

PRICES = json.loads(FIXTURES.joinpath("prices.json").read_text(encoding="utf-8"))
TIMES = json.loads(FIXTURES.joinpath("modelled_time.json").read_text(encoding="utf-8"))
WORLD = Path(__file__).resolve().parents[2].joinpath("data", "world")


def call(input_tokens, output_tokens, model_id="fake-1", error=None):
    return {"error": error, "input_tokens": input_tokens, "output_tokens": output_tokens, "model_id": model_id}


# ---- the two files

def changed(table, path, value):
    table = json.loads(json.dumps(table))
    place = table
    for key in path[:-1]:
        place = place[key]
    if value is KeyError:
        del place[path[-1]]
    else:
        place[path[-1]] = value
    return table


PRICE_SOURCES = {"fake-1": {"input": "price page of the provider, read 2026-10-13", "output": "the same page"}}
TIME_SOURCES = {name: dict.fromkeys(money.PARAMETERS, "owner estimate of 2026-10-13") for name in money.SETS}
SOURCED_PRICES = {**PRICES, "kind": "sourced", "sources": PRICE_SOURCES}
SOURCED_TIMES = {**TIMES, "kind": "sourced", "sources": TIME_SOURCES}


def test_the_fixture_files_are_accepted_and_say_they_are_fixtures():
    money.check_prices(PRICES)
    money.check_times(TIMES)
    assert PRICES["kind"] == "fixture" == TIMES["kind"] and TIMES["unit"] == "minutes"
    assert money.is_fixture(PRICES) and money.is_fixture(TIMES)
    money.check_prices(changed(PRICES, ["note"], KeyError))  # the note is optional; the kind is not


def test_a_sourced_file_is_accepted_when_every_value_has_a_source():
    money.check_prices(SOURCED_PRICES)
    money.check_times(SOURCED_TIMES)
    assert not money.is_fixture(SOURCED_PRICES) and not money.is_fixture(SOURCED_TIMES)


@pytest.mark.parametrize("check, table, path, value", [
    (money.check_prices, PRICES, ["kind"], KeyError), (money.check_prices, PRICES, ["kind"], "real"),
    (money.check_prices, PRICES, ["kind"], True), (money.check_prices, PRICES, ["kind"], "sourced"),  # no sources
    (money.check_prices, PRICES, ["sources"], PRICE_SOURCES),  # a fixture has none
    (money.check_prices, SOURCED_PRICES, ["sources"], KeyError), (money.check_prices, SOURCED_PRICES, ["sources"], {}),
    (money.check_prices, SOURCED_PRICES, ["sources", "fake-1", "output"], KeyError),
    (money.check_prices, SOURCED_PRICES, ["sources", "fake-1", "input"], " "),
    (money.check_prices, SOURCED_PRICES, ["sources", "fake-1", "input"], 3),
    (money.check_prices, SOURCED_PRICES, ["sources", "another-model"], {"input": "a", "output": "b"}),
    (money.check_times, TIMES, ["kind"], KeyError), (money.check_times, TIMES, ["kind"], "sourced"),
    (money.check_times, TIMES, ["sources"], TIME_SOURCES),
    (money.check_times, SOURCED_TIMES, ["sources", "HIGH"], KeyError),
    (money.check_times, SOURCED_TIMES, ["sources", "LOW", "l2"], KeyError),
    (money.check_times, SOURCED_TIMES, ["sources", "BASE", "second_review"], ""),
    (money.check_times, SOURCED_TIMES, ["sources", "BASE", "extra"], "a source for nothing"),
])
def test_a_file_must_say_its_kind_and_a_sourced_one_must_source_every_value(check, table, path, value):
    with pytest.raises(money.TableError):
        check(changed(table, path, value))


def write(folder, name, value):
    folder.joinpath(name).write_text(json.dumps(value), encoding="utf-8")
    return str(folder.joinpath(name))


@pytest.mark.parametrize("prices, times, named", [
    (PRICES, TIMES, "the price table and the modelled-time file"),
    (PRICES, SOURCED_TIMES, "the price table must"),
    (SOURCED_PRICES, TIMES, "the modelled-time file must"),
])
def test_a_real_provider_refuses_a_fixture_file_before_any_call(tmp_path, monkeypatch, prices, times, named):
    calls = []
    monkeypatch.setitem(harness_run.providers.PROVIDERS, "some_real_provider", lambda: calls.append)
    model = write(tmp_path, "model.json", {"provider": "some_real_provider", "model": "m", "temperature": 0,
                                           "max_tokens": 8, "timeout_s": 5})
    config = write_config(tmp_path, model_config=model, price_table=write(tmp_path, "prices.json", prices),
                          modelled_time=write(tmp_path, "times.json", times))
    with pytest.raises(harness_run.ConfigError, match=f"real provider 'some_real_provider' refuses a fixture: {named}"):
        harness_run.run(config, tmp_path.joinpath("out"))
    assert calls == [] and not tmp_path.joinpath("out").exists()


def test_a_real_provider_runs_with_sourced_files_and_its_results_are_not_mechanism_only(tmp_path, monkeypatch, clean_scoring):
    monkeypatch.setitem(harness_run.providers.PROVIDERS, "some_real_provider", fake_model.Fake)
    model = write(tmp_path, "model.json", {"provider": "some_real_provider", "model": "fake-1", "temperature": 0,
                                           "max_tokens": 512, "timeout_s": 30})
    config = write_config(tmp_path, model_config=model, price_table=write(tmp_path, "prices.json", SOURCED_PRICES),
                          modelled_time=write(tmp_path, "times.json", SOURCED_TIMES))
    manifest = harness_run.run(config, tmp_path.joinpath("out"))
    assert manifest["state"] == "completed" and manifest["model"]["provider"] == "some_real_provider"
    assert manifest["price_table"]["table"]["sources"] == PRICE_SOURCES  # the sources travel with the manifest
    assert manifest["modelled_time"]["parameters"]["sources"] == TIME_SOURCES
    done = score.score_all(tmp_path.joinpath("out"), WORLD)
    report, = done["reports"].values()
    set_report, = done["sets"].values()
    assert report["mechanism_only"] == {"cost": False, "modelled_time": False} == set_report["mechanism_only"]
    assert set_report["acceptance"]["mechanism_only"] is False


def test_the_stub_and_the_test_fake_are_the_only_providers_that_may_use_fixtures():
    import subprocess
    import sys
    shipped = subprocess.run([sys.executable, "-B", "-c", "from harness.run import NOT_REAL; print(sorted(NOT_REAL))"],
                             cwd=WORLD.parents[1], capture_output=True, text=True).stdout.strip()
    assert shipped == "['stub']"  # as shipped; the tests add their fake for the length of the session
    assert harness_run.NOT_REAL == {"stub", "fake", "slow"}


@pytest.mark.parametrize("path, value", [
    (["source"], KeyError), (["date"], KeyError), (["currency"], KeyError), (["unit"], KeyError), (["models"], KeyError),
    (["extra"], 1), (["source"], ""), (["currency"], 7), (["date"], "13 October 2026"),
    (["date"], "2026-02-30"), (["unit"], "per token"), (["models"], {}), (["models"], []),
    (["models", "fake-1"], {"input": "1"}), (["models", "fake-1", "extra"], "1"),
    (["models", "fake-1", "input"], 1.0), (["models", "fake-1", "input"], "-1"),
    (["models", "fake-1", "output"], "NaN"), (["models", "fake-1", "output"], "cheap"),
])
def test_a_wrong_price_table_is_refused_before_any_call(tmp_path, path, value):
    table = changed(PRICES, path, value)
    with pytest.raises(money.TableError):
        money.check_prices(table)
    tmp_path.joinpath("prices.json").write_text(json.dumps(table), encoding="utf-8")
    with pytest.raises(harness_run.ConfigError):
        harness_run.run(write_config(tmp_path, price_table=str(tmp_path.joinpath("prices.json"))), tmp_path.joinpath("out"))
    assert not tmp_path.joinpath("out").exists()


@pytest.mark.parametrize("path, value", [
    (["unit"], KeyError), (["sets"], KeyError), (["unit"], "seconds"), (["extra"], 1), (["sets", "BASE"], KeyError),
    (["sets", "EXTRA"], TIMES["sets"]["BASE"]), (["sets", "LOW", "l2"], KeyError), (["sets", "LOW", "extra"], "1"),
    (["sets", "HIGH", "second_review"], 3), (["sets", "HIGH", "manual_clearing"], "-0.5"),
    (["sets", "BASE", "proposal_review"], "Infinity"),
])
def test_a_wrong_modelled_time_file_is_refused_before_any_call(tmp_path, path, value):
    parameters = changed(TIMES, path, value)
    with pytest.raises(money.TableError):
        money.check_times(parameters)
    tmp_path.joinpath("times.json").write_text(json.dumps(parameters), encoding="utf-8")
    with pytest.raises(harness_run.ConfigError):
        harness_run.run(write_config(tmp_path, modelled_time=str(tmp_path.joinpath("times.json"))), tmp_path.joinpath("out"))
    assert not tmp_path.joinpath("out").exists()


# ---- cost, against literals

def test_cost_in_exact_decimals_with_its_gaps_counted():
    block = money.cost([call(1000, 500), call(None, None, None, "ModelTimeout"), call(3, 1, "some-other-model"),
                        call(250000, 0), call(7, None)], PRICES)
    # 1000 x 1.00 + 500 x 2.00 + 250000 x 1.00 = 252000 millionths of a dollar
    assert block["known_cost"] == {"numerator": 63, "denominator": 250, "not_applicable": False, "decimal": "0.252",
                                   "rounded": False}
    assert block["currency"] == "USD" and block["attempts"] == 5
    assert block["attempts_without_token_counts"] == 2 and block["attempts_without_price"] == 1 and block["at_least"] is True
    assert block["statement"] == "at least 0.252 USD; 2 attempts without token counts, 1 without a price"


def test_a_complete_cost_is_stated_plainly_and_zero_calls_cost_exactly_zero():
    block = money.cost([call(1, 1)], PRICES)
    assert block["known_cost"]["decimal"] == "0.000003" and block["at_least"] is False
    assert block["statement"] == "0.000003 USD"
    none = money.cost([], PRICES)
    assert none["known_cost"]["decimal"] == "0" and none["attempts"] == 0 and none["at_least"] is False
    assert none["statement"] == "0 USD"


def test_unknown_token_counts_are_never_a_cost_of_zero():
    block = money.cost([call(None, None), call(None, None)], PRICES)
    assert block["known_cost"]["decimal"] == "0" and block["at_least"] is True and block["attempts_without_token_counts"] == 2
    assert block["statement"] == "at least 0 USD; 2 attempts without token counts"


def test_no_float_is_used_where_floats_would_be_wrong():
    table = changed(PRICES, ["models", "fake-1"], {"input": "0.1", "output": "0.2"})
    block = money.cost([call(1_000_000, 1_000_000)] * 3, table)
    assert 0.1 + 0.2 + 0.1 + 0.2 + 0.1 + 0.2 != 0.9  # the float sum is off
    assert block["known_cost"]["decimal"] == "0.9" and block["known_cost"]["numerator"] == 9
    tiny = money.cost([call(1, 0)], changed(PRICES, ["models", "fake-1", "input"], "0.000000000001"))
    assert tiny["known_cost"]["decimal"] == "0.000000000000000001"


def test_cost_per_alert_is_rounded_for_reading_and_says_so():
    block = money.cost([call(1_000_000, 0)], PRICES)  # 1 USD
    assert money.per_item(block, 3) == {"numerator": 1, "denominator": 3, "not_applicable": False,
                                        "decimal": "0.333333", "rounded": True}
    assert money.per_item(block, 1800)["decimal"] == "0.000556" and money.per_item(block, 0) is None


# ---- cost, on the full world

def scripted_cost(alerts, framings=FRAMINGS):
    """Counted here from the fake's rule: a call that answers reports the length of the user message and of the
    reply; a call scripted to fail reports nothing. Prices are 1.00 and 2.00 per million."""
    known, without = Fraction(0), 0
    for alert in alerts:
        for framing in framings:
            items = frame(alert, framing)
            ids = [item["id"] for item in items]
            outcome = fake_model.outcome_of(ids)
            if outcome in fake_model.FAULTS:
                without += 3 if outcome in ("timeout", "provider_error") else 1
            else:
                user = build_messages(build_payload(items))[1]["content"]
                known += Fraction(len(user) * 1 + len(fake_model.reply_text(ids)) * 2, 1_000_000)
    return known, without


def test_full_world_cost_for_main_twin_and_total(scored):
    main, main_without = scripted_cost(load_alerts())
    twin, twin_without = scripted_cost(load_twins())
    out, ids, done = scored
    for run_id in ids:
        cost = done["reports"][run_id]["cost"]
        for name, known, without in (("main", main, main_without), ("twin", twin, twin_without),
                                     ("total", main + twin, main_without + twin_without)):
            block = cost[name]
            assert Fraction(block["known_cost"]["numerator"], block["known_cost"]["denominator"]) == known
            assert block["attempts_without_token_counts"] == without and block["attempts_without_price"] == 0
            assert block["at_least"] is True and block["statement"].startswith("at least ")
        assert cost["main_items"] == 1800 and cost["all_items"] == 1845
        # the second figure: the total cost over all items, twins included
        assert Fraction(cost["per_item_all_items"]["numerator"], cost["per_item_all_items"]["denominator"]) == (main + twin) / 1845
        assert Fraction(cost["per_alert"]["numerator"], cost["per_alert"]["denominator"]) == main / 1800
        assert cost["per_alert"]["rounded"] is True and cost["main"]["known_cost"]["rounded"] is False
    report, = done["sets"].values()
    pooled = report["pooled"]["cost"]
    assert Fraction(pooled["main"]["known_cost"]["numerator"], pooled["main"]["known_cost"]["denominator"]) == 3 * main
    assert pooled["main_items"] == 5400 and pooled["total"]["attempts_without_token_counts"] == 3 * (main_without + twin_without)
    assert Fraction(pooled["per_alert"]["numerator"], pooled["per_alert"]["denominator"]) == main / 1800
    spread = report["spread"]["cost"]["main"]["known_cost"]
    assert spread["min"] == spread["max"] == done["reports"][ids[0]]["cost"]["main"]["known_cost"]
    assert report["mechanism_only"] == {"cost": True, "modelled_time": True}


def test_full_world_cost_per_alert_by_framing_and_by_primary_family_over_main_items(scored):
    from worldgen.truth import load_truth
    truth, alerts = load_truth(), load_alerts()
    family = lambda alert: truth[alert["id"]]["primary_family"] or "none"
    out, ids, done = scored
    expected = {("by_framing", str(framing)): (scripted_cost(alerts, [framing]), len(alerts)) for framing in FRAMINGS}
    for name in sorted({family(alert) for alert in alerts}):
        group = [alert for alert in alerts if family(alert) == name]
        expected["by_family", name] = (scripted_cost(group), 3 * len(group))
    for run_id in ids:
        cost = done["reports"][run_id]["cost"]
        assert set(cost["by_framing"]) == {"1", "2", "3"} and len(cost["by_family"]) == len(expected) - 3
        for (part, name), ((known, without), items) in expected.items():
            block = cost[part][name]
            assert block["items"] == items, (part, name)
            assert Fraction(block["cost"]["known_cost"]["numerator"], block["cost"]["known_cost"]["denominator"]) == known
            assert block["cost"]["attempts_without_token_counts"] == without
            assert Fraction(block["per_alert"]["numerator"], block["per_alert"]["denominator"]) == known / items
        total = lambda part: sum((Fraction(block["cost"]["known_cost"]["numerator"], block["cost"]["known_cost"]["denominator"])
                                  for block in cost[part].values()), Fraction(0))
        main = Fraction(cost["main"]["known_cost"]["numerator"], cost["main"]["known_cost"]["denominator"])
        assert total("by_framing") == total("by_family") == main  # main items only: twins are in neither


def test_the_index_and_the_manifest_hold_the_known_cost_of_completed_and_aborted_runs(tmp_path, monkeypatch, full_run):
    out, manifest, lines = full_run
    total, without = (a + b for a, b in zip(scripted_cost(load_alerts()), scripted_cost(load_twins())))
    entry, = json.loads(out.joinpath("index.json").read_text(encoding="utf-8"))["runs"]
    assert entry["cost"] == manifest["cost"]
    assert Fraction(entry["cost"]["known_cost"]["numerator"], entry["cost"]["known_cost"]["denominator"]) == total
    assert entry["cost"]["attempts_without_token_counts"] == without and entry["cost"]["currency"] == "USD"

    def breaking(items, model, settings, item_id):
        result, sink = fake_model.inprocess(items, model, settings, item_id)
        if item_id == "ALT-0003/1":
            raise RuntimeError("after the model was paid for")
        return result, sink

    monkeypatch.setitem(harness_run.AGENTS, "breaking", breaking)
    aborted = harness_run.run(write_config(tmp_path, agent="breaking"), tmp_path.joinpath("out"))
    spent = [one for line in lines if line["item_id"] < "ALT-0003/2" for one in line["attempts"]]
    assert aborted["state"] == "aborted" and len(spent) >= 7  # seven items were called, the last one included
    assert aborted["cost"] == money.cost(spent, PRICES) and aborted["cost"]["attempts"] == len(spent)
    entry, = json.loads(tmp_path.joinpath("out", "index.json").read_text(encoding="utf-8"))["runs"]
    assert entry["state"] == "aborted" and entry["cost"] == aborted["cost"]  # what an aborted run cost stays visible


# ---- retry, then success

def test_a_retry_that_succeeds_is_two_attempts_and_the_first_has_no_cost():
    answered = [alert for alert in load_alerts() if fake_model.outcome_of([i["id"] for i in alert["evidence"]]) == "close"][:4]
    items = [{"item_id": f"{alert['id']}/1", "alert_id": alert["id"], "framing": 1, "twin": False,
              "evidence": frame(alert, 1)} for alert in answered]
    done = []
    harness_run.hand_off(items, fake_model.inprocess, fake_model.FailsOnce(), Settings("fake-1", 0, 512, 30), done)
    for line in done:
        first, second = line["attempts"]
        assert first == {**call(None, None, None, "ProviderError"), "prompt_bytes": second["prompt_bytes"]}  # W2-02
        assert second["error"] is None and second["input_tokens"] > 0 and second["prompt_bytes"] > 0
        assert line["result"]["recommendation"] == "CLOSE" and line["result"]["system_failure"] is False
        assert line["result"]["log"]["attempts"] == 2 and len(line["result"]["log"]["attempt_log"]) == 2
        assert line["wall_s"] >= line["result"]["log"]["latency_s"] > 0  # the item's time covers both attempts
    block = money.cost([one for line in done for one in line["attempts"]], PRICES)
    assert block["attempts"] == 8 and block["attempts_without_token_counts"] == 4 and block["at_least"] is True
    assert block["known_cost"]["numerator"] > 0 and block["statement"].endswith("4 attempts without token counts")


# ---- modelled review time, against literals on the micro world

MICRO = score.figures(micro_case.lines(), micro_case.TRUTH, times=TIMES)["modelled_time"]


def decimals(block):
    return {policy: block[policy]["assisted_per_alert"]["decimal"] for policy in money.POLICIES}


def test_micro_modelled_time_for_three_sets_and_two_policies():
    """Six alerts, three of which should be escalated. Per framing the micro world gives 2, 3 and 5 escalations
    and 4, 3 and 1 closes."""
    assert MICRO["unit"] == "minutes" and MICRO["alerts"] == 6 and MICRO["escalate_alerts"] == 3
    base = MICRO["sets"]["BASE"]  # manual 5, proposal 2, L2 15, second review 2
    assert base["parameters"] == TIMES["sets"]["BASE"]  # the parameters stand beside the result
    assert base["manual_per_alert"]["decimal"] == "12.500000"  # (6 x 5 + 15 x 3) / 6
    assert decimals(base) == {"STRICT_FOUR_EYES": "11.222222", "none": "10.333333"}  # 202 / 18 and 186 / 18
    strict = base["STRICT_FOUR_EYES"]
    assert (strict["assisted_per_alert"]["numerator"], strict["assisted_per_alert"]["denominator"]) == (101, 9)
    assert {cell: value["decimal"] for cell, value in strict["by_cell"].items()} == {
        "1": "8.333333", "2": "10.500000", "3": "14.833333"}  # 50 / 6, 63 / 6, 89 / 6
    assert {cell: value["decimal"] for cell, value in base["none"]["by_cell"].items()} == {
        "1": "7.000000", "2": "9.500000", "3": "14.500000"}  # 42 / 6, 57 / 6, 87 / 6
    assert strict["lower_than_manual"] is True and base["none"]["lower_than_manual"] is True
    low = MICRO["sets"]["LOW"]  # manual 3, proposal 1, L2 10, second review 1
    assert low["manual_per_alert"]["decimal"] == "8.000000" and decimals(low) == {"STRICT_FOUR_EYES": "7.000000", "none": "6.555556"}
    high = MICRO["sets"]["HIGH"]  # manual 8, proposal 3, L2 20, second review 3
    assert high["manual_per_alert"]["decimal"] == "18.000000"
    assert decimals(high) == {"STRICT_FOUR_EYES": "15.444444", "none": "14.111111"}  # 278 / 18 and 254 / 18
    assert all(rounded["rounded"] for rounded in (base["manual_per_alert"], strict["assisted_per_alert"]))


def test_four_eyes_costs_exactly_the_second_reviews():
    for name in money.SETS:
        block, second = MICRO["sets"][name], Fraction(TIMES["sets"][name]["second_review"])
        gap = Fraction(block["STRICT_FOUR_EYES"]["assisted_per_alert"]["numerator"],
                       block["STRICT_FOUR_EYES"]["assisted_per_alert"]["denominator"]) - Fraction(
            block["none"]["assisted_per_alert"]["numerator"], block["none"]["assisted_per_alert"]["denominator"])
        assert gap == second * (4 + 3 + 1) / 18  # eight closes over three framings of six alerts


def test_the_always_escalate_flag_follows_the_worlds_own_counts():
    assert [MICRO["sets"][name]["always_escalate_beats_manual"] for name in money.SETS] == [False, False, False]
    cells = {"1": {"ESCALATE": 6, "CLOSE": 0}}
    # proposal 1 + (1 - E/N) x L2 10 against manual 5.5: with half the alerts to escalate it is 6, with 5 of 6 it is 2.67
    generous = changed(TIMES, ["sets", "BASE"], {"manual_clearing": "5.5", "proposal_review": "1", "l2": "10", "second_review": "1"})
    assert money.modelled_time(generous, cells, 6, 3)["sets"]["BASE"]["always_escalate_beats_manual"] is False
    flagged = money.modelled_time(generous, cells, 6, 5)["sets"]["BASE"]
    assert flagged["always_escalate_beats_manual"] is True and flagged["STRICT_FOUR_EYES"]["lower_than_manual"] is True
    edge = changed(TIMES, ["sets", "BASE"], {"manual_clearing": "6", "proposal_review": "1", "l2": "10", "second_review": "1"})
    assert money.modelled_time(edge, cells, 6, 3)["sets"]["BASE"]["always_escalate_beats_manual"] is False  # equal is not below


def test_a_system_failure_costs_l2_time_like_any_escalation():
    everything_fails = {place: "timeout" for place in micro_case.RESULTS}
    block = score.figures(micro_case.lines(everything_fails), micro_case.TRUTH, times=TIMES)["modelled_time"]["sets"]["BASE"]
    assert decimals(block) == {"STRICT_FOUR_EYES": "17.000000", "none": "17.000000"}  # proposal 2 + L2 15, no close at all
    assert block["STRICT_FOUR_EYES"]["lower_than_manual"] is False


# ---- modelled review time, on the full world

def test_full_world_modelled_time_per_run_and_averaged_over_the_run_set(scored):
    from worldgen.truth import load_truth
    truth = load_truth()
    out, ids, done = scored
    escalate_alerts = sum(facts["correct_action"] == "ESCALATE" for facts in truth.values() if facts["twin_of"] is None)
    assert escalate_alerts == 60
    closes = {framing: 0 for framing in FRAMINGS}
    for alert in load_alerts():
        for framing in FRAMINGS:
            ids_shown = [item["id"] for item in frame(alert, framing)]
            if fake_model.outcome_of(ids_shown) not in fake_model.FAULTS:
                closes[framing] += json.loads(fake_model.reply_text(ids_shown)).get("recommendation") == "CLOSE" \
                    if fake_model.outcome_of(ids_shown) not in ("not_json", "no_citations", "wrong_version", "close_unknown_id") else 0
    manual, proposal, l2, second = (Fraction(TIMES["sets"]["BASE"][key]) for key in money.PARAMETERS)
    expected = {framing: (600 * proposal + l2 * (600 - closes[framing]) + second * closes[framing]) / 600 for framing in FRAMINGS}
    for run_id in ids:
        block = done["reports"][run_id]["modelled_time"]
        assert block["alerts"] == 600 and block["escalate_alerts"] == 60
        base = block["sets"]["BASE"]
        assert Fraction(base["manual_per_alert"]["numerator"], base["manual_per_alert"]["denominator"]) == manual + l2 * 60 / 600
        for framing in FRAMINGS:
            cell = base["STRICT_FOUR_EYES"]["by_cell"][str(framing)]
            assert Fraction(cell["numerator"], cell["denominator"]) == expected[framing]
        average = base["STRICT_FOUR_EYES"]["assisted_per_alert"]
        assert Fraction(average["numerator"], average["denominator"]) == sum(expected.values()) / 3
    report, = done["sets"].values()
    pooled = report["pooled"]["modelled_time"]["sets"]["BASE"]["STRICT_FOUR_EYES"]
    assert len(pooled["by_cell"]) == 9 and f"{ids[0]}/1" in pooled["by_cell"]  # each run and framing, then averaged
    assert Fraction(pooled["assisted_per_alert"]["numerator"], pooled["assisted_per_alert"]["denominator"]) == sum(expected.values()) / 3
    spread = report["spread"]["modelled_time"]["sets"]["BASE"]["STRICT_FOUR_EYES"]["assisted_per_alert"]
    assert list(spread["per_run"]) == ids and spread["min"] == spread["max"] == spread["per_run"][ids[0]]
    assert report["pooled"]["modelled_time"]["sets"]["BASE"]["parameters"] == TIMES["sets"]["BASE"]


def closes_of(alert, framing):
    """Whether the fake's result for this alert in this framing is a non-failure CLOSE, counted from its rule."""
    shown = [item["id"] for item in frame(alert, framing)]
    outcome = fake_model.outcome_of(shown)
    if outcome in fake_model.FAULTS or outcome in ("not_json", "no_citations", "wrong_version", "close_unknown_id"):
        return False
    return json.loads(fake_model.reply_text(shown))["recommendation"] == "CLOSE"


def test_full_world_modelled_time_by_framing_and_by_primary_family(scored):
    from worldgen.truth import load_truth
    truth, alerts = load_truth(), load_alerts()
    family = lambda alert: truth[alert["id"]]["primary_family"] or "none"
    manual, proposal, l2, second = (Fraction(TIMES["sets"]["BASE"][key]) for key in money.PARAMETERS)

    def expected_for(group):  # (manual per alert, {framing: assisted per alert}) for these alerts
        n = len(group)
        escalate = sum(truth[alert["id"]]["correct_action"] == "ESCALATE" for alert in group)
        cells = {}
        for framing in FRAMINGS:
            closes = sum(closes_of(alert, framing) for alert in group)
            cells[str(framing)] = (n * proposal + l2 * (n - closes) + second * closes) / n
        return (n * manual + l2 * escalate) / n, cells

    value = lambda block: Fraction(block["numerator"], block["denominator"])
    out, ids, done = scored
    everything = expected_for(alerts)[1]
    groups = {name: [alert for alert in alerts if family(alert) == name] for name in {family(alert) for alert in alerts}}
    for run_id in ids:
        block = done["reports"][run_id]["modelled_time"]
        for framing in FRAMINGS:
            base = block["by_framing"][str(framing)]["sets"]["BASE"]
            assert block["by_framing"][str(framing)]["alerts"] == 600
            assert list(base["STRICT_FOUR_EYES"]["by_cell"]) == [str(framing)]
            assert value(base["STRICT_FOUR_EYES"]["assisted_per_alert"]) == everything[str(framing)]
        assert set(block["by_family"]) == set(groups)
        for name, group in groups.items():
            here = block["by_family"][name]
            manual_expected, cells = expected_for(group)
            assert here["alerts"] == len(group)
            assert value(here["sets"]["BASE"]["manual_per_alert"]) == manual_expected
            assert value(here["sets"]["BASE"]["STRICT_FOUR_EYES"]["assisted_per_alert"]) == sum(cells.values()) / 3, name
            assert here["sets"]["BASE"]["parameters"] == TIMES["sets"]["BASE"]


# ---- AC-24: the report is complete

def test_every_run_report_holds_every_metrics_figure_the_manifest_and_the_parameters(scored):
    out, ids, done = scored
    for run_id in ids:
        report = json.loads(out.joinpath(run_id, "report.json").read_text(encoding="utf-8"))
        cell = report["figures"]["overall"]
        for name in ("missed_true_matches", "ambiguous_closed", "over_escalation", "over_escalation_failures",
                     "citation_existence", "citation_accuracy", "citation_precision", "verdict_consistency", "latency"):
            assert name in cell, name  # SPEC.md Metrics, lines 127 to 133 and 137
        assert set(cell["latency"]["wall_s"]) == {"median", "p95"}
        assert report["injection"]["overall"]["divergent"] >= 0  # line 134
        assert set(report["figures"]) == {"overall", "by_framing", "by_family", "true_match_by_secondary_family"}  # line 135
        assert report["cost"]["per_alert"]["decimal"]  # line 136
        assert set(report["cost"]["by_framing"]) == {"1", "2", "3"} and report["cost"]["by_family"]  # FR-20
        assert set(report["modelled_time"]["by_framing"]) == {"1", "2", "3"} and report["modelled_time"]["by_family"]
        assert set(report["modelled_time"]["sets"]) == {"LOW", "BASE", "HIGH"}  # line 138
        assert report["manifest"]["run_id"] == run_id and report["manifest"]["price_table"]["table"] == PRICES
        assert report["manifest"]["modelled_time"]["parameters"] == TIMES  # the parameters, in the manifest
        assert all(report["modelled_time"]["sets"][name]["parameters"] == TIMES["sets"][name] for name in money.SETS)
        assert report["mechanism_only"] == {"cost": True, "modelled_time": True}
        assert {"cost", "modelled_time"} <= set(report["notes"])
