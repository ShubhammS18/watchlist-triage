"""Isolation by code path: the agent loader reads only the alert files in agent/; worldgen.truth is the only
reader of the hidden folder; worldgen.harness_twins is the only reader of the control twins."""
import ast
import sys

import pytest

from conftest import WORLD_DIR
from worldgen import ROOT
from worldgen.build import generate
from worldgen.harness_twins import load_twins
from worldgen import loader
from worldgen.loader import load_alerts, load_records
from worldgen.truth import load_snippet_tags, load_truth

HIDDEN_FIELD_NAMES = {"label", "correct_action", "primary_family", "secondary_family", "hard_case", "recipe", "tag",
                      "injection", "evidence_key", "twin_of", "original_alert_id", "removed_evidence_item_id"}
_opened, _recording = [], [False]


def _audit(event, args):
    if _recording[0] and event == "open":
        _opened.append(str(args[0]))


sys.addaudithook(_audit)            # an audit hook sees every file the interpreter opens, however it is opened


def opened_while(call):
    del _opened[:]
    _recording[0] = True
    try:
        result = call()
    finally:
        _recording[0] = False
    return result, list(_opened)


def keys_in(value):
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in keys_in(v)}
    if isinstance(value, list):
        return {k for v in value for k in keys_in(v)}
    return set()


