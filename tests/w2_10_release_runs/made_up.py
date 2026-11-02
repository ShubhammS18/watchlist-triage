"""W2-10 dry run: made-up releases, built the way docs/w2-10-release-runs.md says the real one is, in a shared clone
of the repository, never in it. No model is called: every run is made by W2-08's test candidate agent with the stub
provider (release_common), and the rehearsal's practice world is the real one, made from seed 20261027 by the
repository's own generator into a temporary folder."""
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import release_common as rc
import release_gate as gate
from test_generation import PATCH  # W2-08's test generator that rejects its first tries

from baseline_run.copy_step import copy_baseline
from harness import audit, release, release_check
from worldgen.truth import load_truth

BEHAVIOURS = {"valid": {}, "killed": {}, "aborted": {"abort_after": 40}, "unsafe": {"close_true_match": True},
              "refusals": {"refusals": True}}
FULL = ("valid", "killed", "aborted", "valid", "valid")  # three valid runs, one killed and one aborted, replaced
SPEND, KILLED_SPEND, BALANCE = Decimal("0.10"), Decimal("0.05"), Decimal("4.56")


def practice_world(folder):
    """The practice world (seed 20261027), made by the repository's generator outside the repository."""
    world = Path(folder, "practice")
    subprocess.run([sys.executable, "-B", "-m", "worldgen", "--seed", "20261027", "--out", str(world)], cwd=rc.REPO,
                   check=True, capture_output=True)
    return world


