# Framings design for T03-framings

Requirements: FR-21 and AC-23. Decision records: `DEC-T03-FRAMINGS-DESIGN` (owner decisions D1 to D7),
`DEC-T03-NOSNIPPET` (D10), `DEC-T03-PERWORDING` (D11, which replaces the per-type wording of D5) and
`DEC-T03-FR21-AMENDS-D1` (decision 12, which amends D1).

A framing is one of three presentations of the same alert. The three differ in field order, name format and note
wording, and in nothing else. T03 provides the function that produces them. Presenting every alert to an agent in
all three framings is the job of the evaluation harness, task T06; nothing in T03 shows an alert to an agent.

## The three framings

| | Framing 1 | Framing 2 | Framing 3 |
|---|---|---|---|
| Field order | as in the world | watchlist fields, customer fields, notes | notes, customer fields reversed, watchlist fields reversed |
| Name format | as written | `Dr. PLUKIL, Drigutek` | `Dr Plukil Drigutek` |
| Note wording | the original | that original's framing-2 alternate | that original's framing-3 alternate |

Framing 1 is the alert exactly as the world holds it.

**Where wording applies (D10, and decision 12 amending D1).** D1 said framings 2 and 3 are transformed "in all
three ways". That holds only where there is a note to reword. Framings 2 and 3 always differ from framing 1 and
from each other in field order and name format, and they differ in wording wherever a note exists. Of the 615
bundles (600 alerts and 15 control twins), 335 carry at least one note and 280 carry none; those 280 differ in
order and name format only.

This is the owner's reading of FR-21, recorded as `DEC-T03-FR21-AMENDS-D1`. FR-21 and the glossary in `SPEC.md`
still say the three framings differ in field order, name formatting and snippet wording without stating the
no-note case. `SPEC.md` is not changed by T03; a spec clarification is an open item for the wave-2 reopen.

## What each transformation does

**Field order.** A block is every evidence item of one kind: `customer_field`, `watchlist_field` or `snippet`.
Framing 2 shows the watchlist block, then the customer block, then the notes, and items keep their order inside
each block. Framing 3 shows the notes in their order, then the customer block reversed, then the watchlist block
reversed. A few alerts in the world have a note placed between structured fields; framings 2 and 3 gather it into
the notes block.

**Name format.** Tokens are moved and re-punctuated by position only. The code never guesses which token is a
given name or a family name. A title is a first token found in `worldgen/names/titles.txt` once its dot is
removed. Titles and accents stay as written.

- Framing 2: the title first with a trailing dot, then the last token in capitals with a comma, then the
  remaining tokens in their original order.
- Framing 3: the title first without a dot, then the last token, then the remaining tokens in their original
  order. No comma and no capitals.

Names and aliases (`name` and `alias` fields) use the same format, and so do names written inside a reworded
note. The code raises an error instead of guessing when a name has fewer than two tokens after its title, or when
capitals would change a name's normalised letters. Neither case occurs in the frozen world.

**Note wording (D11).** The code finds which original wording a note is from its text alone: it renders each of
the 25 templates in `worldgen/snippets.py` with the alert's own customer name and listed name and compares. A
note that matches exactly one original is replaced by that original's own alternate for the framing, from
`framings/wording.py`. A note that matches no original must be one of the five injected texts and is shown byte
for byte as written; any other unmatched note, or a note matching two originals, raises an error.

Each original has two hand-written alternates, 50 in all, and no model call is involved. An alternate keeps every
specific fact of its original (the source, the kind of relationship, the document, the nationality, age or place,
the office or role), its direction and its level of reassurance, and adds no fact, check, outcome or instruction.
Each row also lists two to four key-fact words and some key phrases from the original that both alternates must
contain. The whole set is laid out in `docs/framings/wording-set.md`, with the owner's review recorded as
`DEC-T03-WORDING-REVIEW-2`.

The 50 reviewed alternates are pinned by a SHA-256 fingerprint, printed in that document and held in the tests.
Changing any alternate fails the tests until the owner reviews the set again and the pin is updated.

## What never changes

Evidence IDs; dates of birth, ID numbers, nationalities, addresses, PEP status, office, relationship fields and
every date field; the five injected texts; every key of an item other than `value`. Nothing is written into
`data/world/` and the world hash is unchanged.

## Where the code is

| File | Holds |
|---|---|
| `framings/__init__.py` | `frame(alert, framing)`: the public function. Takes one alert with its evidence items (the shape `worldgen.loader` and `worldgen.harness_twins` return) and a framing number 1 to 3, and returns the framed evidence items as new dicts. |
| `framings/order.py` | field order |
| `framings/names.py` | name formats |
| `framings/recognise.py` | which original a note is, from its text |
| `framings/wording.py` | the 25 rows: key facts and two alternates each |

