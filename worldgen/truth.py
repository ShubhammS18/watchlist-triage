"""Harness-side truth: labels, supporting evidence keys, snippet tags and twin links.

This is the only module that reads a world's hidden folder. Agent code must never import it.
"""
import json
from pathlib import Path

from . import ROOT

HIDDEN_DIR = ROOT.parent.joinpath("data", "world", "hidden")
LABEL_FIELDS = ("label", "correct_action", "primary_family", "secondary_family", "hard_case", "recipe", "injection")


def _read(folder, name):
    text = Path(folder).joinpath(name).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.split("\n") if line]


def load_snippet_tags(hidden_dir=HIDDEN_DIR):
    return {row["evidence_item_id"]: row["tag"] for row in _read(hidden_dir, "snippet_tags.jsonl")}


def load_truth(hidden_dir=HIDDEN_DIR):
    """{alert id: truth}. Covers the 600 alerts and the 15 control twins.

    A twin has the label and evidence key of the alert it copies; `twin_of` names that alert and
    `removed_evidence_item_id` the injected item the twin leaves out. For an alert, `twin` names its control twin.
    """
    keys = {row["alert_id"]: row["evidence_item_ids"] for row in _read(hidden_dir, "supporting_evidence.jsonl")}
    truth = {}
    for row in _read(hidden_dir, "labels.jsonl"):
        truth[row["alert_id"]] = {**{field: row[field] for field in LABEL_FIELDS}, "evidence_key": keys[row["alert_id"]],
                                  "twin": None, "twin_of": None, "removed_evidence_item_id": None}
    for link in _read(hidden_dir, "twin_links.jsonl"):
        original = truth[link["original_alert_id"]]
        original["twin"] = link["twin_alert_id"]
        truth[link["twin_alert_id"]] = {**original, "injection": False, "twin": None,
                                        "twin_of": link["original_alert_id"],
                                        "removed_evidence_item_id": link["removed_evidence_item_id"]}
    return truth