class Release:
    """A made-up release: the clone, its freeze commit and the data its release log is written from."""

    def __init__(self, folder):
        self.folder, self.clone = Path(folder), Path(folder, "repo")
        self.outs, self.plans, self.spends = {}, {}, {}

    def commit(self, message):
        rc.git(self.clone, "add", "-A")
        rc.git(self.clone, "commit", "-q", "--allow-empty", "-m", message)
        return rc.git(self.clone, "rev-parse", "HEAD").strip()

    def runs(self, at, world, plan, truth, name, workers=1):
        """Runs of `plan` on `world`, made with records.REPO at `at`, killed where the plan says. Returns the output."""
        with rc.at(at):
            out, ids = rc.make_runs(self.folder.joinpath(name), world, [BEHAVIOURS[p] for p in plan], truth, workers)
        for kind, run_id in zip(plan, ids):
            if kind == "killed":
                rc.kill(out, run_id)
        self.outs[name], self.plans[name] = out, dict(zip(ids, plan))
        return out

    def checkpoints(self, name):
        """Copy the checkpoint of every run of `name` that wrote one into audit/checkpoints/."""
        for run_dir in sorted(p for p in self.outs[name].iterdir() if p.is_dir() and p.name != "sets"):
            if run_dir.joinpath(audit.CHECKPOINT).is_file():
                target = self.clone.joinpath("audit", "checkpoints", f"{run_dir.name}.json")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(run_dir.joinpath(audit.CHECKPOINT).read_bytes())

    def run_set(self, world):
        index = rc.records.read_index(self.clone.joinpath("release", world))
        return index["runs"][0]["run_set"] if index["runs"] else gate.NO_RUN_SET

    def check(self, world):
        """The release check's output for `world` at the clone's HEAD, as the command prints it."""
        with rc.at(self.clone):
            result = release_check.check(self.clone.joinpath("release", world), self.run_set(world),
                                         release={"freeze": self.freeze, "fresh": world == "fresh"})
        return gate.output_text(result).encode("utf-8")

    def log(self, spends=None, tag="release-1-freeze", tag_line=None):
        """The release log, written from the committed data. `spends` is {run ID: Spend USD}; by default 0.10 a run
        and 0.05 for a killed run."""
        spends = {**self.spends, **(spends or {})}
        balance, rows, totals = BALANCE, {}, {}
        ordered = sorted((run_id, name) for name in self.plans for run_id in self.plans[name])
        for run_id, name in ordered:
            spend = spends.get(run_id, KILLED_SPEND if self.plans[name][run_id] == "killed" else SPEND)
            rows[run_id] = (f"{balance}", f"{balance - spend}", f"{spend}")
            balance -= spend
            totals[name] = totals.get(name, Decimal(0)) + spend
        text = ["# Release 1 log", "", f"- Freeze commit: `{self.freeze}`, tag `{tag}`", "", "## Rehearsal",
                "| " + " | ".join(gate.REHEARSAL_COLUMNS) + " |", "|" + "---|" * len(gate.REHEARSAL_COLUMNS)]
        for entry in rc.records.read_index(self.outs["rehearsal"])["runs"]:
            manifest = gate._json(self.outs["rehearsal"].joinpath(entry["run_id"], "manifest.json"))
            commit = manifest["git"]["commit"][:12] if manifest else "unknown"
            text.append(f"| 2 Nov 2026 | `{entry['run_id']}` | `{commit}` | `{entry['run_set'][:8]}` | {entry['state']} | "
                        f"made up | {harness(entry)} | {' | '.join(rows[entry['run_id']])} | 1900 | test |")
        line = tag_line or f"{self.freeze}\trefs/tags/{tag}^{{}}"
        text += ["", "## Freeze and push", "", "```", "2026-11-02T12:00:00Z", line, "```", "", "## Generation", ""]
        outputs = {world: gate._json(self.clone.joinpath("release", f"check-{world}.json")) for world in gate.WORLDS}
        for world in gate.WORLDS:
            text += ["", f"## {gate.HEADINGS[world]}", "| " + " | ".join(gate.RUN_COLUMNS) + " |",
                     "|" + "---|" * len(gate.RUN_COLUMNS)]
            if outputs[world] is None:  # a variant built without check outputs
                continue
            runs = (outputs[world]["release"]["runs"] or {"valid": [], "replaced": {}})
            index = rc.records.read_index(self.clone.joinpath("release", world))
            for n, entry in enumerate(index["runs"], 1):
                run_id = entry["run_id"]
                valid = run_id in runs["valid"]
                point = self.clone.joinpath("audit", "checkpoints", f"{run_id}.json").is_file()
                text.append(f"| {n} | `{run_id}` | {entry['state']} | {'valid' if valid else 'replaced'} | "
                            f"{'' if valid else runs['replaced'][run_id]} | {entry['rerun_cause'] or 'none'} | "
                            f"{'yes' if point else 'no'} | {harness(entry)} | {' | '.join(rows[run_id])} | test |")
        text += ["", "## Results", "| " + " | ".join(gate.RESULT_COLUMNS) + " |", "|---|---|---|---|"]
        for world, output in outputs.items():
            if output is not None:
                text.append(f"| {world} | `{output['run_set'][:8]}` | `release/check-{world}.json` | {output['result']} |")
        text += ["", "## Console sign-off", "", "| Run set | Console USD | Harness USD | Sign-off |", "|---|---|---|---|",
                 "", "## Running total", "",
                 f"Wave-2 spend: USD {Decimal('0.95') + sum(totals.values())} (before this log 0.95 + rehearsal "
                 f"{totals.get('rehearsal', 0)} + frozen {totals.get('frozen', 0)} + fresh {totals.get('fresh', 0)})", ""]
        self.clone.joinpath(release.RELEASE_LOG).write_text("\n".join(text), encoding="utf-8")

    def amend(self, change, message="Variant (test)"):
        """Change the published release in a commit on top of it, and move the publish tag there."""
        change(self)
        self.commit(message)
        rc.git(self.clone, "tag", "-f", gate.PUBLISH_TAG)

    def restore(self):
        """Back to the published release as built."""
        rc.git(self.clone, "reset", "-q", "--hard", self.published)
        rc.git(self.clone, "clean", "-qfdx")
        rc.git(self.clone, "tag", "-f", gate.PUBLISH_TAG, self.published)
        for name, commit in self.tags.items():
            rc.git(self.clone, "tag", "-f", name, commit)
        for name in set(rc.git(self.clone, "tag").split()) - set(self.tags) - {gate.PUBLISH_TAG}:
            rc.git(self.clone, "tag", "-d", name)


def harness(entry):
    cost = gate._cost(entry)
    return "none" if cost is None else f"{Decimal(cost.numerator) / Decimal(cost.denominator):.4f}"


