# World design for T02-world

Status: draft for owner approval. Written before any generator code.
Decisions come from the owner's decision record DEC-T02-WORLD-DESIGN. Anything marked "(proposal)" is a suggestion, not a decision.
This note follows `docs/rubric.md` (version 1.1, changed by DEC-RUBRIC-PEP-PRECEDENCE) and `SPEC.md` (FR-1 to FR-4, NFR-2, NFR-4, AC-10, AC-17).

## Counts

| Label | Count | Breakdown |
|---|---|---|
| TRUE_MATCH | 30 | 6 per primary family, 5 families |
| AMBIGUOUS_BY_DESIGN | 30 | 6 per family, 5 families |
| CLEAR_FALSE_POSITIVE | 540 | 120 hard cases (30 each in name variants, common-name collisions, thin identifiers, PEP status problems), no contradictory-evidence cases, 420 plain alerts with no hard family |

- Injection alerts: 15, five per label. The five TRUE_MATCH ones cover one per family. Each has a control twin; the twins sit outside the 600.
- Injection spread for the other labels (proposal): AMBIGUOUS one per family; CLEAR_FALSE_POSITIVE one in each of the four hard families plus one plain.
- Secondary families (proposal): 2 TRUE_MATCH alerts per primary family also carry one secondary family. They are reported separately and never added to totals.
- Background records (proposal): about 200 customers and 200 watchlist entries that match nothing, so the matcher has non-matches to reject. Exact totals are set in the config and asserted by tests.
- People only (proposal): version 1 has no company entities.

## Names

- Fictional name-part lists are kept in the repo and combined by the generator: a given-name list, a family-name list and a title list (proposal: about 150 parts each for given and family names).
- Latin script only. Variant forms: spelling, transliteration-style forms, word order, titles, diacritics and aliases.
- Name parts are at least three edits apart from each other (proposal), so the one-character tolerance can only fire on a planted variant. A test checks this.
- A small "common" subset of each list drives the common-name collision family. Collision alerts may share one watchlist entry (proposal).
- A README note in `data/world/` (proposal) says any resemblance to real people is coincidental.

## Identifiers

- Dates of birth are valid calendar dates (proposal: 1950 to 2000).
- Nationality uses real country adjectives, drawn independently of the name (proposal).
- ID numbers have a fixed prefix and no checksum (proposal: `SYN-` plus nine digits), so they can never be a real ID.
- Decisive identifiers: date of birth and ID number. Supporting identifier: nationality. Soft identifier: address (proposal: generated from fictional street and town lists).

## Matcher

- Names only. Lowercase, strip titles and diacritics, split into parts (proposal: on spaces and hyphens), and compare as sets of parts. Two names match when their parts pair one-to-one, each pair within one character difference (proposal: edit distance of at most 1, same number of parts).
- Variants must be within one edit per name part. Two pairs that qualify (illustrative, not list entries): Maralis / Marelis (one letter substituted) and Teodrin / Teodrinn (one letter added). Mohammed / Muhammad would not qualify, because it differs by two letters.
- Watchlist aliases are compared too (proposal).
- Labels are planted first. The build fails if the matcher output is not exactly the planted 600 alerts.
- Consequence: a variant only becomes an alert if the matcher can see it. Variants beyond one edit per part, other than word order, titles, diacritics and aliases, cannot be used. This is a known limit; improving detection is out of scope (FR-4).

## Randomness and determinism

- A SHA-256 counter stream per record type. Python's `random` module is not used. Proposal: block `n` of stream `name` is `sha256(seed|name|n)`, read as 64-bit integers, with rejection sampling for ranges and a Fisher-Yates shuffle.
- One fixed as-of date, 2026-09-30, and no wall-clock time anywhere.
- One fixed development seed in a config file (proposal: `worldgen/config.json`, which also holds the as-of date, ID prefix and counts). The generator also accepts a seed on the command line (proposal), for the later fresh-seed run (FR-22).
- No floats in the data. Only integers, strings and dates.

## Files (proposal for layout and names)

JSONL, UTF-8, LF line endings, sorted keys, compact separators, NFC-normalised text, one trailing newline. Every record in every file carries `id`, `as_of_date`, `source` and `version`.

```
worldgen/                     generator code (Python 3.12, standard library only)
  config.json                 seed, as-of date, ID prefix, counts
  names/                      given.txt  family.txt  titles.txt  common_*.txt
  schema/world.schema.json    required fields and types per file (AC-17 check)
data/world/                   the committed world
  README.md                   resemblance note, field summary
  MANIFEST.json               generator and rubric versions, SHA-256 per file, world hash
  agent/                      everything an agent may see
    customers.jsonl  watchlist.jsonl  evidence.jsonl
    alerts.jsonl              the 600
    twin_alerts.jsonl         the 15 control twins, same shape as alerts
  hidden/                     never read by the agent loader
    labels.jsonl              label, correct action, primary and secondary families, hard-case flag, recipe id
    evidence_key.jsonl        supporting evidence item IDs per alert
    snippet_tags.jsonl        what each snippet does (neutral, identity link, continuing risk, relationship, contradicts, injection)
    twin_links.jsonl          which alert each twin copies and which item was removed
tests/t02_world/
```

