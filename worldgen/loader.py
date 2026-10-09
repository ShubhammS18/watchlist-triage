"""Agent-side loader. It reads only four named files of a world's agent folder and returns the 600 alerts with
their evidence. This describes the default loader path and its allowlist; it is not a security boundary.

Labels, evidence keys and snippet tags are kept elsewhere and are never read by this module. Neither are the
control copies used by the evaluation, which only the evaluation's own module loads.
"""
import json
from pathlib import Path

from . import ROOT

AGENT_DIR = ROOT.parent.joinpath("data", "world", "agent")


AGENT_FILES = frozenset(("customers.jsonl", "watchlist.jsonl", "evidence.jsonl", "alerts.jsonl"))


def _read(folder, name):
    """Read one of the four allowed files from a folder named `agent`. Everything else is refused: any other
    file name, any path with "..", any folder not named `agent`, and any symbolic link on the way to the file."""
    folder = Path(folder)
    path = folder.joinpath(name)
    if name not in AGENT_FILES:
        raise ValueError(f"the loader does not read {name!r}")
    if ".." in folder.parts or folder.name != "agent":
        raise ValueError(f"the loader reads only a folder named agent, not {str(folder)!r}")
    if path.resolve() != path.absolute():
        raise ValueError(f"the loader does not follow symbolic links: {str(path)!r}")
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.split("\n") if line]


def bundle(alert, evidence):
    """One alert with its evidence items in order. Each item is returned without its `alert_id`."""
    result = {key: value for key, value in alert.items() if key != "evidence_item_ids"}
    result["evidence"] = [{key: value for key, value in evidence[item_id].items() if key != "alert_id"}
                          for item_id in alert["evidence_item_ids"]]
    return result


def load_alerts(agent_dir=AGENT_DIR):
    """The 600 alerts, each with its evidence items in order."""
    evidence = {item["id"]: item for item in _read(agent_dir, "evidence.jsonl")}
    return [bundle(alert, evidence) for alert in _read(agent_dir, "alerts.jsonl")]


def load_records(agent_dir=AGENT_DIR):
    """The customer and watchlist records, keyed by id, for callers that want the full records."""
    return ({r["id"]: r for r in _read(agent_dir, "customers.jsonl")},
            {r["id"]: r for r in _read(agent_dir, "watchlist.jsonl")})
