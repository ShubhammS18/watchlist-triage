"""The static test of the workflow (DEC-W2-04-CHOICES). There is no YAML library here, so the workflow is kept flat
and checked line by line after comments are removed. Anything the rules do not recognise fails. Each rule is also
shown to catch a bad workflow."""
import re
from itertools import takewhile

import pytest

from drift_common import COMMAND, WORKFLOWS

TOP_LEVEL = ["name", "on", "permissions", "jobs"]
ON = "on: [push, pull_request]"            # every push and pull request: no filters, never pull_request_target
PINNED_ACTION = re.compile(r"actions/checkout@[0-9a-f]{40}")


def lines_of(text):
    """The workflow's lines without comments or blank lines, indentation kept."""
    stripped = (re.sub(r"(^|\s)#.*$", "", line).rstrip() for line in text.split("\n"))
    return [line for line in stripped if line]


def values(lines, key):
    """The value of every `key:` line at any indentation, a leading list dash allowed."""
    pattern = re.compile(rf"^\s*(- )?{re.escape(key)}:(.*)$")
    return [match.group(2).strip() for match in map(pattern.match, lines) if match]


def workflow_problems(text):
    lines = lines_of(text)
    found = []
    top = [line.split(":")[0] for line in lines if not line.startswith(" ")]
    if top != TOP_LEVEL:
        found.append(f"top-level keys are {top}, not {TOP_LEVEL}")
    if ON not in lines:
        found.append(f"the trigger line is not exactly {ON!r}")
    if values(lines, "permissions") != [""] or "permissions:" not in lines:
        found.append("there must be one permissions block, at the top level")
    else:
        block = list(takewhile(lambda line: line.startswith(" "), lines[lines.index("permissions:") + 1:]))
        if [line.strip() for line in block] != ["contents: read"]:
            found.append(f"permissions are {block}, not only 'contents: read'")
    if values(lines, "runs-on") != ["ubuntu-24.04"]:
        found.append(f"runs-on is {values(lines, 'runs-on')}, not one job on ubuntu-24.04")
    timeouts = values(lines, "timeout-minutes")
    if len(timeouts) != 1 or not timeouts[0].isdigit() or not 1 <= int(timeouts[0]) <= 5:
        found.append(f"timeout-minutes is {timeouts}, not one limit of at most 5")
    uses = values(lines, "uses")
    if len(uses) != 1 or not PINNED_ACTION.fullmatch(uses[0]):
        found.append(f"actions used are {uses}, not only actions/checkout pinned to a full commit SHA")
    if values(lines, "persist-credentials") != ["false"]:
        found.append("the checkout does not set persist-credentials: false")
    if values(lines, "run") != [COMMAND]:
        found.append(f"run steps are {values(lines, 'run')}, not only {COMMAND!r}")
    for needle in ("secrets", "${{", "pull_request_target", "workflow_run"):
        if needle in text:
            found.append(f"{needle!r} appears in the workflow")
    return found


def the_workflow():
    files = sorted(path.name for path in WORKFLOWS.iterdir())
    assert files == ["world-drift.yml"], files
    return WORKFLOWS.joinpath("world-drift.yml").read_text(encoding="utf-8")


def test_the_workflow_triggers_on_push_and_pull_request_and_runs_the_gate_command():
    assert workflow_problems(the_workflow()) == []


def test_comments_are_ignored_but_a_hash_inside_a_value_is_kept():
    assert lines_of("a: 1  # note\n# whole line\n  b: x#y\n") == ["a: 1", "  b: x#y"]


BAD = [
    ("on: [push, pull_request]", "on: [push]", "the trigger line"),
    ("on: [push, pull_request]", "on: [push, pull_request_target]", "'pull_request_target' appears"),
    ("on: [push, pull_request]", "on:\n  push:\n    branches: [main]\n  pull_request:", "the trigger line"),
    ("  contents: read", "  contents: write", "permissions are"),
    ("  contents: read", "  contents: read\n  actions: write", "permissions are"),
    ("permissions:\n  contents: read\n", "", "one permissions block"),
    ("    runs-on: ubuntu-24.04", "    runs-on: ubuntu-24.04\n    permissions: write-all", "one permissions block"),
    ("runs-on: ubuntu-24.04", "runs-on: ubuntu-latest", "runs-on is"),
    ("    timeout-minutes: 5\n", "", "timeout-minutes is"),
    ("timeout-minutes: 5", "timeout-minutes: 360", "timeout-minutes is"),
    ("@3d3c42e5aac5ba805825da76410c181273ba90b1", "@v7.0.1", "actions used are"),
    ("      - run: python3", "      - uses: actions/setup-python@" + "0" * 40 + "\n      - run: python3",
     "actions used are"),
    ("          persist-credentials: false", "          persist-credentials: true", "persist-credentials"),
    ("      - run: python3 tools/check_world_drift.py", "      - run: python3 tools/other.py", "run steps are"),
    ("      - run: python3 tools/check_world_drift.py",
     "      - run: pip install pyyaml\n      - run: python3 tools/check_world_drift.py", "run steps are"),
    ("      - run: python3 tools/check_world_drift.py",
     "      - run: python3 tools/check_world_drift.py\n        env:\n          KEY: ${{ secrets.KEY }}", "'secrets'"),
    ("name: world drift\n", "name: world drift\nenv:\n  X: 1\n", "top-level keys"),
]


@pytest.mark.parametrize("old, new, expected", BAD, ids=[f"bad-{n}" for n in range(len(BAD))])
def test_each_rule_catches_a_bad_workflow(old, new, expected):
    text = the_workflow()
    assert text.count(old) == 1, old
    found = workflow_problems(text.replace(old, new))
    assert any(expected in problem for problem in found), found
