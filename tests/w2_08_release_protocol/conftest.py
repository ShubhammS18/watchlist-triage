"""Fixtures of the W2-08 tests: the candidate agent registered for the session, a check that no test writes inside
the repository, one shared clone with a test freeze commit, the fresh world made from it, and pools of release runs
on each world from which each test assembles the run output it needs."""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_common as rc  # noqa: E402

from harness import release, release_check  # noqa: E402
from worldgen.truth import load_truth  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def registered():
    with pytest.MonkeyPatch.context() as patch:
        rc.register(patch)
        yield


@pytest.fixture(scope="session", autouse=True)
def repository_untouched():
    """No test writes inside the repository."""
    status = lambda: subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=rc.REPO,
                                    capture_output=True, text=True).stdout
    before = status()
    yield
    assert status() == before


@pytest.fixture(scope="session")
def cloned(tmp_path_factory):
    """(clone, freeze commit). Tests that use it run one at a time and leave it at a commit of their own; `publish`
    resets it first."""
    return rc.new_clone(tmp_path_factory.mktemp("clone").joinpath("repo"))


@pytest.fixture(scope="session")
def fresh(cloned, tmp_path_factory):
    """The fresh world made from the test freeze commit: (its folder, the generation record)."""
    clone, freeze = cloned
    rc.reset(clone, freeze)
    folder = tmp_path_factory.mktemp("fresh")
    record = release.make_fresh_world(freeze, folder.joinpath("world"), folder.joinpath("generation.json"), repo=clone)
    return folder.joinpath("world"), record


class Pool(dict):
    """Runs on one world at the test freeze commit, all in one run set and one output folder, each made when a test
    first asks for it by name: {name: run id, "out": folder}. Asking resets the clone to the freeze commit, so a test
    takes what it needs from a pool before it publishes."""

    def __init__(self, cloned, folder, world, behaviours, truth, workers=1, at=None):
        super().__init__(out=folder.joinpath("out"))
        self.cloned, self.folder, self.world, self.behaviours, self.truth = cloned, folder, world, behaviours, truth
        self.workers, self.at = workers, at

    def __missing__(self, name):
        clone, freeze = self.cloned
        rc.reset(clone, self.at or freeze)
        with rc.at(clone):
            _, (run_id,) = rc.make_runs(self.folder, self.world, [self.behaviours[name]], self.truth, self.workers)
        self[name] = run_id
        return run_id


FROZEN = {  # name -> how the candidate behaves in that run
    "valid1": {}, "valid2": {}, "valid3": {}, "valid4": {},
    "infra1": {"timeouts": True}, "infra2": {"timeouts": True}, "infra3": {"timeouts": True},
    "aborted_unsafe": {"close_true_match": True, "abort_after": 40},
    "aborted": {"abort_after": 40},
    "unbounded": {"failed_call": True},
}
FRESH = {"over1": {"escalate_clear": True}, "over2": {"escalate_clear": True}, "over3": {"escalate_clear": True},
         "aborted_unsafe": {"close_true_match": True, "abort_after": 40}}


@pytest.fixture(scope="session")
def frozen_pool(cloned, tmp_path_factory):
    clone, _ = cloned
    return Pool(cloned, tmp_path_factory.mktemp("frozen-pool"), clone.joinpath("data", "world"), FROZEN, load_truth())


@pytest.fixture(scope="session")
def other_set(cloned, tmp_path_factory):
    """A run on the frozen world with another configuration (two workers), so of another run set."""
    clone, _ = cloned
    return Pool(cloned, tmp_path_factory.mktemp("other-set"), clone.joinpath("data", "world"), {"other": {}},
                load_truth(), workers=2)


@pytest.fixture(scope="session")
def before_freeze(cloned, tmp_path_factory):
    """A run on the frozen world made at the commit before the freeze, so of another run set."""
    clone, freeze = cloned
    return Pool(cloned, tmp_path_factory.mktemp("before-freeze"), clone.joinpath("data", "world"),
                {"early1": {}, "early2": {}, "early3": {}}, load_truth(), at=rc.git(clone, "rev-parse", f"{freeze}~1").strip())


@pytest.fixture(scope="session")
def fresh_pool(cloned, fresh, tmp_path_factory):
    """Runs on the fresh world: three that escalate every plain clear false positive (safe, but far off the rate
    targets), and an aborted run that closed a true match."""
    world, _ = fresh
    return Pool(cloned, tmp_path_factory.mktemp("fresh-pool"), world, FRESH, rc.fresh_truth(world))


@pytest.fixture
def judge(cloned):
    """judge(world, run_set=None): the release check of the clone's HEAD on one world; the run set defaults to the
    one the output holds."""
    clone, freeze = cloned

    def run(world="frozen", run_set=None):
        out = clone.joinpath("release", world)
        if run_set is None:
            run_set = {entry["run_set"] for entry in rc.records.read_index(out)["runs"]}.pop()
        with rc.at(clone):
            return release_check.check(out, run_set, release={"freeze": freeze, "fresh": world == "fresh"})
    return run
