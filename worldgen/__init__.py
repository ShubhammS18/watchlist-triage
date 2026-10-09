"""Synthetic watchlist world generator for task T02. Python standard library only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_config():
    return json.loads(ROOT.joinpath("config.json").read_text(encoding="utf-8"))


def load_names(filename):
    """Name parts from worldgen/names/<filename>, one per line, in file order."""
    text = ROOT.joinpath("names", filename).read_text(encoding="utf-8")
    return [line for line in text.split("\n") if line]
