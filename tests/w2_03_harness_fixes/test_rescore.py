"""W2-03: the committed baseline/ and w2-02-runs/ output re-score to exactly what was committed, so no fix here moved a
figure. Each folder is copied to a temporary folder and re-scored there with --rescore, by the code as it is now, as
if by the commit that wrote the committed reports; the committed files are never written to.

w2-02-runs/ was scored by code that already wrote every key, so its reports must come back equal as a whole. The
baseline was scored in T07, before W2-01 added injection figures and changed the notes text: there, the keys added
since are left out of the new report and the notes are not compared, and every value the committed report holds must
come back equal, as W2-01's own re-score test requires (tests/w2_01_acceptance/test_baseline.py)."""
import json
import shutil
import subprocess
from fractions import Fraction

import pytest

from conftest import REPO, WORLD
from harness import score

FOLDERS = {"baseline": "f2e614d2", "w2-02-runs": "8f4050be"}
LATER = {"baseline": True, "w2-02-runs": False}  # whether code after the committed reports added keys and notes
# The one value W2-01 rewrote in the baseline's set report: the AC-6 placeholder text, now that targets exist
# (DEC-W2-01-DESIGN). Every other value must come back as committed.
W2_01_TEXT = {"not determined: no AC-16 target exists yet":
              "not determined here: the release targets are judged by python -m harness acceptance"}


def as_committed(new, committed, folder):
    """`new` as the code that wrote `committed` would have written it: for the baseline, without the keys added
    since and without the notes. Values are never changed, only keys the committed report lacks are left out."""
    if not LATER[folder] or not isinstance(new, dict) or not isinstance(committed, dict):
        return new
    return {key: as_committed(value, committed[key], folder) for key, value in new.items()
            if key in committed and key != "notes"}


def drop_notes(report, folder):
    return {key: value for key, value in report.items() if key != "notes"} if LATER[folder] else report


def committed_set(folder):
    """The committed set report, with W2_01_TEXT applied for the baseline."""
    path = [one for one in REPO.joinpath(folder, "sets").glob("*.json") if one.name.startswith(FOLDERS[folder])]
    assert len(path) == 1
    report = json.loads(path[0].read_text(encoding="utf-8"))
    if LATER[folder]:
        report["acceptance"]["AC-6"]["citation_accuracy"]["result"] = \
            W2_01_TEXT[report["acceptance"]["AC-6"]["citation_accuracy"]["result"]]
    return report


def without_order(report):
    """A set report with its runs in run-ID order: which command scored last changes that order
    (docs/evidence/t07/known-issues.md, issue 3)."""
    return {**report, "runs": sorted(report["runs"], key=lambda run: run["run_id"])}


def value(amount):
    return None if amount["not_applicable"] else Fraction(amount["numerator"], amount["denominator"])


def assert_same_spread(new, committed, path="spread"):
    """The spread as committed. Each run's own value must be equal exactly, and so must every other entry, with one
    exception from the same known issue: where runs tie, a minimum or maximum shows the first tied run's fraction
    (0/2 against 0/3, both 0). So a minimum or maximum may differ from the committed one only when both are among
    the runs' own values and equal in value; otherwise the whole rate object must be equal."""
    if isinstance(new, dict) and "per_run" in new and isinstance(new.get("min"), dict) and "numerator" in new["min"]:
        assert set(new) == set(committed) and new["per_run"] == committed["per_run"], path
        for end in ("min", "max"):
            shown, kept, runs = new[end], committed[end], list(committed["per_run"].values())
            assert shown == kept or (shown in runs and kept in runs and value(shown) == value(kept)), \
                f"{path}.{end}: {shown} against {kept}"
        assert {key: one for key, one in new.items() if key not in ("min", "max", "per_run")} == \
               {key: one for key, one in committed.items() if key not in ("min", "max", "per_run")}, path
    elif isinstance(new, dict):
        assert isinstance(committed, dict) and set(new) == set(committed), path
        for key in new:
            assert_same_spread(new[key], committed[key], f"{path}.{key}")
    else:
        assert new == committed, path


@pytest.fixture(scope="module", params=sorted(FOLDERS))
def rescored(request, tmp_path_factory):
    folder = request.param
    copy = tmp_path_factory.mktemp("rescore").joinpath(folder)
    shutil.copytree(REPO.joinpath(folder), copy)
    before = committed_set(folder)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(score, "scoring_state", lambda out: before["scored_by"])
        done = score.score_all(copy, WORLD, rescore=True)
    return folder, copy, done


def test_the_committed_files_are_unchanged(rescored):
    folder, _, _ = rescored
    assert subprocess.run(["sha256sum", "--check", "--quiet", "--strict", "SHA256SUMS"],
                          cwd=REPO.joinpath(folder)).returncode == 0


def test_every_run_report_rescores_to_the_committed_one(rescored):
    folder, copy, done = rescored
    runs = sorted(path.parent.name for path in REPO.joinpath(folder).glob("2*/report.json"))
    assert len(runs) == 3 and sorted(done["written"]) == runs and not done["excluded"]
    for run in runs:
        committed = json.loads(REPO.joinpath(folder, run, "report.json").read_text(encoding="utf-8"))
        new = json.loads(copy.joinpath(run, "report.json").read_text(encoding="utf-8"))
        assert as_committed(new, committed, folder) == drop_notes(committed, folder), run


def test_the_set_report_rescores_to_the_committed_one_acceptance_included(rescored):
    folder, copy, done = rescored
    committed = committed_set(folder)
    new = json.loads(copy.joinpath("sets", f"{committed['run_set']}.json").read_text(encoding="utf-8"))
    assert new["acceptance"] == committed["acceptance"] and new["acceptance"]["mechanism_only"] is False
    assert new["mechanism_only"] == committed["mechanism_only"] == {"cost": False, "modelled_time": False}
    new, committed = as_committed(without_order(new), without_order(committed), folder), drop_notes(without_order(committed), folder)
    assert {key: one for key, one in new.items() if key != "spread"} == \
           {key: one for key, one in committed.items() if key != "spread"}
    assert_same_spread(new["spread"], committed["spread"])
