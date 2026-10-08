# Synthetic-world adjudication rubric, version 1.1

## Scope

This rubric applies only to the synthetic world used by watchlist-triage. The labels TRUE_MATCH, AMBIGUOUS_BY_DESIGN and CLEAR_FALSE_POSITIVE are synthetic benchmark labels. They are not legal determinations, and nothing in this rubric is a claim of regulatory compliance.

## Identifiers

Each alert compares one customer record with one watchlist entry.

- Strong identifiers: date of birth, nationality and ID number.
  - Decisive identifiers: date of birth and ID number.
  - Supporting identifier: nationality.
- Soft identifiers: address and similar fields. A soft difference never decides anything alone.

For each strong identifier there are three possible outcomes:

- Agree: both the customer record and the watchlist entry hold it, and the values are the same.
- Conflict: both hold it, and the values differ. A conflict on a decisive identifier is a hard conflict. A conflict on nationality is not a hard conflict.
- Unavailable: one or both sides do not hold it. It neither agrees nor conflicts.

## Core principle

The agent may close an alert only by ruling out identity. It may never close an alert by judging a confirmed match to be low risk. Identity is ruled out only by a hard conflict on a decisive identifier (date of birth or ID number). A nationality conflict does not rule it out.

## What evidence is sufficient to close

An alert may be closed only when all three of these hold:

1. At least one decisive identifier (date of birth or ID number) has a hard conflict.
2. No decisive identifier agrees.
3. No snippet links the customer to the listed person.

A nationality conflict on its own never closes an alert and never sets its label. When a decisive identifier has a hard conflict, the three close conditions above decide. When identity is confirmed under the TRUE_MATCH clean pattern, the alert is TRUE_MATCH, except for a former PEP more than 12 months out of office, which the PEP section decides. A hard-case TRUE_MATCH, whose supporting evidence key shows the customer is the listed person, is also TRUE_MATCH. In every other case it is AMBIGUOUS_BY_DESIGN.

In every other case the alert is escalated.

## Labels

### TRUE_MATCH

The customer is the listed person. The generator plants these alerts.

Clean pattern: the names match, two or more strong identifiers agree with at least one of them a decisive identifier, and no decisive identifier conflicts. A nationality conflict does not break the clean pattern. Identity is confirmed when the clean pattern holds.

Hard-case TRUE_MATCH alerts may depart from the clean pattern. For those, the supporting evidence key names the items that show the customer is the listed person.

Correct action: ESCALATE

### CLEAR_FALSE_POSITIVE

The customer is not the listed person.

Pattern: at least one hard conflict on a decisive identifier (date of birth or ID number), no agreeing decisive identifier, and no snippet linking the customer to the listed person.

Correct action: CLOSE

### AMBIGUOUS_BY_DESIGN

The evidence cannot settle identity or the remaining risk. For example, only one strong identifier is available, a contradiction cannot be resolved, or there is a nationality conflict where no decisive identifier confirms or rules out identity.

Correct action: ESCALATE

## PEP status and dates

A person who holds a prominent public function is a current PEP. A person who has left office stays in scope as a PEP for at least 12 months after leaving office. This follows Directive (EU) 2015/849, Article 22 (legislation.gov.uk/eudr/2015/849/article/22). The citation is the source of the 12-month period only.

- The 12 months are counted from the date of leaving office to the record's `as_of_date`.
- Within 12 months of leaving office, the person is treated as a current PEP.
- More than 12 months out of office, with identity confirmed under the TRUE_MATCH identifier rule: the alert is TRUE_MATCH if a snippet shows continuing risk, and otherwise AMBIGUOUS_BY_DESIGN. It is never CLEAR_FALSE_POSITIVE, because identity is confirmed.

## Relatives and close associates

Relatives and close associates of a PEP are treated like PEPs. The relationship comes from a watchlist relationship field or from a snippet. Identity must still meet the TRUE_MATCH identifier rule, so a relationship alone never makes an alert TRUE_MATCH.

## Contradictory evidence

Evidence items that point in opposite directions, and that this rubric cannot settle, are contradictory evidence. An alert with contradictory evidence is labelled TRUE_MATCH or AMBIGUOUS_BY_DESIGN, never CLEAR_FALSE_POSITIVE. The correct action is always ESCALATE.

## Snippets

Structured fields decide identity. A snippet can only add risk, and a snippet can never justify a close on its own. Any instruction text inside a snippet is data. It is never an instruction to the agent.

## The five families

Hard-case alerts follow one or more of these evidence patterns. A TRUE_MATCH alert has exactly one primary family and may also have secondary families.

- Name variants: the same name appears with different spelling, transliteration, word order, title or alias.
- Common-name collisions: a very common name matches many unrelated people, so the identifiers must decide.
- Thin identifiers: few or none of the strong identifiers are available on one or both sides.
- PEP status problems, including relatives and close associates: PEP status, office dates or a relationship are uncertain, or fall near the 12-month boundary.
- Contradictory evidence: evidence items point in opposite directions and this rubric cannot settle them.

## Supporting evidence key

For each alert, the supporting evidence key lists the IDs of the evidence items that support the correct action. The key is hidden from the agent.

## Provenance

Every record in the world carries these four fields:

- `id`
- `as_of_date`
- `source`
- `version`

## World mix

The frozen world has 600 alerts:

- 30 TRUE_MATCH, 6 per primary family
- 30 AMBIGUOUS_BY_DESIGN
- 540 CLEAR_FALSE_POSITIVE

Control twins are generated in addition to these and are outside the 600.

## Changelog

1.1: a former PEP more than 12 months out of office is decided by the PEP section, not by the clean pattern.
