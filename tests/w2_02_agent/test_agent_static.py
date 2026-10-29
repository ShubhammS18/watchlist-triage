"""W2-02: the agent is written from the rubric, not from the generator (DEC-W2-02-RULES-FIRST). These are static checks
of the source text, and only these:
- every import statement of each module in triage_agent/ names a module on that module's list;
- no module has a name or attribute spelled importlib, __import__, exec, eval or __builtins__, and none imports
  importlib;
- no module's source holds a generator string of 20 characters or more or a note text of the frozen world.
Nothing is checked at run time, so they do not show that no import happens at run time: code that reaches an import
another way, not spelled with one of those names, is not caught. Short fragments, text put together from pieces, and
notes the generator would write on another seed are not checked either. The modules that run
in the child process keep the baseline's child rules (DEC-T05-PAYLOAD): they open no files and import only the
standard modules json and time, model_interface and the baseline's own child modules."""
import ast
import json

import pytest

from conftest import REPO

AGENT = sorted(REPO.joinpath("triage_agent").glob("*.py"))
ALLOWED = {  # module -> what it may import; a leading dot is a relative import
    "__init__.py": set(),
    "child.py": {"json", "time", "baseline_agent.agent", "baseline_agent.reply", "model_interface", ".prompt"},
    "prompt.py": {"baseline_agent.prompt"},
    "record.py": {"hashlib", "pathlib", ".prompt"},
    "recommend.py": {"copy", "time", "dataclasses", "baseline_agent.agent", "baseline_agent.payload",
                     "baseline_agent.recommend", "model_interface.runner", ".prompt", ".rules"},
    "rules.py": set(),
}
DYNAMIC = {"importlib", "__import__", "exec", "eval", "__builtins__"}
CHILD = ("__init__.py", "child.py", "prompt.py")  # triage_agent.child and what it imports
CHILD_IMPORTS = {"json", "time", "model_interface", "baseline_agent.agent", "baseline_agent.reply",
                 "baseline_agent.prompt", "prompt"}  # "prompt": the relative import of .prompt
FILE_NAMES = {"open", "__import__", "eval", "exec", "read_text", "write_text", "read_bytes", "write_bytes"}
TEMPLATES = (REPO.joinpath("worldgen", "snippets.py"), REPO.joinpath("framings", "wording.py"))


def imports(source, relative="."):
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            found.append(relative * node.level + (node.module or ""))
    return found


def problems(source, allowed):
    """What breaks the import rule in one module's source: an import not in `allowed`, or a name or attribute spelled
    as one of DYNAMIC."""
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    return sorted(set(imports(source)) - allowed) + sorted((names | set(imports(source))) & DYNAMIC)


def test_every_agent_module_imports_only_its_listed_modules_and_names_no_dynamic_import():
    assert {path.name for path in AGENT} == set(ALLOWED)
    for path in AGENT:
        assert problems(path.read_text(encoding="utf-8"), ALLOWED[path.name]) == [], path.name


@pytest.mark.parametrize("source", [
    "import worldgen", "from worldgen import snippets", "from framings.wording import X", "import json, os",
    "import importlib", "importlib.import_module('worldgen')", "__import__('worldgen')", "exec('import worldgen')",
    "eval('1')", "import builtins\nbuiltins.__import__('worldgen')", "from importlib import import_module",
    "getattr(__builtins__, '__im' + 'port__')('worldgen')", "__builtins__['__import__']('worldgen')",
])
def test_the_import_rule_catches_each_static_case_it_names(source):
    assert problems(source, {"json"}) != []


def test_the_child_modules_open_no_files_and_import_only_what_the_child_may():
    for path in AGENT:
        if path.name not in CHILD:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert set(imports(path.read_text(encoding="utf-8"), relative="")) <= CHILD_IMPORTS, path.name
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
