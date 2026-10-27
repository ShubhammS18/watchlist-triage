"""W2-01: the release check reads the committed targets file and judges a rate against a target in the right
direction, equality included (DEC-T07-TARGETS, DEC-W2-01-ELIGIBILITY)."""
import json
import subprocess

import pytest

from harness import release_check
from harness.manifest import REPO, sha256

PATH = "targets/release-targets.json"


def test_the_fixed_hash_is_the_committed_file_and_the_one_in_the_targets_record():
    assert sha256(REPO.joinpath(PATH).read_bytes()) == release_check.TARGETS_SHA256
    assert subprocess.run(["git", "diff", "--quiet", "HEAD", "--", PATH], cwd=REPO).returncode == 0
    decisions = json.loads(REPO.joinpath(".genesis", "project.json").read_text(encoding="utf-8"))["decisions"]
    record, = [record for record in decisions if record["id"] == "DEC-T07-TARGETS"]
    assert release_check.TARGETS_SHA256 in record["text"]


def rate(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator, "not_applicable": denominator == 0}


@pytest.mark.parametrize("direction, value, expected", [
    ("at_most", rate(39, 1000), "pass"), ("at_most", rate(78, 2000), "pass"), ("at_most", rate(40, 1000), "fail"),
    ("at_least", rate(1239, 1800), "pass"), ("at_least", rate(1238, 1800), "fail"), ("at_least", rate(0, 0), "fail"),
    ("at_most", rate(0, 0), "fail")])
def test_a_rate_is_judged_as_an_exact_fraction_with_equality_passing(direction, value, expected):
    target = {"direction": direction, "target": {"numerator": 39, "denominator": 1000} if direction == "at_most"
              else {"numerator": 1239, "denominator": 1800}}
    assert release_check.judge_rate(value, target) == expected
