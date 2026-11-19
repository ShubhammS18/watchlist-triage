"""The W2-09 gate: the README against its evidence (NFR-7, NFR-8). It checks that every release-checklist item names
evidence paths that exist, that the README's gap list equals DEC-W2-SCOPE's, that every release figure the README
gives equals the committed check output, and that the cited statistic carries its DOI. It reads files only. It does
not check that a claim says what its evidence says; the review does."""
import json
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
README = REPO.joinpath("README.md").read_text(encoding="utf-8")
CHECKLIST = REPO.joinpath("docs", "release-checklist.md").read_text(encoding="utf-8")
CHECKS = {world: json.loads(REPO.joinpath("release", f"check-{world}.json").read_text(encoding="utf-8"))
          for world in ("frozen", "fresh")}
GAP_ID = re.compile(r"((?:FR|AC)-\d+)(?: \(([^)]*)\))?")
DOI = "10.3389/frai.2024.1374323"


def section(title):
    """The README text under the `## title` heading, up to the next one."""
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", README, re.M | re.S)
    assert match, f"README has no section {title!r}"
    return match.group(1)


def decision(record_id):
    records = json.loads(REPO.joinpath(".genesis", "project.json").read_text(encoding="utf-8"))["decisions"]
    record, = [record for record in records if record["id"] == record_id]
    return record


def rows(text):
    """The cells of each body row of every markdown table in text: a table's header and separator are left out."""
    lines = text.splitlines()
    return [[cell.strip() for cell in line.strip().strip("|").split("|")]
            for i, line in enumerate(lines)
            if line.startswith("|") and i >= 2 and lines[i - 1].startswith("|") and lines[i - 2].startswith("|")]


def flat(text):
    """text with every run of whitespace made one space, so a phrase may wrap across lines."""
    return " ".join(text.split())


# 1. checklist evidence paths

def evidence_paths(cell):
    """Backticked names in an evidence cell that are paths: they hold a slash or a dot, or are a capitalised file
    name such as LICENSE. Record IDs such as DEC-W2-SCOPE and tags such as release-1 are not paths."""
    return [name for name in re.findall(r"`([^`]+)`", cell)
            if "/" in name or "." in name or re.fullmatch(r"[A-Z]+", name)]


def test_every_checklist_item_names_evidence_that_exists():
    items = [row for row in rows(CHECKLIST) if re.fullmatch(r"[SC]\d+", row[0])]
    assert len(items) >= 40
    assert len({row[0] for row in items}) == len(items), "item numbers repeat"
    for row in items:
        paths = evidence_paths(row[-1])
        assert paths, f"{row[0]} names no evidence path"
        for path in paths:
            assert REPO.joinpath(path).exists(), f"{row[0]}: {path} does not exist"
            assert "hidden" not in Path(path).parts, f"{row[0]}: evidence under hidden/"


def test_the_path_rule_ignores_record_ids_and_tags():
    assert evidence_paths("`DEC-W2-SCOPE`, `release-1`, `SPEC.md`, `docs/reviews/`, `LICENSE`") == [
        "SPEC.md", "docs/reviews/", "LICENSE"]


# 2. the gap list

def scope_gaps():
    source = decision("DEC-W2-SCOPE")["source"]
    listed = re.search(r"gaps: (.*?);", source).group(1)
    return GAP_ID.findall(listed)


def readme_gaps():
    return [GAP_ID.match(line[len("- **"):].replace("**", "", 1)).groups()
            for line in section("What was not built").splitlines() if re.match(r"- \*\*(FR|AC)-\d+\*\*", line)]


def test_readme_gap_list_equals_the_scope_record():
    assert len(scope_gaps()) == 13
    assert [(rid, note or "") for rid, note in readme_gaps()] == scope_gaps()


def test_gap_parsing_keeps_the_qualifier():
    assert GAP_ID.findall("FR-8 (pipeline half), FR-11, AC-14 (override, rejection, stop)") == [
        ("FR-8", "pipeline half"), ("FR-11", ""), ("AC-14", "override, rejection, stop")]


# 3. release figures

def per_run(world, target):
    return ", ".join(str(value) for value in CHECKS[world]["targets"][target]["per_run"].values())


def fraction(world, target):
    value = CHECKS[world]["targets"][target]["value"]
    return value["numerator"], value["denominator"]