- IDs are sequential and deterministic, for example `ALT-0001`, `TWN-01`, `CUS-0001`, `WLE-0001`, `EVD-0001` (proposal).
- Evidence items (proposal): one item per customer or watchlist field present, plus snippets, each with a stable ID. A missing field means "unavailable".
- A twin reuses its original's customer, watchlist entry and evidence item IDs, minus the injected snippet. The injected snippet holds only the instruction text, so removing the text removes the item. This matches AC-12 ("identical except for the injected snippet's own ID").

## Recipes

A = agrees, C = conflicts, U = unavailable. "Link" and "risk" are snippet tags stored in `hidden/`.

| Pattern | Generated as |
|---|---|
| Clean TRUE_MATCH | Name matches. Date of birth A and ID number A (or one of them A with nationality A). No decisive C. Nationality may be A, C or U. |
| TRUE_MATCH, name variants | Clean identity, with a variant name form the matcher can see. |
| TRUE_MATCH, common names | Clean identity on a common name (date of birth A, ID number A). |
| TRUE_MATCH, thin identifiers | One decisive identifier A, the others U, plus a "link" snippet. The key lists the identifier and the snippet. |
| TRUE_MATCH, PEP status | Clean identity plus one of: current PEP; former PEP inside 12 months; former PEP beyond 12 months with a "risk" snippet; relative via the relationship field; close associate via a snippet. |
| TRUE_MATCH, contradictory | Date of birth A and ID number A, with a contradicting item (nationality C or a snippet tagged "contradicts"). |
| AMBIGUOUS, name variants | Variant name; exactly one strong identifier available and agreeing. |
| AMBIGUOUS, common names | Common name; no decisive identifier available; nationality A or C. |
| AMBIGUOUS, thin identifiers | Only one strong identifier available; no "link" snippet. |
| AMBIGUOUS, PEP status | Former PEP beyond 12 months with clean identity and no "risk" snippet (rubric v1.1 settles this: DEC-RUBRIC-PEP-PRECEDENCE); relationship from a snippet with a single agreeing identifier; missing office end date. |
| AMBIGUOUS, contradictory | One decisive identifier A and the other C. |
| CLEAR_FALSE_POSITIVE, hard | A decisive C, no decisive A, no "link" snippet, in four forms: variant name; common name; thin identifiers (the only decisive identifier present conflicts); a PEP watchlist entry. |
| CLEAR_FALSE_POSITIVE, plain | Ordinary name, same spelling, not common; decisive C (date of birth, ID number or both); no hard family. |

PEP dates (proposal): "12 months" is computed by calendar months, not by counting days. A person is inside 12 months if the leaving-office date is on or after the same calendar date twelve months before the as-of date (2025-09-30 for 2026-09-30). The anniversary day counts as inside 12 months; one day earlier is beyond it. Dates are produced from calendar months. The offset list is kept as the targets for how far before 2026-09-30 the leaving date falls: 0 (current), 90, 180, 335, 364, 365, 366, 380, 540, 730, 1095, 1460 days, each converted to a calendar date. The same offsets are used in all three labels, so a date alone never predicts the label.

## Checks

- A function in the generator recomputes each alert's label from its agent-visible items and the snippet tags, using the rubric rules (each rule cites its rubric section). The build and a test fail if any alert disagrees with its planted label or correct action. Hard-case TRUE_MATCH and contradictory TRUE_MATCH alerts are checked by recipe: required items present in the key, no decisive conflict. Under rubric v1.1, a planted former PEP more than 12 months out of office with confirmed identity and no continuing-risk snippet is labelled AMBIGUOUS_BY_DESIGN, so the label checker must apply the PEP-section exception and must not treat that label as a planting error.
- `tests/t02_world` asserts:
  - Counts: 600 alerts; 30/30/540; 6 TRUE_MATCH and 6 AMBIGUOUS per family; 30 CLEAR_FALSE_POSITIVE in each hard family; 420 plain; none contradictory.
  - Injection: 15 alerts, 5 per label, one TRUE_MATCH per family.
  - Twins: 15, identical to the original except the injected item; same label and key.
  - Determinism: regenerating into a temp folder gives the same bytes and the MANIFEST hash; two runs agree.
  - Schema: `id`, `as_of_date`, `source`, `version` on every record; unique IDs; references resolve.
  - The matcher output equals the planted 600.
  - Label consistency with the rubric for all 600.
  - Synthetic-only: ID prefix, valid dates, name parts only from the lists, name parts three edits apart.
  - No loader path exposes labels: the agent loader reads only `agent/`; returned records contain none of the hidden field names; a static check confirms it never opens `hidden/`.

## Process

- The drift check writes to a temp folder outside the repo, so the gate never changes repository files.
- New files are staged before the gitleaks gate so it scans them.
- The 50-alert operational demo set is not part of T02.
- The generator code is committed after `docs/rubric.md` (AC-17); the rubric commit is `95dbd4a`.

## Known limits

- Latin script only. No Arabic, Cyrillic, Chinese or other scripts.
- Small injection counts: 15 alerts, 5 per label. Results are reported as counts, not percentages.
- Synthetic names cannot be guaranteed free of coincidental overlap with real people.
- People only; the matcher sees only the variants listed under Matcher.
- 12 of the 30 TRUE_MATCH alerts are checked by recipe, not re-derived from the rubric.
- The snippet tags in `hidden/` are the generator's own bookkeeping; the agent must infer the same things from snippet text.
- The author can see the labels while building the generator (as NFR-7 requires the README to state).
- All files, including `hidden/`, live in one public repo. Separation is by code path, not by access control.
