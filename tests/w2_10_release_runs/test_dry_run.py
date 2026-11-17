"""W2-10 dry run (docs/w2-10-release-runs.md, "The gate tests"): the gate's rules on made-up releases, each built the
way the real release is, in a shared clone, with fake models only. One whole release passes every check (G1 to G12);
each break fails its named check; a FAIL, a NO FRESH WORLD, a broken freeze and a second freeze, each published
consistently, pass.

It runs only by hand, with W2_10_DRY_RUN=1, just before the freeze, and its output is committed as evidence
(DEC-W2-10-ROUND3): it takes about 80 s, and the gate keeps the real-release test and the quick checks
(test_quick.py) under the 100-second aim."""
import json
import os
from decimal import Decimal
from pathlib import Path

import pytest

import made_up
import release_common as rc
import release_gate as gate
from harness import release

pytestmark = pytest.mark.skipif(os.environ.get("W2_10_DRY_RUN") != "1",
                                reason="the dry run runs only with W2_10_DRY_RUN=1, by hand just before the freeze")


def named(found, check, text=""):
    """Whether one of the problems found is from `check` and contains `text`."""
    return any(one.startswith(f"{check}:") and text in one for one in found)


@pytest.fixture(scope="module")
def base(tmp_path_factory, practice):
    """The whole made-up release, and the check's own output for each world, from the documented command."""
    made = made_up.build(tmp_path_factory.mktemp("base"), practice)
    reproduced = {world: gate.reproduce(made.clone, world, made.run_set(world), made.freeze) for world in gate.WORLDS}
    yield made, reproduced
    made.restore()


def test_the_made_up_release_passes_every_check(base):
    made, reproduced = base
    assert gate.problems(made.clone, reproduced) == []
    for world in gate.WORLDS:  # the committed outputs are the documented command's, byte for byte
        assert made.clone.joinpath("release", f"check-{world}.json").read_bytes() == reproduced[world]
    output = json.loads(reproduced["frozen"])
    assert output["result"] == "PASS" and len(output["release"]["runs"]["replaced"]) == 2  # the killed and aborted


def _log(edit):
    def change(made):
        path = made.clone.joinpath(release.RELEASE_LOG)
        path.write_text(edit(made, path.read_text(encoding="utf-8")), encoding="utf-8")
    return change


def _row(made, text, kind, replace):
    """`text` with the frozen-world row of the first run of `kind` changed by `replace(line)`."""
    run = next(run_id for run_id, plan in sorted(made.plans["frozen"].items()) if plan == kind)
    lines = text.split("\n")
    at = next(n for n, line in enumerate(lines) if f"`{run}`" in line and line.count("|") == len(gate.RUN_COLUMNS) + 1)
    lines[at] = replace(lines[at])
    return "\n".join(lines)


def _tag_object(made):
    return rc.git(made.clone, "rev-parse", "release-1-freeze").strip()


def _seed(made):
    path = made.clone.joinpath(release.GENERATION)
    record = json.loads(path.read_text())
    record["accepted"]["seed"] += 1
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


def _spend_all(made, value):
    return {run: Decimal(value) for plan in made.plans.values() for run in plan}


