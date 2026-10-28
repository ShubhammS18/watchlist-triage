"""W2-02: the agent is written from the rubric, not from the generator (DEC-W2-02-RULES-FIRST). It imports nothing from
the generator or the framings, and its source holds none of the generator's snippet or wording text. The modules that
run in the child process keep the baseline's child rules (DEC-T05-PAYLOAD): they open no files and import only the
standard modules json and time, model_interface and the baseline's own child modules."""
import ast
import json

from conftest import REPO

AGENT = sorted(REPO.joinpath("triage_agent").glob("*.py"))
FORBIDDEN = ("worldgen", "framings")
CHILD = ("__init__.py", "child.py", "prompt.py")  # triage_agent.child and what it imports
CHILD_IMPORTS = {"json", "time", "model_interface", "baseline_agent.agent", "baseline_agent.reply",
                 "baseline_agent.prompt", "prompt"}  # "prompt": the relative import of .prompt
FILE_NAMES = {"open", "__import__", "eval", "exec", "read_text", "write_text", "read_bytes", "write_bytes"}
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
    assert {path.name for path in AGENT} == {"__init__.py", "child.py", "prompt.py", "record.py", "recommend.py", "rules.py"}
    for path in AGENT:
        assert not [name for name in imports(path) if name.split(".")[0] in FORBIDDEN], path.name


def test_the_child_modules_open_no_files_and_import_only_what_the_child_may():
    for path in AGENT:
        if path.name not in CHILD:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert set(imports(path)) <= CHILD_IMPORTS, path.name
        used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        used |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        assert not used & FILE_NAMES, path.name
    init = ast.parse(REPO.joinpath("triage_agent", "__init__.py").read_text(encoding="utf-8"))
    assert len(init.body) == 1 and isinstance(init.body[0].value, ast.Constant)  # only its docstring


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
