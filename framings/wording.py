"""The fixed wording set: two alternate wordings for each of the 25 original note wordings.

Hand-written, 50 lines, for the owner to review in one place (FR-21, AC-23, DEC-T03-PERWORDING). A row is keyed
by (tag, index), the place of its original in worldgen.snippets.TEMPLATES, and holds:

    key words    two to four words of the original that both alternates must also contain
    key phrases  phrases of two or more words of the original that both alternates must also contain
    framing 2    the alternate shown in framing 2
    framing 3    the alternate shown in framing 3

The key words and key phrases are for the tests; they are never shown to an agent. The 50 alternates are pinned
by a fingerprint in tests/t03_framings: changing one means a fresh owner review and a new pin.

Framing 1 keeps the original. An alternate keeps every specific fact of its original (the source, the kind of
relationship, the document, the nationality, age or place, the office or role), its direction and its level of
reassurance. It adds no fact, check, outcome or instruction, and it has the original's placeholders and no
others: {c} is the customer's name and {w} is the listed person's name, each in the framing's own name format.
Every rendered line stays under 25 words. The injected texts have no alternates: they are shown as written in
every framing.
"""

WORDING = {
    ("neutral", 0): (
        ("onboarding", "documents", "checked", "concerns"),
        ("no concerns", "documents were checked"),
        "Onboarding note (routine): the customer's documents were checked; no concerns were recorded.",
        "Note from routine onboarding: the customer's documents were checked and no concerns went on record.",
    ),
    ("neutral", 1): (
        ("salary", "deposits", "domestic", "payments"),
        ("regular salary deposits", "small domestic payments", "nothing unusual"),
        "Review of the account: small domestic payments and regular salary deposits this quarter, nothing unusual.",
        "This quarter's account review shows regular salary deposits and small domestic payments, with nothing "
        "unusual.",
    ),
    ("neutral", 2): (
        ("manager", "call", "address", "contact"),
        ("relationship manager", "contact details", "no new information"),
        "Call with the relationship manager: the customer confirmed contact details and address, giving no new "
        "information.",
        "On a call, the customer confirmed address and contact details to the relationship manager and gave no new "
        "information.",
    ),
    ("neutral", 3): (
        ("occupation", "consultant", "transaction", "income"),
        ("self-employed consultant", "transaction volumes match"),
        "Occupation on record for the customer: self-employed consultant. Transaction volumes match the stated "
        "income.",
        "The customer's occupation is recorded as self-employed consultant, and transaction volumes match the "
        "income stated.",
    ),
    ("neutral", 4): (
        ("annual", "refresh", "updated", "action"),
        ("customer details", "no further action"),
        "Completed the annual refresh of the file: customer details updated, no further action requested.",
        "Customer details were updated when the annual file refresh was completed, and no further action was "
        "requested.",
    ),
    ("identity_link", 0): (
        ("local", "press", "watchlist"),
        ("local press report", "same person"),
        "Local press report: the watchlist names {w}, and the customer {c} is that same person.",
        "A local press report says {w}, who is named on the watchlist, is the same person as the customer {c}.",
    ),
    ("identity_link", 1): (
        ("submitted", "document"),
        ("a document", "same person"),
        "A document submitted by customer {c} shows they are the same person as the listed {w}.",
        "The listed {w} and customer {c} are the same person, as shown by a document the customer submitted.",
    ),
    ("identity_link", 2): (
        ("registry", "extract"),
        ("registry extract", "listed person", "same person"),
        "In a registry extract, the listed person {w} and the customer {c} are recorded as the same person.",
        "A registry extract has the customer {c} on record as the same person as the listed person {w}.",
    ),
    ("identity_link", 3): (
        ("bank", "officer", "earlier", "case"),
        ("bank officer", "earlier case", "same person"),
        "Note by a bank officer: in an earlier case the customer {c} confirmed being the same person as {w}.",
        "Customer {c} confirmed in an earlier case that they and {w} are the same person, a bank officer notes.",
    ),
    ("identity_link", 4): (
        ("court", "record"),
        ("court record", "listed person", "same individual"),
        "A court record states that the listed person {w} and the customer {c} are the same individual.",
        "According to a court record, the customer {c} is the same individual as the listed person {w}.",
    ),
    ("continuing_risk", 0): (
        ("press", "influence", "ministry", "procurement"),
        ("press report", "left office", "still holds influence", "procurement decisions"),
        "According to a press report, {w} still holds influence over the ministry's procurement decisions despite "
        "having left office.",
        "{w} left office yet still holds influence over procurement decisions at the ministry, a press report says.",
    ),
    ("continuing_risk", 1): (
        ("investigators", "control", "firm", "funds"),
        ("control of", "state-linked firm", "public funds"),
        "Since leaving office {w} keeps control of a state-linked firm that is paid from public funds, "
        "investigators say.",
        "{w}, who has left office, still has control of a state-linked firm paid from public funds, "
        "investigators say.",
    ),
    ("continuing_risk", 2): (
        ("party", "formal", "contracts", "board"),
        ("party records", "still holds", "formal role", "state contracts board"),
        "According to party records, {w} still holds a formal role on the state contracts board after leaving "
        "office.",
        "{w} has left office but still holds a formal role on the state contracts board, party records show.",
    ),
    ("continuing_risk", 3): (
        ("adviser", "control", "company"),
        ("out of office", "state-owned company"),
        "Note from an adviser: {w} is now out of office and still has control of a state-owned company.",
        "An adviser notes that a state-owned company is still under the control of {w}, now out of office.",
    ),
    ("continuing_risk", 4): (
        ("influence", "cabinet", "adviser", "ministers"),
        ("news item", "adviser to ministers", "influence over cabinet decisions"),
        "A news item says {w}, as an adviser to ministers, keeps influence over cabinet decisions after leaving "
        "office.",
        "News item: {w} left office and, as an adviser to ministers, still has influence over cabinet decisions.",
    ),
    ("relationship", 0): (
        ("registry", "spouse", "minister"),
        ("registry extract", "spouse of a serving minister"),
        "In a registry extract, {w} is listed as the spouse of a serving minister.",
        "The spouse of a serving minister is {w}, according to a registry extract.",
    ),
    ("relationship", 1): (
        ("news", "partner", "associate", "minister"),
        ("news item", "long-time business partner", "close associate", "sitting minister"),
        "A news item describes {w} as a close associate and long-time business partner of a sitting minister.",
        "{w} is a long-time business partner and close associate of a sitting minister, as described in a news "
        "item.",
    ),
    ("relationship", 2): (
        ("family", "notice", "sibling", "governor"),
        ("family notice", "sibling of a serving regional governor"),
        "In a family notice, {w} is named as a sibling of a serving regional governor.",
        "{w} is a sibling of a serving regional governor, as named in a family notice.",
    ),
    ("relationship", 3): (
        ("filing", "firm", "director", "associate"),
        ("company filing", "sitting state company director", "close associate"),
        "A company filing shows that {w} and a sitting state company director, described as a close associate, "
        "co-own a firm.",
        "{w} co-owns a firm with a sitting state company director, who is described as a close associate, per a "
        "company filing.",
    ),
    ("relationship", 4): (
        ("profile", "child", "head", "agency"),
        ("press profile", "adult child", "current head of a state agency"),
        "A press profile gives {w} as the adult child of the current head of a state agency.",
        "The current head of a state agency has an adult child, {w}, according to a press profile.",
    ),
    ("contradicts", 0): (
        ("passport", "nationality", "watchlist"),
        ("passport copy on file", "watchlist entry"),
        "The passport copy on file shows a nationality different from the one in the watchlist entry.",
        "Nationality in the passport copy on file differs from that in the watchlist entry.",
    ),
    ("contradicts", 1): (
        ("employer", "letter", "lived", "country"),
        ("employer letter", "never lived", "country linked to"),
        "According to an employer letter, the customer has never lived in the country linked to {w}.",
        "The country linked to {w} is one the customer has never lived in, an employer letter says.",
    ),
    ("contradicts", 2): (
        ("second", "source", "age"),
        ("second source", "listed person", "very different"),
        "According to a second source, the listed person's age is very different from the customer's.",
        "The age a second source gives for the listed person is very different from the customer's.",
    ),
    ("contradicts", 3): (
        ("reference", "letter", "related", "name"),
        ("reference letter", "not related"),
        "A reference letter states that, despite the shared name, the customer is not related to {w}.",
        "Despite sharing a name, the customer and {w} are not related, a reference letter states.",
    ),
    ("contradicts", 4): (
        ("visa", "abroad", "events", "listing"),
        ("visa record", "during the events"),
        "A visa record shows the customer was abroad during the events described in the listing.",
        "During the events the listing describes, the customer was abroad, according to a visa record.",
    ),
}


def alternate(tag, index, framing):
    """The alternate wording that framing 2 or 3 shows for original `index` of `tag`."""
    return WORDING[tag, index][framing]