BREAKS = {  # name: (change, the check that must fail, a text its problem contains)
    "a run missing from the log": (_log(lambda m, t: _row(m, t, "valid", lambda line: "")), "G6", "same runs"),
    "a log row for a run that is not there": (
        _log(lambda m, t: _row(m, t, "valid", lambda line: line + "\n" + line.replace(
            line.split("`")[1], "20991231T000000000000Z-deadbeef"))), "G6", "same runs"),
    "a replaced run called valid": (
        _log(lambda m, t: _row(m, t, "killed", lambda line: line.replace("| replaced | never finished |", "| valid |  |"))),
        "G6", "valid or replaced"),
    "a wrong harness amount": (
        _log(lambda m, t: _row(m, t, "valid", lambda line: line.replace("| 0.0000 |", "| 0.0100 |", 1))), "G6", "Harness USD"),
    "Spend USD that is not the Console difference": (
        _log(lambda m, t: _row(m, t, "valid", lambda line: line.replace("| 0.10 |", "| 0.09 |"))), "G6", "Console before"),
    "a wrong running total": (
        _log(lambda m, t: t.replace("Wave-2 spend: USD 1.80 ", "Wave-2 spend: USD 1.81 ")), "G9", "running total"),
    "a wrong result in the Results table": (
        _log(lambda m, t: t.replace("`release/check-frozen.json` | PASS |", "`release/check-frozen.json` | FAIL |")),
        "G9", "Results row"),
    "a tag-object line, not the peeled line": (
        _log(lambda m, t: t.replace(f"{m.freeze}\trefs/tags/release-1-freeze^{{}}",
                                    f"{_tag_object(m)}\trefs/tags/release-1-freeze")), "G11", "peeled"),
    "an edited check output": (
        lambda m: m.clone.joinpath("release", "check-frozen.json").write_bytes(
            m.clone.joinpath("release", "check-frozen.json").read_bytes() + b"\n"), "G5", "check-frozen"),
    "a seed that is not the seed function's": (_seed, "G3", "seed function"),
    "a code change after the freeze, published without NOT ELIGIBLE": (
        lambda m: m.clone.joinpath("README.md").write_text("changed\n"), "G2", "freeze is broken"),
    "the publish tag not on the commit checked": (
        lambda m: m.clone.joinpath("docs", "note.md").write_text("x\n"), "G9", "tag release-1"),
    "a run over USD 0.30 with a run after it": (
        lambda m: m.log(spends={sorted(m.plans["frozen"])[0]: Decimal("0.31")}), "G12", "over 0.30"),
    "spend over USD 2.00 with a run after it": (lambda m: m.log(spends=_spend_all(m, "0.29")), "G12", "over 2.00"),
    # review round 2
    "a reason on a valid run's row": (
        _log(lambda m, t: _row(m, t, "valid", lambda line: line.replace("| valid |  |", "| valid | fine |"))),
        "G6", "valid or replaced"),
    "a Results row for a world that is not a release world": (
        _log(lambda m, t: t.replace("`release/check-frozen.json` | PASS |", "`release/check-frozen.json` | PASS |\n"
                                    "| practice | `00000000` | `release/check-practice.json` | PASS |")),
        "G9", "not a release world"),
    "two Results rows for one world": (
        _log(lambda m, t: t.replace("`release/check-frozen.json` | PASS |", "`release/check-frozen.json` | PASS |\n"
                                    + next(line for line in t.split("\n") if "`release/check-frozen.json`" in line))),
        "G9", "Results row of the frozen world"),
    "a killed run's last item, a refusal, whole but without its newline, with runs after it": (
        lambda m: _killed_refusal(m), "G12", "refusal checkpoint"),
    "a rehearsal row whose State is not its index's": (
        _log(lambda m, t: _rehearsal_row(t, 4, "aborted")), "G8", "state 'aborted'"),
    "a rehearsal row whose Run set is not its index's": (
        _log(lambda m, t: _rehearsal_row(t, 3, "`deadbeef`")), "G8", "run set `deadbeef`"),
    "a line of an items file that is not an item record": (
        lambda m: _items(m, lambda lines: lines[:1] + [b"{not json"] + lines[2:]), "G12", "not an item record"),
}


def _rehearsal_row(text, cell, value):
    """`text` with one cell of the rehearsal's row (0 is Date) set to `value`."""
    lines = text.split("\n")
    at = next(n for n, line in enumerate(lines) if "| made up |" in line)
    cells = lines[at].split(" | ")
    cells[cell] = value
    lines[at] = " | ".join(cells)
    return "\n".join(lines)


def _killed_refusal(made):
    """The killed frozen-world run's items file, as a crash right after its first item can leave it: that one item, a
    model refusal, whole, without its newline (review round 3, R3-1). A refusal share of 100%, with runs after it."""
    killed = next(run for run, plan in sorted(made.plans["frozen"].items()) if plan == "killed")
    valid = next(run for run, plan in sorted(made.plans["frozen"].items()) if plan == "valid")
    line = json.loads(made.clone.joinpath("release", "frozen", valid, "items.jsonl").read_bytes().split(b"\n")[0])
    line["result"]["failure_kind"] = "model_refusal"
    made.clone.joinpath("release", "frozen", killed, "items.jsonl").write_text(json.dumps(line))


def _items(made, change):
    """Change the item lines of the first valid frozen-world run's items file."""
    run = next(run_id for run_id, plan in sorted(made.plans["frozen"].items()) if plan == "valid")
    path = made.clone.joinpath("release", "frozen", run, "items.jsonl")
    path.write_bytes(b"\n".join(change(path.read_bytes().split(b"\n"))))


@pytest.mark.parametrize("name", BREAKS)
def test_each_break_fails_its_check(base, name):
    made, reproduced = base
    change, check, text = BREAKS[name]
    try:
        if name == "the publish tag not on the commit checked":  # a commit after the tag, which stays where it was
            change(made)
            made.commit("After the publish tag (test)")
        else:
            made.amend(change)
        found = gate.problems(made.clone, reproduced)
        assert named(found, check, text), found
    finally:
        made.restore()


