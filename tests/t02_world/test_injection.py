"""Injection alerts and their control twins (FR-3), checked on the committed world."""
from collections import Counter
from datetime import date

from checks import check_twins
from worldgen import load_config
from worldgen.harness_twins import load_twins
from worldgen.plan import FAMILIES, HARD_FAMILIES
from worldgen.rubric_check import adjudicate
from worldgen.snippets import INJECTED_TEXTS, INJECTION_PLAN
from worldgen.truth import load_truth

AS_OF = date.fromisoformat(load_config()["as_of_date"])
KIND_OF = {text: kind for kind, text in INJECTED_TEXTS}
LABELS = ("TRUE_MATCH", "AMBIGUOUS_BY_DESIGN", "CLEAR_FALSE_POSITIVE")


def injection_alerts(by_alert):
    return {alert_id: d for alert_id, d in by_alert.items() if d["label"]["injection"]}


def injected_items(data):
    return [i for i in data["items"] if data["tags"].get(i["id"]) == "injection"]


def test_the_library_has_five_texts_three_close_one_escalate_one_reveal():
    texts = [text for _, text in INJECTED_TEXTS]
    assert len(texts) == 5 and len(set(texts)) == len(texts)
    assert Counter(kind for kind, _ in INJECTED_TEXTS) == {"close": 3, "escalate": 1, "reveal": 1}
    assert all(5 <= len(text.split()) < 25 for text in texts)


def test_the_plan_gives_every_label_every_text_exactly_once():
    assert set(INJECTION_PLAN) == set(LABELS)
    for plan in INJECTION_PLAN.values():
        assert sorted(plan) == [0, 1, 2, 3, 4]
    assert len(set(INJECTION_PLAN.values())) == 3                     # the order differs by label


def test_each_injected_text_appears_exactly_once_per_label(by_alert):
    """Review round 2: the exact wording must not predict the label, so every label carries every text once."""
    seen = Counter()
    for data in injection_alerts(by_alert).values():
        seen[(data["label"]["label"], injected_items(data)[0]["value"])] += 1
    assert seen == {(label, text): 1 for label in LABELS for _, text in INJECTED_TEXTS}


def test_there_are_15_injection_alerts_five_per_label(by_alert):
    found = injection_alerts(by_alert)
    assert len(found) == 15
    assert Counter(d["label"]["label"] for d in found.values()) == {label: 5 for label in LABELS}


def test_injection_alerts_are_spread_over_the_families(by_alert):
    spread = Counter((d["label"]["label"], d["label"]["primary_family"]) for d in injection_alerts(by_alert).values())
    expected = {("TRUE_MATCH", f): 1 for f in FAMILIES}
    expected.update({("AMBIGUOUS_BY_DESIGN", f): 1 for f in FAMILIES})
    expected.update({("CLEAR_FALSE_POSITIVE", f): 1 for f in HARD_FAMILIES})
    expected[("CLEAR_FALSE_POSITIVE", None)] = 1                      # the plain one
    assert spread == expected


def test_the_direction_of_the_injected_text_is_identical_across_labels(by_alert):
    """Review finding: the wording must not predict the label. Every label gets 3 close-directed and 2 other texts."""
    direction = {label: Counter() for label in LABELS}
    kinds = {label: Counter() for label in LABELS}
    used = set()
    for data in injection_alerts(by_alert).values():
        text = injected_items(data)[0]["value"]
        used.add(text)
        kinds[data["label"]["label"]][KIND_OF[text]] += 1
        direction[data["label"]["label"]]["close" if KIND_OF[text] == "close" else "other"] += 1
    assert all(direction[label] == {"close": 3, "other": 2} for label in LABELS), direction
    assert direction["TRUE_MATCH"] == direction["AMBIGUOUS_BY_DESIGN"] == direction["CLEAR_FALSE_POSITIVE"]
    assert all(kinds[label] == {"close": 3, "escalate": 1, "reveal": 1} for label in LABELS)
    assert used == set(KIND_OF)                                       # every library text is used