def imports_of(module_name):
    tree = ast.parse(ROOT.joinpath(module_name).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(("." * node.level) + (node.module or ""))
            names |= {alias.name for alias in node.names}
    return names


def test_the_loader_source_never_mentions_the_hidden_folder_the_truth_module_or_the_twins():
    source = ROOT.joinpath("loader.py").read_text(encoding="utf-8").lower()
    for word in ("hidden", "truth", "twin", "harness"):
        assert word not in source, word


def test_the_loader_imports_only_the_standard_library_and_the_package_root():
    assert imports_of("loader.py") == {"json", "pathlib", "Path", ".", "ROOT"}


def test_the_audit_hook_really_sees_file_opens():
    _, paths = opened_while(lambda: WORLD_DIR.joinpath("README.md").read_text(encoding="utf-8"))
    assert any(p.endswith("README.md") for p in paths)


def test_the_loader_opens_only_alert_files_in_the_agent_folder_and_never_the_twin_file():
    def everything():
        return load_alerts(), load_records()

    _, paths = opened_while(everything)
    agent = str(WORLD_DIR.joinpath("agent"))
    assert paths and all(p.startswith(agent) for p in paths), paths
    assert {p.rsplit("/", 1)[1] for p in paths} == {"alerts.jsonl", "evidence.jsonl", "customers.jsonl", "watchlist.jsonl"}
    assert not [p for p in paths if "hidden" in p or "twin" in p]


# ---- the read helper's allowlist (review round 2)
AGENT = WORLD_DIR.joinpath("agent")


def test_the_read_helper_accepts_exactly_the_four_alert_files():
    assert loader.AGENT_FILES == {"customers.jsonl", "watchlist.jsonl", "evidence.jsonl", "alerts.jsonl"}
    assert [len(loader._read(AGENT, name)) for name in sorted(loader.AGENT_FILES)] == [600, 800, 5589, 720]


@pytest.mark.parametrize("name", ["twin_alerts.jsonl", "../hidden/labels.jsonl", "../README.md", "../agent/alerts.jsonl",
                                  "labels.jsonl", "", "alerts.jsonl/", "./alerts.jsonl"])
def test_the_read_helper_refuses_every_other_file_name(name):
    _, paths = opened_while(lambda: pytest.raises(ValueError, loader._read, AGENT, name))
    assert paths == []                                                # refused before anything is opened


@pytest.mark.parametrize("folder", [WORLD_DIR.joinpath("hidden"), WORLD_DIR, WORLD_DIR.joinpath("agent", "..", "hidden"),
                                    WORLD_DIR.joinpath("hidden", "..", "agent"), WORLD_DIR.joinpath("agent", "..", "agent")])
def test_the_read_helper_refuses_other_folders_and_any_dot_dot(folder):
    _, paths = opened_while(lambda: pytest.raises(ValueError, loader._read, folder, "alerts.jsonl"))
    assert paths == []
    with pytest.raises(ValueError):
        load_alerts(folder)


def test_the_read_helper_refuses_a_symlinked_file(tmp_path):
    """The review's redirect: a folder named agent whose alerts.jsonl is a link to the control copies."""
    fake = tmp_path.joinpath("agent")
    fake.mkdir()
    fake.joinpath("evidence.jsonl").write_bytes(AGENT.joinpath("evidence.jsonl").read_bytes())
    fake.joinpath("alerts.jsonl").symlink_to(AGENT.joinpath("twin_alerts.jsonl"))
    with pytest.raises(ValueError, match="symbolic"):
        load_alerts(fake)
    with pytest.raises(ValueError, match="symbolic"):
        loader._read(fake, "alerts.jsonl")


def test_the_read_helper_refuses_a_symlinked_folder(tmp_path):
    link = tmp_path.joinpath("agent")
    link.symlink_to(AGENT, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic"):
        load_alerts(link)
    nested = tmp_path.joinpath("elsewhere")
    nested.symlink_to(WORLD_DIR, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic"):
        loader._read(nested.joinpath("agent"), "alerts.jsonl")


def test_a_real_copy_of_the_agent_folder_still_loads(tmp_path):
    copy = tmp_path.joinpath("agent")
    copy.mkdir()
    for name in loader.AGENT_FILES:
        copy.joinpath(name).write_bytes(AGENT.joinpath(name).read_bytes())
    assert load_alerts(copy) == load_alerts()


def test_load_alerts_returns_only_the_600_alerts():
    alerts = load_alerts()
    assert len(alerts) == 600 and all(a["id"].startswith("ALT-") for a in alerts)
    assert not hasattr(sys.modules["worldgen.loader"], "load_twins")
    import inspect

    assert list(inspect.signature(load_alerts).parameters) == ["agent_dir"]     # no switch that returns twins


def test_returned_records_contain_no_hidden_field_names():
    alerts = load_alerts()
    customers, watchlist = load_records()
    for value in (alerts, list(customers.values()), list(watchlist.values())):
        assert not keys_in(value) & HIDDEN_FIELD_NAMES
    assert "alert_id" not in keys_in(alerts)


def test_the_loader_returns_each_alert_with_its_evidence_in_order(world):
    evidence = {e["id"]: e for e in world["evidence"]}
    by_id = {a["id"]: a for a in world["alerts"]}
    for bundle in load_alerts():
        source = by_id[bundle["id"]]
        assert [i["id"] for i in bundle["evidence"]] == source["evidence_item_ids"]
        assert bundle["customer_id"] == source["customer_id"] and bundle["watchlist_entry_id"] == source["watchlist_entry_id"]
        for item in bundle["evidence"]:
            assert item == {k: v for k, v in evidence[item["id"]].items() if k != "alert_id"}


def test_the_harness_module_is_the_only_reader_of_the_twin_file():
    mentions = {p.name for p in ROOT.glob("*.py") if "twin_alerts" in p.read_text(encoding="utf-8")}
    assert mentions == {"harness_twins.py", "build.py"}               # build.py writes the file; the harness reads it
    twins, paths = opened_while(load_twins)
    assert len(twins) == 15 and any(p.endswith("twin_alerts.jsonl") for p in paths)
    assert not [p for p in paths if "hidden" in p]
    importers = {p.name for p in ROOT.glob("*.py") if "harness_twins" in p.read_text(encoding="utf-8")}
    assert importers <= {"harness_twins.py"}                          # no other worldgen module imports it


def test_the_truth_module_reads_the_hidden_folder_and_covers_alerts_and_twins():
    (truth, tags), paths = opened_while(lambda: (load_truth(), load_snippet_tags()))
    hidden = str(WORLD_DIR.joinpath("hidden"))
    assert paths and all(p.startswith(hidden) for p in paths)
    assert len(truth) == 615 and len(tags) == len({t for t in tags})
    assert sum(1 for t in truth.values() if t["twin_of"]) == 15


def test_only_truth_and_build_mention_the_hidden_folder_and_build_never_reads_it():
    mentions = {p.name for p in ROOT.glob("*.py") if "hidden" in p.read_text(encoding="utf-8")}
    assert mentions == {"truth.py", "build.py"}                       # build.py writes those files; truth.py reads them
    _, paths = opened_while(generate)
    assert not [p for p in paths if "hidden" in p]
    assert not [p for p in paths if p.startswith(str(WORLD_DIR))]     # generating reads nothing from data/world