def test_a_second_freeze_tag_passes(base):
    """The gate reads the freeze commit from the generation record, not from a tag name (DEC-W2-10-STOPS)."""
    made, reproduced = base

    def retag(m):
        rc.git(m.clone, "tag", "-a", "-m", "freeze", "release-1-freeze-2", m.freeze)
        rc.git(m.clone, "tag", "-d", "release-1-freeze")
        m.log(tag="release-1-freeze-2")
    try:
        made.amend(retag)
        assert gate.problems(made.clone, reproduced) == []
    finally:
        made.restore()


def _built(tmp_path, practice, **variant):
    return made_up.build(tmp_path.joinpath("made"), practice, **variant)


def _reproduced(made):
    """Both worlds' check outputs from the documented command, so every published-result case checks G5 too (review
    round 2, finding N4)."""
    return {world: gate.reproduce(made.clone, world, made.run_set(world), made.freeze) for world in gate.WORLDS}


def test_a_published_fail_passes(tmp_path, practice):
    made = _built(tmp_path, practice, frozen=("valid",), fresh=("unsafe", "valid", "valid"))
    assert json.loads(made.clone.joinpath("release", "check-fresh.json").read_text())["result"] == "FAIL"
    reproduced = _reproduced(made)
    assert gate.problems(made.clone, reproduced) == []
    path = made.clone.joinpath("release", "check-fresh.json")  # and an edited output on this FAIL branch
    made.amend(lambda m: path.write_bytes(path.read_bytes().replace(b'"FAIL"', b'"PASS (safety counts only)"')))
    assert named(gate.problems(made.clone, reproduced), "G5", "check-fresh")


@pytest.fixture(scope="module")
def no_fresh_lost_index(tmp_path_factory, practice):
    """One release for two published results: NO FRESH WORLD (a test generator rejects all ten tries), and a frozen
    world whose index a crash cut off, with one run whose items file a crash cut mid-line, copied in as it is
    (DEC-W2-10-LOST-INDEX). One build, since each takes about 8 s."""
    made = made_up.build(tmp_path_factory.mktemp("lost"), practice, reject=10, frozen=("valid", "valid", "cut"),
                         lost_index=("frozen",))
    return made, _reproduced(made)


def test_a_published_no_fresh_world_passes(no_fresh_lost_index):
    made, reproduced = no_fresh_lost_index
    fresh = json.loads(made.clone.joinpath("release", "check-fresh.json").read_text())
    assert (fresh["result"], fresh["run_set"]) == (release.NO_FRESH_WORLD, gate.NO_RUN_SET)
    assert gate.problems(made.clone, reproduced) == []


def test_a_broken_freeze_published_as_not_eligible_passes(tmp_path, practice):
    """DEC-W2-10-STOPS: a broken freeze is reported, not failed."""
    made = _built(tmp_path, practice, frozen=("valid",), fresh=("valid",),
                  before_checks=lambda clone: Path(clone, "README.md").write_text("changed\n"))
    for world in gate.WORLDS:
        output = json.loads(made.clone.joinpath("release", f"check-{world}.json").read_text())
        assert output["result"] == "NOT ELIGIBLE"
        assert any(p.endswith("README.md: changed after the freeze, and it is not a file the release may change")
                   for p in output["not_eligible_because"])
    assert not any(one.startswith(("G2:", "G5:")) for one in gate.problems(made.clone, _reproduced(made)))


def test_a_lost_index_and_a_cut_off_items_file_published_as_not_eligible_pass(no_fresh_lost_index):
    """DEC-W2-10-LOST-INDEX and review round 2, finding N2: a crash leaves the frozen world's index cut off and one
    run's items file ending mid-line. The world is copied in as it is, the index that is not JSON left out with its
    hash printed for the log, and published as NOT ELIGIBLE; the gate passes it and reads the cut file's whole
    records. The log's "Left out" entry for the index is required (review round 3, R3-2): without it the gate fails."""
    made, reproduced = no_fresh_lost_index
    lost = made.clone.joinpath(release.RELEASE_LOG).read_text().split("## Frozen world\n", 1)[1].split("\n## ", 1)[0]
    entry = made.left_out["frozen"].split("\n")[0]  # what copy_as_is printed for the index it left out
    assert entry.startswith("- Left out: `index.json`, SHA-256 `") and entry in lost
    assert not made.clone.joinpath("release", "frozen", "index.json").exists()
    cut = next(run for run, plan in made.plans["frozen"].items() if plan == "cut")
    assert not made.clone.joinpath("release", "frozen", cut, "items.jsonl").read_bytes().endswith(b"\n")
    output = json.loads(made.clone.joinpath("release", "check-frozen.json").read_text())
    assert output["result"] == "NOT ELIGIBLE" and set(output["release"]["runs"]["replaced"].values()) == \
        {"not listed in the index"}
    assert gate.problems(made.clone, reproduced) == []
    try:  # the same release with the index's "Left out" entry not written
        made.amend(_log(lambda m, t: "\n".join(line for line in t.split("\n") if not line.startswith("- Left out:"))))
        assert named(gate.problems(made.clone, reproduced), "G6", "no 'Left out' entry")
    finally:
        made.restore()


