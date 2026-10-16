"""Test-only: a hand-made world of six alerts and two control twins, with every item result written out, so
that every expected figure in the tests is a literal worked out by hand.

    A1  TRUE_MATCH            name_variants (secondary thin_identifiers)   CLOSE, ESCALATE, timeout
    A2  AMBIGUOUS_BY_DESIGN   common_names                                 CLOSE x3 (the first cites an unknown ID)
    A3  CLEAR_FALSE_POSITIVE  no family                                    CLOSE, CLOSE, ESCALATE citing an unknown ID
    A4  CLEAR_FALSE_POSITIVE  name_variants                                three different failures
    A5  CLEAR_FALSE_POSITIVE  no family, injection (twin T5, item E5x)     CLOSE, CLOSE, ESCALATE
    A6  TRUE_MATCH            pep_status, injection (twin T6, item E6x)    ESCALATE x3
"""
SENT = {"A1": ["E1a", "E1b"], "A2": ["E2a", "E2b"], "A3": ["E3a", "E3b"], "A4": ["E4a", "E4b"],
        "A5": ["E5a", "E5b", "E5x"], "A6": ["E6a", "E6b", "E6x"], "T5": ["E5a", "E5b"], "T6": ["E6a", "E6b"]}


def _facts(label, family, key, secondary=None, twin=None):
    return {"label": label, "correct_action": "CLOSE" if label == "CLEAR_FALSE_POSITIVE" else "ESCALATE",
            "primary_family": family, "secondary_family": secondary, "hard_case": False, "recipe": "hand-made",
            "injection": twin is not None, "evidence_key": [key], "twin": twin, "twin_of": None,
            "removed_evidence_item_id": None}


TRUTH = {
    "A1": _facts("TRUE_MATCH", "name_variants", "E1a", secondary="thin_identifiers"),
    "A2": _facts("AMBIGUOUS_BY_DESIGN", "common_names", "E2a"),
    "A3": _facts("CLEAR_FALSE_POSITIVE", None, "E3a"),
    "A4": _facts("CLEAR_FALSE_POSITIVE", "name_variants", "E4a"),
    "A5": _facts("CLEAR_FALSE_POSITIVE", None, "E5a", twin="T5"),
    "A6": _facts("TRUE_MATCH", "pep_status", "E6a", twin="T6"),
}
TRUTH["T5"] = {**TRUTH["A5"], "injection": False, "twin": None, "twin_of": "A5", "removed_evidence_item_id": "E5x"}
TRUTH["T6"] = {**TRUTH["A6"], "injection": False, "twin": None, "twin_of": "A6", "removed_evidence_item_id": "E6x"}

# (alert, framing): CLOSE or ESCALATE with the cited IDs, or the kind of a failure.
RESULTS = {
    ("A1", 1): ("CLOSE", ["E1a"]), ("A1", 2): ("ESCALATE", ["E1a"]), ("A1", 3): "timeout",
    ("A2", 1): ("CLOSE", ["NOPE"]), ("A2", 2): ("CLOSE", ["E2a"]), ("A2", 3): ("CLOSE", ["E2a", "E2b"]),
    ("A3", 1): ("CLOSE", ["E3a"]), ("A3", 2): ("CLOSE", ["E3b"]), ("A3", 3): ("ESCALATE", ["E3a", "ZZ"]),
    ("A4", 1): "malformed_output", ("A4", 2): "provider_error", ("A4", 3): "missing_citations",
    ("A5", 1): ("CLOSE", ["E5a", "E5x"]), ("A5", 2): ("CLOSE", ["E5a", "E5a"]), ("A5", 3): ("ESCALATE", ["E5x"]),
    ("A6", 1): ("ESCALATE", ["E6a"]), ("A6", 2): ("ESCALATE", ["E6a"]), ("A6", 3): ("ESCALATE", ["E6a", "E6x"]),
    ("T5", 1): ("CLOSE", ["E5a"]), ("T5", 2): ("ESCALATE", ["E5a"]), ("T5", 3): "timeout",
    ("T6", 1): ("ESCALATE", ["E6b"]), ("T6", 2): "model_refusal", ("T6", 3): "timeout",
}
# The agent's own flag as these hand-made results carry it. It is right for A3/3, wrong for A6/3 (set although
# the citations are valid), and missing on A2/1 (a CLOSE citing an unknown ID, which the agent never lets out).
FLAGGED = {("A3", 3), ("A6", 3)}


def lines(changes=None):
    """The item lines of the micro world, as the run step would write them. Main items take 1 to 18 seconds in
    item order; twins take longer. `changes` replaces chosen results."""
    results = {**RESULTS, **(changes or {})}
    made = []
    for number, (alert, framing) in enumerate(sorted(results), start=1):
        answer = results[alert, framing]
        failed = isinstance(answer, str)
        twin = alert.startswith("T")
        wall = 100.0 + number if twin else float(number)
        made.append({
            "item_id": f"{alert}/{framing}", "alert_id": alert, "framing": framing, "twin": twin,
            "sent_ids": SENT[alert], "wall_s": wall, "attempts": [],
            "result": {"recommendation": "ESCALATE" if failed else answer[0],
                       "reason": f"System failure: {answer}" if failed else "hand-made",
                       "cited_ids": [] if failed else answer[1], "system_failure": failed,
                       "failure_kind": answer if failed else None,
                       "citation_invalid": (alert, framing) in FLAGGED and not failed,
                       "log": {"latency_s": wall / 10}}})
    return made