The package uses the standard library and three `worldgen` modules (`textutil`, `matcher`, `snippets`), which it
imports and does not change. It is a pure function of its input: no randomness, no clock, no environment lookup.
The same function serves the 15 control twins, which the tests load only through `worldgen.harness_twins`.

## How to run the tests

```
.venv/bin/python -m pytest tests/t03_framings -q -p no:cacheprovider
```

The tests cover all 600 alerts and all 15 twins in all three framings: IDs, unchanged values, names, field order,
the D10 rule with its counts, recognition of every note as one original, agreement of the T02 text-only
adjudicator across framings, determinism, an unchanged world and a static check of the package. For the wording
table they check:

- the fingerprint of the 50 alternates against the pinned value of the reviewed set;
- the key-fact words and the key phrases of each original, in both of its alternates;
- that "close associate" appears exactly as often as in the original;
- the placeholders and the length;
- the absence of instruction words (recommend, close, escalate, ignore, instruct; the rubric's phrase "close
  associate" is the one exemption);
- the polarity (a negation word appears if and only if the original has one);
- the keyword predicates of the T02 adjudicator.

Mutation tests break a copy and expect a failure.

## Decision records: active and superseded

Every record below is in `.genesis/project.json` with status `accepted`. `genesis help` documents no way to mark
a record superseded, so no status was changed there: this table is the marker.

| Decision | State | Changed by |
|---|---|---|
| D1 (three framings; in `DEC-T03-FRAMINGS-DESIGN`) | active, amended | D10 (`DEC-T03-NOSNIPPET`) and `DEC-T03-FR21-AMENDS-D1`: wording differs only where a note exists |
| D2, D3, D4, D6, D7 (in `DEC-T03-FRAMINGS-DESIGN`) | active | |
| D5 (one alternate per note type; in `DEC-T03-FRAMINGS-DESIGN`) | superseded | D11 (`DEC-T03-PERWORDING`): two alternates per original wording |
| `DEC-T03-NEUTRAL-WORDING` | superseded | `DEC-T03-PERWORDING` |
| `DEC-T03-NEUTRAL-REVERSED` | superseded | `DEC-T03-PERWORDING` |
| `DEC-T03-WORDING-REVIEW` (review of the ten-line set) | superseded | `DEC-T03-WORDING-REVIEW-2` |
| `DEC-T03-NOSNIPPET` (D10) | active | |
| `DEC-T03-PERWORDING` (D11) | active | |
| `DEC-T03-WORDING-REVIEW-2` (review of the 50 alternates) | active | |
| `DEC-T03-FR21-AMENDS-D1` (decision 12) | active | |

## Known limits

- Meaning is established by the owner's review, not by the tests. The fingerprint only proves that the alternates
  are the ones reviewed: any edit fails it, whatever the edit says.
- The other wording checks are keyword-based: listed key words and key phrases, negation words, instruction words
  and the predicates of `tests/t02_world/text_adjudicator.py`. They catch the loss of a listed word or phrase, a
  flipped negation, an added instruction and a lost rubric phrase. They do not catch a change to a word that is
  not listed.
- Two kinds of edit are caught by the fingerprint only: an added sentence, and an added clause, when it uses none
  of the watched words. Codex round 2's examples were an appended "A second reviewer confirmed this." and an
  inserted "although a concern was reported". No keyword check sees either, so a new wording of that kind would
  rely on a fresh owner review.
- 280 of the 615 bundles have no note, so their three framings differ in field order and name format only (D10).
- Of the 25 originals, the 17 that occur in the frozen world are exercised end to end; the alternates of the other
  8 are covered by the table checks alone.
- The original neutral notes reassure mildly, and their alternates keep that level. The effect of that cue on
  verdicts is measured by the planned neutral-note ablation.
- The orders are fixed. The framings test sensitivity to field order in these two arrangements only.
- Name formats are positional. Where the world writes a name in another word order (the name-variants family),
  the capitalised or front-placed token can be a given name, which looks odd.
- Latin script only, as in the world.

## Known awkward wordings

Codex round 2 found no changed fact in the 50 alternates but called these five awkward. They are left as reviewed,
because any edit changes the fingerprint and needs a fresh owner review.

| Row | Framing | What is awkward |
|---|---|---|
| neutral/4 | 2 | a sentence fragment ("Completed the annual refresh of the file: ...") |
| identity_link/3 | 3 | a trailing attribution (", a bank officer notes.") |
| relationship/2 | 3 | "as named in a family notice" |
| relationship/4 | 2 | "gives ... as the adult child" |
| continuing_risk/3 | 3 | a trailing "now out of office" |
