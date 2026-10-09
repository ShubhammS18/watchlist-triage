"""Shared fixtures: the committed world in data/world, loaded once per test run."""
import json

import pytest

from worldgen import ROOT

WORLD_DIR = ROOT.parent.joinpath("data", "world")
TABLES = {
    "customers": "agent/customers.jsonl",
    "watchlist": "agent/watchlist.jsonl",
    "evidence": "agent/evidence.jsonl",
    "alerts": "agent/alerts.jsonl",
    "twins": "agent/twin_alerts.jsonl",
    "labels": "hidden/labels.jsonl",
    "keys": "hidden/supporting_evidence.jsonl",
    "tags": "hidden/snippet_tags.jsonl",
    "links": "hidden/twin_links.jsonl",
}


def load_world(world_dir):
    """{table name: list of records} for a world folder."""
    def read(relative):
        text = world_dir.joinpath(*relative.split("/")).read_text(encoding="utf-8")
        return [json.loads(line) for line in text.split("\n") if line]

    return {name: read(path) for name, path in TABLES.items()}


def index_by_alert(world):
    """Per alert id: its evidence items, planted label record, key and snippet tags."""
    evidence = {e["id"]: e for e in world["evidence"]}
    label = {r["alert_id"]: r for r in world["labels"]}
    key = {r["alert_id"]: r["evidence_item_ids"] for r in world["keys"]}
    tag = {t["evidence_item_id"]: t["tag"] for t in world["tags"]}
    return {
        a["id"]: {"alert": a, "items": [evidence[i] for i in a["evidence_item_ids"]], "label": label[a["id"]],
                  "key": key[a["id"]], "tags": tag}
        for a in world["alerts"]
    }


@pytest.fixture(scope="session")
def world():
    return load_world(WORLD_DIR)


@pytest.fixture(scope="session")
def by_alert(world):
    return index_by_alert(world)
