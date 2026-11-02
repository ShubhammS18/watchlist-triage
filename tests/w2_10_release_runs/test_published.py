"""W2-10: the gate test of the real release (docs/w2-10-release-runs.md, G1 to G12; DEC-W2-10-CHOICES,
DEC-W2-10-STOPS). It clones the repository into a temporary folder, with full history and the tags, checks out the
publish tag `release-1`, runs the release check there on both worlds with the clone's own code, and applies every
rule to the committed files. Commits after the publish commit therefore cannot break it.

Until the release is published it is xfail (strict): it shows as "xfailed" in every gate run, and becomes an ordinary
test the moment the tag `release-1` exists. The rules themselves are tested on made-up releases (test_dry_run.py)."""
import json
import subprocess

import pytest

import release_common as rc
import release_gate as gate

PUBLISHED = subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{gate.PUBLISH_TAG}"], cwd=rc.REPO,
                           capture_output=True).returncode == 0


@pytest.mark.xfail(not PUBLISHED, strict=True, reason="the release is not published yet")
def test_the_published_release_is_complete_and_consistent(tmp_path):
    assert PUBLISHED, f"there is no tag {gate.PUBLISH_TAG}"
    clone = tmp_path.joinpath("repo")
    subprocess.run(["git", "clone", "-q", "--shared", str(rc.REPO), str(clone)], check=True)
    rc.git(clone, "checkout", "-q", "--detach", gate.PUBLISH_TAG)
    freeze = json.loads(clone.joinpath("release", "generation.json").read_text())["freeze_commit"]
    reproduced = {}
    for world in gate.WORLDS:
        run_set = json.loads(clone.joinpath("release", f"check-{world}.json").read_text())["run_set"]
        reproduced[world] = gate.reproduce(clone, world, run_set, freeze)
    assert gate.problems(clone, reproduced) == []
