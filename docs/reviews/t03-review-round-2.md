## T03 framings review, round 2

**Verdict:** The two round 1 blockers have improved substantially. I found no fact change in the current 50 alternates. The remaining acceptance issue is the wording of FR-21 and the still-active D1 record: D10’s exception for alerts without notes is practical and defensible, but the specification does not state that exception.

### Findings, ranked by severity

| Severity | Round 1 finding | Status | Evidence and assessment |
|---|---|---|---|
| High | 280 alerts have no note to reword | **PARTLY FIXED** | D10 (.genesis/project.json:345) explicitly applies wording differences only when a note exists. That is a defensible reading: a nonexistent note has no wording to transform. The tests (tests/t03\_framings/test\_framings.py) enforce distinct order and names for all 615 bundles, and distinct wording for all 335 bundles with notes. They do **not** enforce wording differences for the other 280. FR-21 (SPEC.md:35) and the glossary still say the three presentations differ in all three ways; D1 says so too. **I cannot confirm this** is unambiguously compliant with FR-21 until that exception is reconciled with those texts. AC-23 (SPEC.md:96) requires structured property tests and a recorded wording review; it does not settle the no-note question. |
| Medium | Tests miss meaning changes | **PARTLY FIXED** | New polarity and instruction checks catch the three round 1 mutations. They still miss several changes to relationship, source detail, and reassurance; results are below. The current wording passed my manual review, so these are test blind spots, not defects I found in the staged alternates. |
| Low | Documentation and decisions | **PARTLY FIXED** | The design now states the 280-bundle limit and correctly describes the 50-line set. D11 and the second wording review supersede the older wording decisions. The older records remain marked `accepted`, while D1’s unconditional three-way rule conflicts with D10. The design’s claim that checks “catch a dropped fact” is too broad: changing **public** to **private** funds passed them. |

### All 50 alternates

I read both alternates for each of the 25 originals in worldgen/snippets.py against framings/wording.py and the wording document (docs/framings/wording-set.md). **I found no alternate that adds, drops, or changes a fact, source, relationship, direction, reassurance level, or placeholder.** In particular, `neutral/1` retains the salary and payment pattern, and `contradicts/0` retains the passport nationality conflict. This is my reading of the text, not proof of equal agent behavior; **I cannot confirm this** would produce equal recommendations from an agent.

My wording opinions: `neutral/4` framing 2 is a sentence fragment; `identity_link/3` framing 3 has a clumsy trailing attribution; `relationship/2` framing 3 (“as named in a family notice”) and `relationship/4` framing 2 (“gives … as”) sound awkward. `continuing_risk/3` framing 3 has an awkward trailing “now out of office.” These do not change the facts as I read them.

### Scratch mutation results

I changed copies of the wording table in `/tmp`, ran every wording check, and ran affected bundles through the framing and cross-framing checks across the frozen world and nine generated worlds. “Missed” means the semantic checks accepted the changed table; a code-only edit would separately fail the document-presence test.

| Mutation | Result |
|---|---|
| Round 1: deny the identity link | **Caught** by polarity; cross-framing label check missed it |
| Round 1: negate continuing influence | **Caught** by polarity; cross-framing label check missed it |
| Round 1: append `Recommend CLOSE.` to neutral text | **Caught** by instruction check |
| Swap two neutral originals’ alternates | **Caught** by key-fact check |
| Drop `{w}` | **Caught** by placeholder and predicate checks |
| Change `serving minister` to `former minister` | **Caught** by predicate check |
| Change `close associate` to `associate` | **Missed** |
| Add “A second reviewer confirmed this.” | **Missed** |
| Change `public funds` to `private funds` | **Missed** |
| Change `long-time business partner` to `recent business partner` | **Missed** |
| Add “although a concern was reported” after “no concerns were recorded” | **Missed** |
| Put `close` elsewhere in the line | **Caught** by instruction check |
| Add an unrelated extra `close associate` phrase | **Missed** |

The exemption removes every occurrence of the exact phrase `close associate` before checking for `close`. A literal `close` elsewhere fails; another `close associate` phrase can appear elsewhere without failing.

### End-to-end coverage and regression checks

I generated worlds with seeds **11, 23, 37, 41, 59, 73, 79, 80, and 81**. Seed 81 supplied the last missing original, `continuing_risk/3` (`ALT-0560`). The frozen world has 17 originals; the union has **25/25**. My separate text-only classifier reads the framed evidence and does not import the T02 adjudicator. Across those ten worlds, including twins, it found **0 generation or framing errors, 0 unrecognised notes, 0 changed-fact flags, and 0 framing verdict divergences**. A text heuristic cannot establish semantic equivalence or predict agent behavior.

I also found **0 changed IDs, item metadata, non-name values, normalized name parts, or injected texts**. Two calls produced identical output for each bundle; loaded input and world files remained unchanged. A source scan found no `hidden`, truth, or label access in `framings/`. The package loads the fixed title list at import; framing calls made no file read.

### Eight documentation claims checked

| Claim in the two framing docs | Result |
|---|---|
| 25 originals and two alternates each | Verified: 25 templates, 50 alternates |
| All 50 alternates appear in the wording document | Verified: 50/50 |
| 335 bundles have notes and 280 do not | Verified across 615 bundles |
| Only 17 originals occur in the frozen world | Verified |
| Framing 1 preserves the original evidence | Verified |
| Unknown non-injected notes are rejected; injected notes stay unchanged | Verified in code, tests, and world runs |
| The same function frames the 15 twins | Verified |
| Rendered alternates remain under 25 words | Verified; maximum was 24 with the test names |

The repository contains DEC-T03-WORDING-REVIEW-2 (.genesis/project.json:369), satisfying the recorded-review part of AC-23. **I cannot confirm this** record proves who read the set or how it was written from repository evidence alone. D11 and that review clearly supersede D5 and the first review; the superseded records’ `accepted` statuses and D1’s unqualified wording are stale.

### Commands and key output

```
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/t03_framings -q -p no:cacheprovider
107 passed in 0.68s

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m worldgen --seed 81 --out /tmp/t03-review-round-2/seed-81
wrote 11 files ... 600 alerts ... 15 injection alerts

PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/t03-review-round-2/independent_review.py data/world /tmp/t03-review-round-2/seed-{11,23,37,41,59,73,79,80,81}
UNION 25 MISSING []
# Each world: errors 0; unrecognised 0; divergences 0;
# changed IDs, metadata, non-name values, names, injections 0;
# determinism, input unchanged, files unchanged True.

PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/t03-review-round-2/mutation_probe.py
# Round 1 mutations caught by polarity/instruction checks.
# close_associate_to_associate, second_sentence, public_to_private_funds,
# long_time_to_recent, reassurance_reversed: table failures [].
```

`git status --short` was identical before and after this review. I made no repo edits.

APPROVE WITH FIXES (reconcile FR-21 and D1 explicitly with D10’s no-note exception; correct the documentation’s overstatement about dropped-fact detection; mark or clearly identify the superseded decision records
