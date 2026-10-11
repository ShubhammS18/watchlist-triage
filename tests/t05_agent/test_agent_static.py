"""T05: the agent code that runs in the child process opens no files (DEC-T05-PAYLOAD, towards FR-9).

A static check of the source of every baseline_agent module the child imports. It reads the syntax tree; it does
not run the code. It covers the agent's own modules only, not model_interface, whose start-up script is the T04
guard. It finds plain uses; it would not find a file opened through a name built at run time.
"""
import ast
from pathlib import Path

import pytest

import baseline_agent

PACKAGE = Path(baseline_agent.__file__).resolve().parent
CHILD_MODULES = ("__init__", "agent", "reply", "payload", "prompt")  # recommend.py is the parent side
ALLOWED_IMPORTS = {"json", "time", "model_interface"}
NAMED_BY_THE_OWNER = {"os", "shutil", "socket", "subprocess", "ctypes", "io", "pathlib"}
FILE_NAMES = {"open", "__import__", "eval", "exec"}
FILE_ATTRIBUTES = {"open", "read_text", "write_text", "read_bytes", "write_bytes"}


def problems(source):
    """Every import outside the allowlist and every use of a file-opening name, as text."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [f"import {alias.name}" for alias in node.names if alias.name not in ALLOWED_IMPORTS]
        elif isinstance(node, ast.ImportFrom) and node.level:
            wanted = [node.module] if node.module else [alias.name for alias in node.names]
            found += [f"relative import of {name}" for name in wanted if name not in CHILD_MODULES]
        elif isinstance(node, ast.ImportFrom) and node.module not in ALLOWED_IMPORTS:
            found.append(f"from {node.module} import")
        elif isinstance(node, ast.Name) and node.id in FILE_NAMES:
            found.append(f"name {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in FILE_ATTRIBUTES:
            found.append(f"attribute .{node.attr}")
    return found


def test_no_module_that_runs_in_the_child_touches_files_or_imports_outside_the_allowlist():
    assert not ALLOWED_IMPORTS & NAMED_BY_THE_OWNER
    found = {name: problems(PACKAGE.joinpath(f"{name}.py").read_text(encoding="utf-8")) for name in CHILD_MODULES}
    assert not {name: lines for name, lines in found.items() if lines}


def test_the_checked_modules_are_the_package_minus_the_parent_side():
    assert {path.stem for path in PACKAGE.glob("*.py")} == {*CHILD_MODULES, "recommend"}


@pytest.mark.parametrize("source", [
    "open('x')",
    "f = open",
    "import io\nio.open('x')",
    "import io",
    "from pathlib import Path",
    "import pathlib",
    "p.read_text()",
    "p.write_text('x')",
    "p.read_bytes()",
    "p.write_bytes(b'x')",
    "p.open()",
    "import os",
    "import os.path",
    "from os import path",
    "import shutil",
    "import socket",
    "import subprocess",
    "import ctypes",
    "import json, os",
    "from model_interface.runner import run_child",
    "from .recommend import recommend",
    "from . import recommend",
    "__import__('os')",
    "exec('import os')",
    "def f():\n    import importlib",
])
def test_the_checker_itself_catches_each_forbidden_construct(source):
    assert problems(source)


def test_the_checker_passes_what_the_agent_needs():
    assert not problems("import json\nimport time\nfrom model_interface import Request\nfrom .reply import parse_reply\n"
                        "from . import payload\njson.loads('1')\ntime.monotonic()\n")