def _rules(clone):
    path = Path(clone, "triage_agent", "rules.py")
    path.write_text(path.read_text() + "\n# a change (test)\n")


def _completed(made):
    return next(run for run, plan in made.plans["rehearsal"].items() if plan == "valid")


def _delete_report(made, folder):
    """A required file of the completed rehearsal deleted, and its SHA256SUMS made again to match."""
    folder.joinpath(_completed(made), "report.json").unlink()
    rc.sums(folder)


def _falsify_workers(made, folder):
    """A rehearsal made with two workers whose manifest is edited to say one, the release runs' setting, and its
    SHA256SUMS made again to match."""
    path = folder.joinpath(_completed(made), "manifest.json")
    manifest = json.loads(path.read_text())
    manifest["workers"] = manifest["run_set_inputs"]["workers"] = 1
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    rc.sums(folder)


def _link_report(made, folder):
    """The completed rehearsal's report replaced by a relative link to the same bytes elsewhere in the tree, so its
    hash still holds. (The fresh-world step refuses a link to an absolute path anywhere in the freeze's tree.)"""
    path = folder.joinpath(_completed(made), "report.json")
    made.clone.joinpath("docs", "linked-report.json").write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(Path("..", "..", "docs", "linked-report.json"))


NONE = {"frozen": (), "fresh": (), "checks": False}  # no release run at all: the rehearsal is bound to the freeze alone
VARIANTS = {  # name: (build keywords, the check that must fail, a text its problem contains)
    "rehearsal evidence committed after the freeze": ({"rehearsal_after_freeze": True, **NONE}, "G8", "by the freeze"),
    "a rehearsal on the frozen world, not the practice world": (
        {"rehearsal_world": lambda clone: clone.joinpath("data", "world"), **NONE}, "G8", "no completed"),
    "code changed between the rehearsal and the freeze": (
        {"before_freeze": _rules, **NONE}, "G8", "triage_agent/rules.py"),
    "no completed rehearsal, only an aborted one": ({"rehearsal": ("aborted",), **NONE}, "G8", "no completed"),
    "a rehearsal with other run settings than the freeze's configuration, and no release run": (
        {"rehearsal_workers": 2, **NONE}, "G8", "no completed"),
    "a required rehearsal file deleted, with SHA256SUMS to match": (
        {"rehearsal_evidence": _delete_report, **NONE}, "G8", "report.json missing"),
    "a falsified rehearsal manifest field, with SHA256SUMS to match": (
        {"rehearsal_workers": 2, "rehearsal_evidence": _falsify_workers, **NONE}, "G8", "do not agree"),
    "a rehearsal file committed as a symbolic link": (
        {"rehearsal_evidence": _link_report, **NONE}, "G8", "symbolic link"),
    "fresh-world checkpoints committed before the generation record": (
        {"checkpoints_before_generation": True, "frozen": (), "fresh": ("valid",), "checks": False}, "G7",
        "before the generation record"),
    "refusals over the 2% checkpoint with a run after it": (
        {"frozen": ("refusals", "valid"), "fresh": (), "checks": False}, "G12", "refusal checkpoint"),
    "six runs on one world": ({"frozen": ("valid",) * 6, "fresh": (), "checks": False}, "G6", "above five"),
}


def test_the_control_built_like_the_variants_fails_none_of_their_checks(tmp_path, practice):
    """A right rehearsal, built the same short way as the variants below (one run per world, no check outputs), so
    each variant's problem is its own and not the short build's."""
    found = gate.problems(_built(tmp_path, practice, frozen=("valid",), fresh=("valid",), checks=False).clone)
    assert not [one for one in found if one.startswith(("G7:", "G8:", "G12:")) or "above five" in one], found


@pytest.mark.parametrize("name", VARIANTS)
def test_each_wrong_release_fails_its_check(tmp_path, practice, name):
    keywords, check, text = VARIANTS[name]
    found = gate.problems(_built(tmp_path, practice, **keywords).clone)
    assert named(found, check, text), found
