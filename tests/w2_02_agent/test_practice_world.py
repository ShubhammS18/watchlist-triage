"""W2-02: the rules on whole worlds. On the practice world, rebuilt from its recorded seed and with its labels read,
every rule decision is the correct action, in every framing, and every rule close cites at least one item of the
supporting evidence key. On the frozen world, whose labels are not read, the rules decide the same number of alerts in
every framing, as the pre-flight counted from the public files."""
import collections
import json

from baseline_agent.payload import build_payload
from framings import FRAMINGS, frame
from triage_agent.rules import decide
from worldgen.harness_twins import load_twins
from worldgen.loader import load_alerts

from conftest import PRACTICE_HASH, REPO


def decisions(world):
    """{(alert id, framing): what the rules decide, or None} for every alert and twin of a world."""
    agent_dir = world.joinpath("agent")
    return {(alert["id"], framing): decide(build_payload(frame(alert, framing))["items"])
            for alert in [*load_alerts(agent_dir), *load_twins(agent_dir)] for framing in FRAMINGS}


def test_on_the_practice_world_every_rule_decision_is_correct_and_every_close_cites_the_key(practice_world):
    from worldgen.truth import load_truth
    assert json.loads(practice_world.joinpath("MANIFEST.json").read_text(encoding="utf-8"))["world_hash"] == PRACTICE_HASH
    truth = load_truth(practice_world.joinpath("hidden"))
    made = decisions(practice_world)
    counts = collections.Counter()
    for (alert_id, framing), decided in made.items():
        facts = truth[alert_id]
        if decided is None:
            counts["model"] += 1
            continue
        recommendation, _, cited = decided
        assert recommendation == facts["correct_action"], (alert_id, framing, facts["label"])
        if recommendation == "CLOSE":
            assert set(cited) & set(facts["evidence_key"]), (alert_id, framing)
        counts[recommendation] += 1
    for alert_id in {alert_id for alert_id, _ in made}:  # the same in every framing
        assert len({None if made[alert_id, f] is None else made[alert_id, f][0] for f in FRAMINGS}) == 1, alert_id
    assert sum(counts.values()) == 615 * len(FRAMINGS) and counts["CLOSE"] > 0 and counts["ESCALATE"] > 0


def test_on_the_frozen_world_the_rules_decide_what_the_public_files_settle():
    made = decisions(REPO.joinpath("data", "world"))
    per_framing = {framing: collections.Counter(None if made[key] is None else made[key][0]
                                                for key in made if key[1] == framing) for framing in FRAMINGS}
    for counts in per_framing.values():  # 600 alerts and 15 twins: escalated 58 + 9, closed 252, to the model 290 + 6
        assert counts == {"ESCALATE": 67, "CLOSE": 252, None: 296}
