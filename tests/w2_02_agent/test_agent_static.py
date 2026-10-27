"""W2-02: the agent is written from the rubric, not from the generator (DEC-W2-02-RULES-FIRST). It imports nothing from
the generator or the framings, and its source holds none of the generator's snippet or wording text."""
import ast
import json

from conftest import REPO

AGENT = sorted(REPO.joinpath("triage_agent").glob("*.py"))
FORBIDDEN = ("worldgen", "framings")
TEMPLATES = (REPO.joinpath("worldgen", "snippets.py"), REPO.joinpath("framings", "wording.py"))


def imports(path):
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            found.append(node.module or "")
    return found


def test_the_agent_imports_nothing_from_the_generator_or_the_framings():
    assert {path.name for path in AGENT} == {"__init__.py", "recommend.py", "rules.py"}
    for path in AGENT:
        assert not [name for name in imports(path) if name.split(".")[0] in FORBIDDEN], path.name


def test_the_agent_holds_no_generator_snippet_or_wording_text():
    texts = {node.value.strip().lower() for path in TEMPLATES
             for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
             if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value.strip()) >= 20}
    evidence = REPO.joinpath("data", "world", "agent", "evidence.jsonl").read_text(encoding="utf-8").split("\n")
    texts |= {item["value"].strip().lower() for item in map(json.loads, filter(None, evidence)) if item["kind"] == "snippet"}
    assert len(texts) > 100
    for path in AGENT:
        source = path.read_text(encoding="utf-8").lower()
        assert not [text for text in texts if text in source], path.name
