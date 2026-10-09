"""Static checks over worldgen/: no clock, no random module, no floats."""
import ast
import json

import pytest

from worldgen import ROOT

SOURCES = sorted(ROOT.glob("*.py"))
FORBIDDEN_IMPORTS = {"random", "time", "uuid", "secrets"}
FORBIDDEN_ATTRIBUTES = {"now", "today", "utcnow", "urandom"}


def violations(path):
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found += [f"import {a.name}" for a in node.names if a.name.split(".")[0] in FORBIDDEN_IMPORTS]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in FORBIDDEN_IMPORTS:
            found.append(f"from {node.module} import ...")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRIBUTES:
            found.append(f".{node.attr}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, float):
            found.append(f"float literal {node.value}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float":
            found.append("float(...)")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            found.append("true division '/'")
    return found


def test_there_are_sources_to_check():
    assert {p.name for p in SOURCES} >= {"rng.py", "textutil.py", "matcher.py", "pepdates.py", "validate.py"}


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_random_module_wall_clock_or_floats(path):
    assert violations(path) == []


def test_the_checker_itself_catches_each_forbidden_construct(tmp_path):
    bad = tmp_path.joinpath("bad.py")
    bad.write_text("import random\nimport time\nfrom datetime import datetime\n"
                   "x = datetime.now()\ny = time.time()\nz = 1.5\nw = float(3)\nv = 3 / 2\n", encoding="utf-8")
    found = violations(bad)
    for needle in ("import random", "import time", ".now", "float literal 1.5", "float(...)", "true division '/'"):
        assert needle in found, (needle, found)


@pytest.mark.parametrize("path", [ROOT.joinpath("config.json"), ROOT.joinpath("schema", "world.schema.json")],
                         ids=lambda p: p.name)
def test_json_files_contain_no_floats(path):
    def refuse(text):
        raise AssertionError(f"float {text} in {path.name}")

    json.loads(path.read_text(encoding="utf-8"), parse_float=refuse)


def test_config_holds_the_decided_values():
    from worldgen import load_config

    config = load_config()
    assert (config["seed"], config["as_of_date"], config["id_prefix"]) == (20260930, "2026-09-30", "SYN-")
    counts = config["counts"]
    assert counts["alerts"] == 600
    assert counts["labels"] == {"TRUE_MATCH": 30, "AMBIGUOUS_BY_DESIGN": 30, "CLEAR_FALSE_POSITIVE": 540}
    assert sum(counts["labels"].values()) == counts["alerts"]
    assert counts["true_match_per_primary_family"] * len(counts["families"]) == counts["labels"]["TRUE_MATCH"]
    assert counts["ambiguous_per_family"] * len(counts["families"]) == counts["labels"]["AMBIGUOUS_BY_DESIGN"]
    hard = counts["clear_false_positive_hard_per_family"] * len(counts["clear_false_positive_hard_families"])
    assert hard + counts["clear_false_positive_plain"] == counts["labels"]["CLEAR_FALSE_POSITIVE"]
    assert "contradictory_evidence" not in counts["clear_false_positive_hard_families"]
    assert counts["injection_per_label"] * len(counts["labels"]) == 15