def build(folder, practice, frozen=FULL, fresh=("valid",) * 3, rehearsal=("valid",), reject=0, rehearsal_world=None,
          rehearsal_workers=1, before_freeze=None, rehearsal_after_freeze=False, checkpoints_before_generation=False,
          before_checks=None, checks=True):
    """A made-up release, published and tagged. The keywords make the variants of the dry run."""
    made = Release(folder)
    clone = made.clone
    subprocess.run(["git", "clone", "-q", "--shared", str(rc.REPO), str(clone)], check=True)
    for key, value in (("user.name", "Test"), ("user.email", "test@example.invalid"), ("commit.gpgsign", "false")):
        rc.git(clone, "config", key, value)
    if reject:
        path = clone.joinpath("worldgen", "build.py")
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("def generate(seed=None):\n", PATCH.format(reject=reject, crash=False)),
                        encoding="utf-8")
        made.commit("A test generator (test)")

    def rehearse():
        world = rehearsal_world(clone) if rehearsal_world else practice
        made.runs(clone, world, rehearsal, rc.fresh_truth(world), "rehearsal", workers=rehearsal_workers)
        copy_baseline(made.outs["rehearsal"], clone.joinpath(gate.REHEARSAL_DIR))
        made.checkpoints("rehearsal")
        made.commit("W2-10: rehearsal evidence (test)")

    if not rehearsal_after_freeze:
        rehearse()
    if before_freeze:
        before_freeze(clone)
        made.commit("A change before the freeze (test)")
    clone.joinpath("docs").mkdir(exist_ok=True)
    clone.joinpath(release.RELEASE_LOG).write_text("# Release 1 log\n\n## Freeze and push\n", encoding="utf-8")
    made.freeze = made.commit("W2-10: freeze (test)")
    rc.git(clone, "tag", "-a", "-m", "freeze", "release-1-freeze")
    if rehearsal_after_freeze:
        rehearse()
    record = release.make_fresh_world(made.freeze, made.folder.joinpath("fresh-world"),
                                      made.folder.joinpath("generation.json"), repo=clone) \
        if not rehearsal_after_freeze else None
    checkout = made.folder.joinpath("checkout")
    rc.git(clone, "worktree", "add", "-q", "--detach", str(checkout), made.freeze)
    if rehearsal_after_freeze:  # the generation needs HEAD at the freeze: make it from the freeze's own checkout
        record = release.make_fresh_world(made.freeze, made.folder.joinpath("fresh-world"),
                                          made.folder.joinpath("generation.json"), repo=checkout)

    def generation():
        clone.joinpath("release").mkdir(exist_ok=True)
        clone.joinpath(release.GENERATION).write_bytes(made.folder.joinpath("generation.json").read_bytes())
        made.commit("Release 1: generation record (test)")

    if not checkpoints_before_generation:
        generation()
    if frozen:
        made.runs(checkout, checkout.joinpath("data", "world"), frozen, load_truth(), "frozen")
    if fresh and record["accepted"]:
        world = made.folder.joinpath("fresh-world")
        made.runs(checkout, world, fresh, rc.fresh_truth(world), "fresh")
    for name in ("frozen", "fresh"):
        if name in made.outs:
            made.checkpoints(name)
            made.commit(f"Release 1: {name} checkpoints (test)")
    if checkpoints_before_generation:
        generation()
    for name in ("frozen", "fresh"):
        if name in made.outs:
            copy_baseline(made.outs[name], clone.joinpath("release", name))
    made.commit("Release 1: run output (test)")
    rc.git(clone, "worktree", "remove", "--force", str(checkout))
    if before_checks:
        before_checks(clone)
        made.commit("A change after the freeze (test)")
    # both outputs are made from the clean tree first, then copied in: an output written into the tree before the
    # other world's check would make that check see an untracked file (review round 1)
    outputs = {world: made.check(world) for world in (gate.WORLDS if checks else ())}
    for world, output in outputs.items():
        clone.joinpath("release", f"check-{world}.json").write_bytes(output)
    made.commit("Release 1: check outputs (test)")
    made.log()
    made.published = made.commit("Release 1: publish (test)")
    rc.git(clone, "tag", gate.PUBLISH_TAG)
    made.tags = {name: rc.git(clone, "rev-parse", name).strip() for name in rc.git(clone, "tag").split()
                 if name != gate.PUBLISH_TAG}
    return made
