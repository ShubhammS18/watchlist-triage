"""Seed sweep (review round 2): worlds built from other seeds must pass the same checks as the committed one.

Each world is written to a temp folder outside the repo and read back from disk.
"""
from collections import Counter
from datetime import date

import pytest

from checks import check_evidence_matches_records, check_labels, check_schema, check_twins
from conftest import index_by_alert, load_world
from leak_tables import ADDRESS, GROUP_SIZES, NAME_FORMS, SNIPPET_COUNTS, largest_gap, tables
from text_adjudicator import label_from_text
from worldgen import ROOT, load_config
from worldgen.build import generate, write
from worldgen.matcher import load_titles, match_all
from worldgen.plan import FAMILIES, HARD_FAMILIES
from worldgen.snippets import INJECTED_TEXTS

SEEDS = (1, 42, 20260931)
AS_OF = date.fromisoformat(load_config()["as_of_date"])
LABELS = ("TRUE_MATCH", "AMBIGUOUS_BY_DESIGN", "CLEAR_FALSE_POSITIVE")


@pytest.fixture(scope="module", params=SEEDS)
def swept(request, tmp_path_factory):
    folder = tmp_path_factory.mktemp(f"seed-{request.param}")
    assert ROOT.parent not in folder.parents and folder != ROOT.parent          # outside the repo
    files, summary = generate(request.param)
    write(files, folder)
    world = load_world(folder)
    return {"dir": folder, "world": world, "by_alert": index_by_alert(world), "summary": summary}


def test_counts(swept):
    world = swept["world"]
    assert swept["summary"]["alerts"] == swept["summary"]["matcher_alerts"] == 600
    assert (len(world["customers"]), len(world["watchlist"]), len(world["twins"])) == (800, 720, 15)
    assert Counter(r["label"] for r in world["labels"]) == {"TRUE_MATCH": 30, "AMBIGUOUS_BY_DESIGN": 30, "CLEAR_FALSE_POSITIVE": 540}
    for label in LABELS[:2]:
        assert Counter(r["primary_family"] for r in world["labels"] if r["label"] == label) == {f: 6 for f in FAMILIES}
    cfp = Counter(r["primary_family"] for r in world["labels"] if r["label"] == "CLEAR_FALSE_POSITIVE")
    assert cfp == {**{f: 30 for f in HARD_FAMILIES}, None: 420}
    planted = sorted((a["customer_id"], a["watchlist_entry_id"]) for a in world["alerts"])
    assert match_all(world["customers"], world["watchlist"], load_titles()) == planted


def test_labels_follow_from_the_rules_on_records_and_evidence(swept):
    check_schema(swept["world"])
    check_evidence_matches_records(swept["world"])
    assert check_labels(swept["world"]) == 600
    check_twins(swept["world"])


def test_balance(swept):
    t = tables(swept["dir"])
    for name, categories in (("address", ADDRESS), ("name_form", NAME_FORMS), ("group_size", GROUP_SIZES),
                             ("snippet_count", SNIPPET_COUNTS)):
        assert largest_gap(t[name], categories) == 0, name


def test_each_injected_text_appears_exactly_once_per_label(swept):
    seen = Counter()
    for data in swept["by_alert"].values():
        seen.update((data["label"]["label"], i["value"]) for i in data["items"] if data["tags"].get(i["id"]) == "injection")
    assert seen == {(label, text): 1 for label in LABELS for _, text in INJECTED_TEXTS}


def test_the_text_adjudicator_agrees_with_all_600_planted_labels(swept):
    titles = load_titles()
    wrong = [(alert_id, d["label"]["label"]) for alert_id, d in swept["by_alert"].items()
             if label_from_text(d["items"], AS_OF, titles) != d["label"]["label"]]
    assert wrong == [] and len(swept["by_alert"]) == 600
