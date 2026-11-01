"""W2-08: what the design doc must say (review round 1, finding 8): no code can prove that the freeze was tagged and
pushed before the fresh world was made; the evidence for that order goes in the release log."""
from release_common import REPO

DOC = " ".join(REPO.joinpath("docs", "w2-08-release-protocol.md").read_text(encoding="utf-8").split())  # lines joined


def test_the_push_before_generation_order_is_stated_as_not_provable_by_code():
    assert "No code can prove that the freeze tag was pushed before the fresh world was made" in DOC


def test_the_release_log_holds_the_evidence_for_that_order():
    assert "the evidence that the freeze tag was public before the fresh world was made" in DOC
