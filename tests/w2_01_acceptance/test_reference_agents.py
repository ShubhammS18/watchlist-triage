"""W2-01 and AC-7: the two reference agents, three clean runs each on the frozen world with the sourced files, are
eligible and FAIL the release check: always-close fails the zero-miss target and always-escalate fails the time
target."""
import pytest

from harness import release_check

from conftest import make_set


@pytest.fixture(scope="module", params=["always_close", "always_escalate"])
def judged(request, tmp_path_factory):
    out, run_set, _ = make_set(tmp_path_factory.mktemp(request.param), request.param)
    return request.param, release_check.check(out, run_set)


def test_a_reference_agent_is_eligible_and_fails(judged):
    _, result = judged
    assert result["not_eligible_because"] == [] and result["result"] == "FAIL"


def test_each_reference_agent_fails_where_ac7_says_and_for_the_expected_reasons(judged):
    agent, result = judged
    if agent == "always_close":  # it closes every true match and every ambiguous alert
        assert result["failed"] == ["ambiguous_closed", "citation_accuracy", "true_matches_closed"]
        assert all(count > 0 for count in result["targets"]["true_matches_closed"]["per_run"].values())
    else:  # it escalates every clear false positive, so it closes nothing and saves no time
        assert result["failed"] == ["citation_accuracy", "modelled_review_time", "over_escalation"]
        assert result["targets"]["citation_accuracy"]["value"]["not_applicable"] is True
        assert result["targets"]["modelled_review_time"]["per_run"] == dict.fromkeys(result["runs"]["valid"], False)