def test_each_injection_alert_has_one_extra_item_holding_only_the_injected_text(by_alert, world):
    tagged = [t for t in world["tags"] if t["tag"] == "injection"]
    assert len(tagged) == 15
    for data in injection_alerts(by_alert).values():
        items = injected_items(data)
        assert len(items) == 1
        item = items[0]
        assert item["kind"] == "snippet" and item["value"] in KIND_OF            # exactly a library text, nothing else
        others = [i for i in data["items"] if i["kind"] == "snippet" and i["id"] != item["id"]]
        assert others, "an injection alert must already carry another snippet"
        assert item["id"] not in data["key"]
    assert not [d for d in by_alert.values() if not d["label"]["injection"] and injected_items(d)]


def test_the_injected_item_sits_at_varied_positions_not_always_last(by_alert):
    positions, from_end, last = [], [], 0
    for data in injection_alerts(by_alert).values():
        ids = data["alert"]["evidence_item_ids"]
        index = ids.index(injected_items(data)[0]["id"])
        positions.append(index)
        from_end.append(len(ids) - 1 - index)
        last += index == len(ids) - 1
    assert len(set(positions)) >= 3 and len(set(from_end)) >= 3, (positions, from_end)
    assert last < 8, "the injected item is last too often"
    assert min(positions) <= 2 and max(from_end) >= 4                 # it also appears near the start


def test_evidence_ids_inside_an_alert_are_consecutive_even_with_an_injected_item(by_alert):
    for data in by_alert.values():
        numbers = [int(i.split("-")[1]) for i in data["alert"]["evidence_item_ids"]]
        assert numbers == list(range(numbers[0], numbers[0] + len(numbers)))


def test_the_injection_tag_has_no_effect_on_the_label(by_alert):
    for data in injection_alerts(by_alert).values():
        planted = data["label"]
        with_item = adjudicate(data["items"], data["tags"], AS_OF, data["key"])
        rest = [i for i in data["items"] if data["tags"].get(i["id"]) != "injection"]
        without_item = adjudicate(rest, data["tags"], AS_OF, data["key"])
        assert with_item == without_item and with_item[0] == planted["label"]


def test_every_twin_equals_its_original_except_for_the_injected_item(world, by_alert):
    check_twins(world)
    twins, links = world["twins"], {l["twin_alert_id"]: l for l in world["links"]}
    assert [t["id"] for t in twins] == [f"TWN-{n:02d}" for n in range(1, 16)]
    assert len(world["alerts"]) == 600 and not {t["id"] for t in twins} & set(by_alert)       # outside the 600
    assert {l["original_alert_id"] for l in links.values()} == set(injection_alerts(by_alert))
    for twin in twins:
        original = by_alert[links[twin["id"]]["original_alert_id"]]["alert"]
        assert len(twin["evidence_item_ids"]) == len(original["evidence_item_ids"]) - 1


def test_a_twin_has_a_gap_in_its_evidence_ids_where_the_item_was_removed(world):
    """A stated limit, pinned here so it is not forgotten: the gap is visible unless the removed item was first or last."""
    gaps = 0
    for twin in world["twins"]:
        numbers = [int(i.split("-")[1]) for i in twin["evidence_item_ids"]]
        gaps += numbers != list(range(numbers[0], numbers[0] + len(numbers)))
    assert gaps >= 8


def test_twins_have_the_label_and_key_of_their_original(world, by_alert):
    truth = load_truth()
    evidence = {e["id"]: e for e in world["evidence"]}
    assert len(truth) == 615
    for twin in world["twins"]:
        mine = truth[twin["id"]]
        original = truth[mine["twin_of"]]
        assert truth[mine["twin_of"]]["twin"] == twin["id"] and original["injection"] and not mine["injection"]
        for field in ("label", "correct_action", "primary_family", "secondary_family", "hard_case", "recipe", "evidence_key"):
            assert mine[field] == original[field], field
        assert set(mine["evidence_key"]) <= set(twin["evidence_item_ids"])
        items = [evidence[i] for i in twin["evidence_item_ids"]]
        tags = by_alert[mine["twin_of"]]["tags"]
        assert adjudicate(items, tags, AS_OF, mine["evidence_key"])[:2] == (mine["label"], mine["correct_action"])


def test_the_harness_module_returns_the_15_twins_in_the_loader_shape(world):
    twins = load_twins()
    by_id = {t["id"]: t for t in world["twins"]}
    assert [t["id"] for t in twins] == [f"TWN-{n:02d}" for n in range(1, 16)]
    for twin in twins:
        assert [i["id"] for i in twin["evidence"]] == by_id[twin["id"]]["evidence_item_ids"]
        assert all("alert_id" not in item for item in twin["evidence"])
