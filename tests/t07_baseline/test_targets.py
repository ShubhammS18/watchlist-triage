"""T07 gate: the committed baseline and its release targets (DEC-T07-TARGET-RULES, DEC-T07-TARGETS).

These tests read committed artifacts and git history; they call no model. They need the repository with its .git
folder, as every earlier gate did, and they never skip: a missing artifact fails.
"""
import hashlib
import json
import re
import subprocess
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from fractions import Fraction

from harness.manifest import REPO, content_hash

TARGETS = "targets/release-targets.json"
REPORT = "docs/baseline-report.md"
TIME_FILE = "config/modelled_time.json"
FILE = json.loads(REPO.joinpath(TARGETS).read_text(encoding="utf-8"))
SET_REPORT = json.loads(REPO.joinpath(FILE["baseline"]["set_report"]).read_text(encoding="utf-8"))


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


def first_commit(path):
    """The commit that added `path`, which must be committed."""
    added = git("log", "--diff-filter=A", "--format=%H", "--", path).splitlines()
    assert added, f"{path} is not committed"
    return added[-1]


def ancestor(older, newer):
    return subprocess.run(["git", "merge-base", "--is-ancestor", older, newer], cwd=REPO).returncode == 0


def fraction(value):
    return Fraction(value["numerator"], value["denominator"])


def pooled(path):
    value = SET_REPORT["pooled"]
    for key in path.split(".")[1:]:
        value = value[key]
    return value


def manifests():
    runs = [run["run_id"] for run in json.loads(REPO.joinpath("baseline", "index.json").read_text())["runs"]]
    assert len(runs) == 3
    return [json.loads(REPO.joinpath("baseline", run, "manifest.json").read_text()) for run in runs]


def test_the_baseline_copy_matches_its_sha256_list_and_holds_nothing_else():
    folder = REPO.joinpath("baseline")
    listed = dict(reversed(line.split("  ", 1)) for line in folder.joinpath("SHA256SUMS").read_text().splitlines())
    present = {path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()} - {"SHA256SUMS"}
    assert set(listed) == present and len(present) == 11
    for name, digest in listed.items():
        assert hashlib.sha256(folder.joinpath(name).read_bytes()).hexdigest() == digest, name


def test_the_targets_file_names_the_committed_baseline_it_was_worked_out_from():
    base = FILE["baseline"]
    assert hashlib.sha256(REPO.joinpath(base["set_report"]).read_bytes()).hexdigest() == base["set_report_sha256"]
    assert SET_REPORT["run_set"] == base["run_set"] and SET_REPORT["eligible_as_baseline"] is True
    assert SET_REPORT["valid_runs"] == base["valid_runs"] == 3 and base["report"] == REPORT
    assert {m["git"]["commit"] for m in manifests()} == {base["run_commit"]}
    assert all(not m["git"]["dirty"] and m["run_set"] == base["run_set"] for m in manifests())


def test_each_target_is_its_rule_applied_to_the_committed_pooled_values():
    targets = FILE["targets"]
    assert set(targets) == {"over_escalation", "verdict_consistency", "citation_accuracy", "cost_per_alert"}
    for target in targets.values():  # the baseline values in the file are the set report's own, unreduced
        source = pooled(target["baseline_source"])
        assert (source["numerator"], source["denominator"]) == (target["baseline_pooled"]["numerator"],
                                                                target["baseline_pooled"]["denominator"])
    base = {name: fraction(pooled(t["baseline_source"])) for name, t in targets.items()}
    citation = pooled(targets["citation_accuracy"]["baseline_source"])
    expected = {
        "over_escalation": min(base["over_escalation"], Fraction(39, 1000)),
        "verdict_consistency": base["verdict_consistency"],
        "citation_accuracy": Fraction(95, 100) if citation["not_applicable"] else max(base["citation_accuracy"], Fraction(95, 100)),
        "cost_per_alert": Fraction(5, 100) * Fraction(30, 60) * 8,  # 5% of USD 30 an hour times 8 minutes
    }
    assert {name: fraction(t["target"]) for name, t in targets.items()} == expected
    assert expected["cost_per_alert"] == Fraction(1, 5) and targets["cost_per_alert"]["unit"] == "USD per alert-framing item"


def test_the_direction_rules_hold():
    targets = FILE["targets"]
    directions = {"over_escalation": "at_most", "verdict_consistency": "at_least", "citation_accuracy": "at_least",
                  "cost_per_alert": "at_most"}
    assert {name: t["direction"] for name, t in targets.items()} == directions
    value = {name: fraction(t["target"]) for name, t in targets.items()}
    base = {name: fraction(t["baseline_pooled"]) for name, t in targets.items()}
    # the over-escalation target is no higher, and consistency and citation accuracy are no lower, than the baseline
    assert value["over_escalation"] <= base["over_escalation"]
    assert value["verdict_consistency"] >= base["verdict_consistency"]
    assert value["citation_accuracy"] >= base["citation_accuracy"]
    for name, t in targets.items():  # a shown decimal is rounded in the strict direction, to six places
        exact = Decimal(value[name].numerator) / Decimal(value[name].denominator)
        rounding = ROUND_FLOOR if t["direction"] == "at_most" else ROUND_CEILING
        assert Decimal(t["target_decimal"]) == exact.quantize(Decimal("0.000001"), rounding=rounding)


def test_the_targets_were_committed_after_the_baseline_report():
    report, targets = first_commit(REPORT), first_commit(TARGETS)
    assert report != targets and ancestor(report, targets)
    assert ancestor(first_commit("baseline/SHA256SUMS"), report)


def test_the_modelled_time_file_was_committed_before_the_runs_and_is_the_one_they_used():
    time_commit = first_commit(TIME_FILE)
    committed = json.loads(git("show", f"{time_commit}:{TIME_FILE}"))
    for manifest in manifests():
        run_commit = manifest["git"]["commit"]
        assert time_commit != run_commit and ancestor(time_commit, run_commit)
        assert content_hash(committed) == manifest["run_set_inputs"]["modelled_time"] == manifest["modelled_time"]["sha256"]
    assert content_hash(json.loads(REPO.joinpath(TIME_FILE).read_text())) == content_hash(committed)  # unchanged since


def test_the_targets_file_hash_is_the_one_in_the_decision_record():
    records = json.loads(REPO.joinpath(".genesis", "project.json").read_text(encoding="utf-8"))["decisions"]
    [record] = [one for one in records if one["id"] == "DEC-T07-TARGETS"]
    assert record["status"] == "accepted" and record["paths"] == [TARGETS]
    [named] = re.findall(r"SHA-256 ([0-9a-f]{64})", record["text"])
    assert hashlib.sha256(REPO.joinpath(TARGETS).read_bytes()).hexdigest() == named