def percent(numerator, denominator):
    """A share as a percentage to two places, half up."""
    return str((Decimal(numerator * 100) / denominator).quantize(Decimal("0.01"), ROUND_HALF_UP))


def expected_cells(world):
    info = "" if world == "frozen" else ", information only"
    over, consistency, accuracy = (fraction(world, t) for t in ("over_escalation", "verdict_consistency",
                                                               "citation_accuracy"))
    time = CHECKS[world]["targets"]["modelled_review_time"]
    return {
        "True matches closed, per run": per_run(world, "true_matches_closed"),
        "Ambiguous alerts closed, per run": per_run(world, "ambiguous_closed"),
        "Closes without a valid citation set, per run": per_run(world, "closes_without_valid_citations"),
        "Verdicts changed by injected text, per run": per_run(world, "injection_verdict_divergence"),
        "Clear false positives escalated": f"{over[0]}/{over[1]} ({percent(*over)}%){info}",
        "Alerts whose three framings agree": f"{consistency[0]}/{consistency[1]} ({percent(*consistency)}%){info}",
        "Citation accuracy": f"{accuracy[0]}/{accuracy[1]}{info}",
        "Model cost per alert-framing item":
            f"USD {CHECKS[world]['targets']['cost_per_alert']['value']['decimal']}{info}",
        "Modelled minutes per alert, assisted against manual":
            f"{float(time['assisted_per_alert']['decimal']):.2f} against "
            f"{float(time['manual_per_alert']['decimal']):.2f}{info}",
        "Result": CHECKS[world]["result"],
    }


def release_table():
    return {row[0]: {"frozen": row[2], "fresh": row[3]} for row in rows(section("Release 1"))}


@pytest.mark.parametrize("world", ["frozen", "fresh"])
def test_every_release_figure_matches_the_check_output(world):
    table = release_table()
    expected = expected_cells(world)
    assert set(table) == set(expected), "the release table's rows changed: update the expected cells"
    for name, cell in expected.items():
        assert table[name][world] == cell, f"{world}, {name}"


def test_release_prose_matches_the_check_output():
    text = flat(section("Release 1"))
    assert CHECKS["frozen"]["result"] == "PASS" and "**Frozen world: PASS.**" in text
    assert CHECKS["fresh"]["result"] == "PASS (safety counts only)" and "**Fresh world: PASS (safety counts only).**" in text
    assert "not a pass on every target" in text
    frozen_bounded = CHECKS["frozen"]["targets"]["cost_per_alert"]["failed_tries_bounded"]
    fresh_bounded = CHECKS["fresh"]["targets"]["cost_per_alert"]["failed_tries_bounded"]
    assert frozen_bounded == 0 and "On the frozen world every call left token counts" in text
    assert f"On the fresh world {fresh_bounded} failed calls left no token counts" in text
    for world in CHECKS:
        assert CHECKS[world]["release"]["freeze_commit"].startswith(re.search(r"commit \(`(\w+)`", text).group(1))
        assert len(CHECKS[world]["runs"]["valid"]) == 3 and not CHECKS[world]["release"]["runs"]["replaced"]
    generation = CHECKS["fresh"]["release"]["generation"]["replayed"]
    assert generation["accepted"]["counter"] == 0 and "(counter 0)" in text
    log = REPO.joinpath("docs", "release-log.md").read_text(encoding="utf-8")
    total = re.search(r"Wave-2 spend: USD ([\d.]+)", log).group(1)
    assert f"wave 2 in all cost USD {total}" in text


def test_the_fresh_world_is_never_said_to_pass_every_target():
    text = flat(README).lower()
    for claim in ("fresh world passed every", "fresh world met every", "fresh world: pass on every"):
        assert claim not in text


# 4. the statistic and its DOI

def test_the_statistic_carries_its_doi():
    for name, text in (("README.md", README), ("docs/release-checklist.md", CHECKLIST)):
        paragraphs = [flat(p) for p in re.split(r"\n\s*\n", text) if "over 90%" in flat(p)]
        assert paragraphs, f"{name} does not give the statistic"
        for paragraph in paragraphs:
            assert DOI in paragraph and "Kim and Yang" in paragraph, name
            assert "citing earlier industry sources" in paragraph, name


# the docs index

def test_docs_index_lists_the_new_docs():
    index = REPO.joinpath("docs", "README.md").read_text(encoding="utf-8")
    for doc in ("release-log.md", "release-checklist.md"):
        assert f"| `{doc}` |" in index
