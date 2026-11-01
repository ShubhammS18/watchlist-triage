"""W2-08: the release gate's Console sign-off (DEC-W2-01-PASS-LABEL, DEC-W2-08-CHOICES; review round 1, finding 6). A
qualified frozen-world pass, as committed in release/check-frozen.json, needs a row in docs/release-log.md's
"Console sign-off" table naming its run set, with the run set's own cost, a Console amount within 5% and "matches".

Until the release is published, the gate's test of the real release is xfail (strict): it shows as "xfailed" in every
gate run, and becomes an ordinary test the moment release/check-frozen.json is committed. The rule itself is tested
on made-up repositories."""
import json
from pathlib import Path

import pytest

from harness import release
from harness.release_check import PASS, QUALIFIED_PASS
from release_common import REPO

RUN_SET = "1c8d128b" + "0" * 56
HEAD = "## Console sign-off\n\n| Run set | Console USD | Harness USD | Sign-off |\n|---|---|---|---|\n"


@pytest.mark.xfail(not REPO.joinpath("release", "check-frozen.json").exists(), strict=True,
                   reason="the release is not published yet")
def test_the_published_release_has_the_console_sign_off_it_needs():
    assert release.signoff_problem(REPO) is None


def made_up(folder, result, rows=None, costs=((2997877, 10_000_000),)):
    folder = Path(folder)
    folder.joinpath("release", "frozen").mkdir(parents=True)
    folder.joinpath("release", "check-frozen.json").write_text(json.dumps({"result": result, "run_set": RUN_SET}))
    runs = [{"run_id": f"run{n}", "run_set": RUN_SET, "cost": {"known_cost": {"numerator": a, "denominator": b}}}
            for n, (a, b) in enumerate(costs)]
    folder.joinpath("release", "frozen", "index.json").write_text(json.dumps({"runs": runs, "sets": {}}))
    if rows is not None:
        folder.joinpath("docs").mkdir()
        folder.joinpath("docs", "release-log.md").write_text(HEAD + "".join(row + "\n" for row in rows))
    return folder


@pytest.mark.parametrize("row, accepted", [
    ("| `1c8d128b` | 0.30 | 0.2998 | Owner, 1 Nov 2026: matches |", True),
    ("| `1c8d128b` | 0.30 | 0.2998 |  |", False),
    ("| `1c8d128b` | 0.30 | 0.2998 | Owner: not checked |", False),
    ("| `1c8d128b` | 0.30 | 0.3100 | Owner: matches |", False),
    ("| `1c8d128b` | 0.32 | 0.2998 | Owner: matches |", False),
    ("| `8f4050be` | 0.30 | 0.2998 | Owner: matches |", False),
    ("| `` | 0.30 | 0.2998 | Owner: matches |", False),
])
def test_a_qualified_pass_needs_a_matching_sign_off_row(tmp_path, row, accepted):
    assert (release.signoff_problem(made_up(tmp_path, QUALIFIED_PASS, [row])) is None) is accepted


def test_the_cost_is_every_run_of_the_set_replaced_runs_included(tmp_path):
    rows = ["| `1c8d128b` | 0.40 | 0.4000 | Owner: matches |"]
    assert release.signoff_problem(made_up(tmp_path, QUALIFIED_PASS, rows, ((3, 10), (1, 10)))) is None


def test_a_qualified_pass_without_a_release_log_is_refused(tmp_path):
    assert "release-log.md is missing" in release.signoff_problem(made_up(tmp_path, QUALIFIED_PASS))


@pytest.mark.parametrize("result", [PASS, "FAIL", "NOT ELIGIBLE"])
def test_any_other_result_needs_no_sign_off(tmp_path, result):
    assert release.signoff_problem(made_up(tmp_path, result)) is None


def test_no_committed_check_output_is_a_problem(tmp_path):
    assert "check-frozen.json is missing" in release.signoff_problem(tmp_path)
