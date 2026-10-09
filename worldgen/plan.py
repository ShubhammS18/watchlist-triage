"""The planting plan: the recipe table of docs/world-design.md as data.

Fully deterministic (no random numbers), so the counts are exact:
30 TRUE_MATCH (6 per primary family), 30 AMBIGUOUS_BY_DESIGN (6 per family),
540 CLEAR_FALSE_POSITIVE (30 in each of four hard families, 420 plain).

Identifier outcomes are written (date of birth, ID number, nationality) with
A = agrees, C = conflicts, U = unavailable on at least one side.
"""
from . import load_config

FAMILIES = ("name_variants", "common_name_collisions", "thin_identifiers", "pep_status", "contradictory_evidence")
HARD_FAMILIES = FAMILIES[:4]
LABELS = ("TRUE_MATCH", "AMBIGUOUS_BY_DESIGN", "CLEAR_FALSE_POSITIVE")

# How a customer name departs from the watchlist name; every kind stays within one edit per part.
VARIANTS = (("spelling",), ("order", "title"), ("alias",), ("diacritic", "spelling"), ("title", "spelling"), ("alias", "diacritic"))

CLEAN = (("A", "A", "A"), ("A", "U", "A"), ("A", "A", "C"), ("U", "A", "A"), ("A", "A", "U"), ("A", "A", "A"))
DECISIVE_CONFLICT = (("C", "C"), ("C", "U"), ("U", "C"))

# Secondary families: the first two TRUE_MATCH alerts of each primary family also carry one of these.
SECONDARY = {
    "name_variants": ("pep_status", "contradictory_evidence"),
    "common_name_collisions": ("name_variants", "pep_status"),
    "thin_identifiers": ("name_variants", "common_name_collisions"),
    "pep_status": ("name_variants", "common_name_collisions"),
    "contradictory_evidence": ("name_variants", "pep_status"),
}
PEP_OVERLAY = ({"status": "current"}, {"status": "former", "offset": 335})
# The name form a TRUE_MATCH alert takes when name_variants is its secondary family, by primary family.
SECONDARY_VARIANT = {
    "common_name_collisions": ("diacritic", "spelling"),
    "thin_identifiers": ("spelling",),
    "pep_status": ("order", "title"),
    "contradictory_evidence": ("title", "spelling"),
}

TRUE_PEP = (
    ("current", {"status": "current"}, ()),
    ("former_inside_a", {"status": "former", "offset": 90}, ()),
    ("former_inside_b", {"status": "former", "offset": 364}, ()),
    ("former_beyond_risk", {"status": "former", "offset": 540}, ("continuing_risk",)),
    ("relative_field", {"relationship_field": "relative", "related_offset": 180}, ()),
    ("associate_snippet", None, ("relationship",)),
)
AMBIGUOUS_PEP = (
    ("beyond_366", {"status": "former", "offset": 366}, (), CLEAN[0]),
    ("beyond_540", {"status": "former", "offset": 540}, (), CLEAN[2]),
    ("beyond_1095", {"status": "former", "offset": 1095}, (), CLEAN[3]),
    ("inside_one_identifier", {"status": "former", "offset": 335}, (), ("A", "U", "U")),
    ("relationship_snippet", None, ("relationship",), ("U", "A", "U")),
    ("no_end_date", {"status": "former"}, (), ("A", "U", "U")),
)


def _case(label, primary, recipe, ident, **extra):
    case = {"label": label, "primary": primary, "secondary": None, "recipe": recipe, "ident": ident,
            "variant": (), "common": False, "pep": None, "snippets": [], "group": None}
    case.update(extra)
    return case


