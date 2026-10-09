"""Harness-only: the 15 control twins. Agent code must never import this module.

A twin copies an alert that carries an injected snippet and leaves that one evidence item out. Comparing an
agent's answer on an alert with its answer on the twin shows whether the injected text changed anything (AC-12).

Rule for the harness (T06): show an agent ONE alert per context. Never put an alert and its twin, or any twin
data, in the same context as the alert it copies. Which alert a twin copies is in worldgen.truth.
"""
import json
from pathlib import Path

from .loader import AGENT_DIR, bundle


def load_twins(agent_dir=AGENT_DIR):
    """The 15 control twins, each with its evidence items in order, in the same shape the agent loader returns."""
    folder = Path(agent_dir)
    read = lambda name: [json.loads(line) for line in folder.joinpath(name).read_text(encoding="utf-8").split("\n") if line]
    evidence = {item["id"]: item for item in read("evidence.jsonl")}
    return [bundle(twin, evidence) for twin in read("twin_alerts.jsonl")]