def _conflict(i):
    """Decisive-conflict pattern for the i-th conflicting alert: date of birth, ID number, nationality."""
    dob, idn = DECISIVE_CONFLICT[i % 3]
    return (dob, idn, ("A", "C", "U")[(i // 3) % 3])


def _true_case(family, i):
    if family == "name_variants":
        case = _case("TRUE_MATCH", family, "tm_name_variants", CLEAN[i], variant=VARIANTS[i])
    elif family == "common_name_collisions":
        case = _case("TRUE_MATCH", family, "tm_common_names", ("A", "A", ("A", "C", "A", "U", "A", "C")[i]), common=True)
    elif family == "thin_identifiers":
        case = _case("TRUE_MATCH", family, "tm_thin_identifiers", (("A", "U", "U"), ("U", "A", "U"))[i % 2],
                     snippets=["identity_link"])
    elif family == "pep_status":
        name, pep, snippets = TRUE_PEP[i]
        case = _case("TRUE_MATCH", family, f"tm_pep_{name}", CLEAN[i], pep=dict(pep) if pep else None, snippets=list(snippets))
    else:
        case = _case("TRUE_MATCH", family, "tm_contradictory", ("A", "A", ("C", "A", "C", "U", "C", "A")[i]),
                     snippets=["contradicts"])
    if i < 2:
        secondary = SECONDARY[family][i]
        case["secondary"] = secondary
        if secondary == "name_variants":
            case["variant"] = SECONDARY_VARIANT[family]
        elif secondary == "common_name_collisions":
            case["common"] = True
        elif secondary == "pep_status":
            case["pep"] = dict(PEP_OVERLAY[i])
        else:
            case["ident"] = ("A", "A", "C")           # still a clean identity: a nationality conflict does not break it
            case["snippets"].append("contradicts")
    return case


def _ambiguous_case(family, i):
    label = "AMBIGUOUS_BY_DESIGN"
    if family == "name_variants":
        return _case(label, family, "am_name_variants", (("A", "U", "U"), ("U", "A", "U"), ("U", "U", "A"))[i % 3],
                     variant=VARIANTS[i])
    if family == "common_name_collisions":
        return _case(label, family, "am_common_names", ("U", "U", ("A", "C")[i % 2]), common=True)
    if family == "thin_identifiers":
        return _case(label, family, "am_thin_identifiers",
                     (("A", "U", "U"), ("U", "A", "U"), ("U", "U", "A"), ("U", "U", "C"), ("A", "U", "U"), ("U", "A", "U"))[i])
    if family == "pep_status":
        name, pep, snippets, ident = AMBIGUOUS_PEP[i]
        return _case(label, family, f"am_pep_{name}", ident, pep=dict(pep) if pep else None, snippets=list(snippets))
    if i >= 4:
        # A decisive identifier conflicts and none agrees, but a snippet links the customer to the listed person.
        # rubric, "What evidence is sufficient to close": the snippet blocks the close, so the alert is ambiguous.
        return _case(label, family, "am_contradictory_link", (("C", "U", "A"), ("U", "C", "C"))[i - 4],
                     snippets=["identity_link"])
    ident = (("A", "C", "A"), ("C", "A", "U"), ("A", "C", "C"), ("C", "A", "A"))[i]
    return _case(label, family, "am_contradictory", ident, snippets=["contradicts"] if i % 2 == 0 else [])


def _clear_false_positive_cases(offsets):
    label = "CLEAR_FALSE_POSITIVE"
    cases = []
    for i in range(30):
        cases.append(_case(label, "name_variants", "cfp_name_variants", _conflict(i), variant=VARIANTS[i % 6]))
    for i in range(30):
        cases.append(_case(label, "common_name_collisions", "cfp_common_names", _conflict(i), common=True))
    for i in range(30):
        cases.append(_case(label, "thin_identifiers", "cfp_thin_identifiers", (("C", "U", "U"), ("U", "C", "U"))[i % 2]))
    for i in range(30):
        if i % 5 == 4:                                   # six relatives and close associates
            if (i // 5) % 2 == 0:
                # the related PEP is in office, left 180 days ago, or left 730 days ago
                pep, snippets = {"relationship_field": "relative", "related_offset": (0, 180, 730)[(i // 10) % 3]}, []
            else:
                pep, snippets = None, ["relationship"]
        else:                                            # twenty-four PEPs spread over every configured offset, twice
            offset = offsets[(i - i // 5) % len(offsets)]
            pep, snippets = ({"status": "current"} if offset == 0 else {"status": "former", "offset": offset}), []
        cases.append(_case(label, "pep_status", "cfp_pep", _conflict(i), pep=pep, snippets=snippets))
    for i in range(420):
        cases.append(_case(label, None, "cfp_plain", _conflict(i)))
    return cases


def make_plan():
    config = load_config()
    offsets = config["pep_offset_days"]
    cases = [_true_case(f, i) for f in FAMILIES for i in range(config["counts"]["true_match_per_primary_family"])]
    cases += [_ambiguous_case(f, i) for f in FAMILIES for i in range(config["counts"]["ambiguous_per_family"])]
    cases += _clear_false_positive_cases(offsets)
    return cases, _share_watchlist_entries(cases)


def _share_watchlist_entries(cases):
    """Put some alerts in groups of three that share one watchlist entry (three customers with the same name).

    The group size must not depend on the label, so every label has the same share of its alerts in a group of
    three: 20% (6 of 30 TRUE_MATCH, 6 of 30 AMBIGUOUS, 108 of 540 CLEAR_FALSE_POSITIVE). Everything else is alone.
    Returns {group number: what the shared entry needs}: whether its name is a common one, and its PEP fields.
    """
    anchors = [c for c in cases if c["primary"] == "common_name_collisions" and c["label"] != "CLEAR_FALSE_POSITIVE"]
    members = [c for c in cases if c["primary"] == "common_name_collisions" and c["label"] == "CLEAR_FALSE_POSITIVE"]
    plain = [c for c in cases if c["recipe"] == "cfp_plain"]
    assert len(anchors) == 12 and len(members) == 30
    groups = {}

    def group_of(shared_cases, common, pep):
        number = len(groups)
        groups[number] = {"common": common, "pep": pep, "variant": ()}
        for case in shared_cases:
            case["group"] = number

    for k, anchor in enumerate(anchors):             # 12 groups: the listed person or an unresolved customer, plus two others
        group_of([anchor, members[2 * k], members[2 * k + 1]], True, anchor["pep"])
    for k in range(2):                               # 2 groups of three common-name clear false positives
        group_of(members[24 + 3 * k:27 + 3 * k], True, None)
    for k in range(26):                              # 26 groups of three plain clear false positives
        group_of(plain[3 * k:3 * k + 3], False, None)
    for label in LABELS:
        mine = [c for c in cases if c["label"] == label]
        assert 5 * sum(c["group"] is not None for c in mine) == len(mine), label
    return groups
