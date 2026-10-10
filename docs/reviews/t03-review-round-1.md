## T03-framings review, round 1

**Two blocking findings:**

1. **FR-21 and D1 are not met for every alert.** Of 600 alerts and 15 twins, **280 alerts have no snippet**. Their three presentations differ in field order and name format, but cannot differ in snippet wording. The tests check three distinct orders for every bundle, while the snippet check has nothing to check on these 280. This conflicts with the “all three ways” decision in .genesis/project.json and the every-alert wording of FR-21 (SPEC.md:35).
2. **Some alternates change facts, despite preserving my classifier’s verdict.** In `ALT-0004`, “regular salary deposits and small domestic payments, nothing unusual this quarter” becomes “the customer’s details were checked” in framing 2 and “records are in order and no follow-up was requested” in framing 3. The original does not assert either check or follow-up outcome. In `ALT-0049`, a _passport nationality difference_ becomes a generic suggestion of a different individual; the rubric says nationality conflict alone does not decide identity. The loss of specifics is acknowledged in the design (docs/framings-design.md:79), but I assess these examples as changes to note meaning under the glossary definition (SPEC.md:156).

### Checks requested

| Check | Result | Evidence and limit |
|---|---|---|
| 1\. Spec and decisions | **PROBLEM** | The order, positional name rules, fixed ten-line table, injected-text handling, and D2–D7 routing match the recorded decisions. D1’s three-way change fails on 280 alerts. The later neutral decision is reflected in the table; equal meaning is disputed below. |
| 2\. Facts and names | **FIXED-OK** | Across all 615 frozen bundles and three framings, my check found **0** changed IDs, non-name values, or item metadata, and **0** unequal name parts under the repo’s normalization. Titles with and without dots, accented capitals, three-token and hyphenated names worked; one-token names and `Dr X` raised `ValueError`, as designed; `Dreß` was refused for uppercase framing 2. |
| 3\. Independent text classifier | **FIXED-OK** | My classifier uses framed evidence text and fields, with no T02 adjudicator or hidden label input. It gave **0 framing divergences** and **0 generation/framing errors** on the frozen world and seeds 7, 91, and 20261009. A separate comparison against hidden labels found **0 mismatches** among the 600 alerts in each world. This establishes consistency on those worlds, not general semantic equivalence. |
| 4\. Wording | **PROBLEM** | All ten alternates retain the broad rubric proposition for their note type, including “same person,” post-office risk, and a serving or sitting official. They also collapse distinct source and evidence facts. The neutral alternatives both reassure, but framing 3’s “records are in order” can encourage **CLOSE** more than originals that only report a call or transaction pattern. Generic contradiction notes may also encourage **CLOSE**; identity-link, continuing-risk and relationship wording may encourage **ESCALATE**. **I cannot confirm this** claimed equality of reassurance without agent-behaviour evidence. |
| 5\. Leaks | **FIXED-OK** | framings/ (framings/\_\_init\_\_.py:27) branches on framing, evidence kind/field and visible snippet text; it does not read alert position, hidden data, labels, truth or twins. Twins are loaded by the test route. Each of the five injected texts occurs once per label and remains byte-identical in every framing. Snippet-count groups retain the world’s 90:5:5 label ratio; I found no framing-introduced label cue. |
| 6\. Determinism and purity | **FIXED-OK** | Two full passes had identical output SHA-256; the loaded input hash was identical before and after. No clock, randomness, environment lookup or file write appears in `framings/`. Its import reads the fixed title list through `load_titles()`; framing calls themselves do not read a file. |
| 7\. Tests | **PROBLEM** | The 73 staged tests pass. Their mutations meaningfully catch altered dates/IDs, missing or reordered items, changed names, injected text, and removal of selected key phrases. They miss semantic negation and directives that retain those phrases; they also miss the 280 bundles with no wording change. Details below. |
| 8\. Docs | **PROBLEM** | Seven of eight sampled factual claims below match code/data; the every-alert three-way wording claim does not. The sentence saying the evaluation _shows an agent_ every alert in all three framings is premature for this staged T03 implementation. A review record exists, but **I cannot confirm this** claim that a human read the set or that no model wrote it from repository evidence alone. |

### Commands and key output

```
.venv/bin/python -m pytest tests/t03_framings -q -p no:cacheprovider
73 passed in 1.01s

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m worldgen --seed 7 --out /tmp/t03-seed-7
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m worldgen --seed 91 --out /tmp/t03-seed-91
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m worldgen --seed 20261009 --out /tmp/t03-seed-20261009
# Each: wrote 11 files; 600 alerts; 15 injection alerts
```

I ran my scratch classifier and invariant check (/tmp/t03\_independent\_review.py) with:

```
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/t03_independent_review.py data/world /tmp/t03-seed-7 /tmp/t03-seed-91 /tmp/t03-seed-20261009
# Each world: alerts 600 twins 15; divergences 0; errors 0; reworded 880
# Each world: 545 CLEAR_FALSE_POSITIVE, 35 AMBIGUOUS_BY_DESIGN, 35 TRUE_MATCH including twins
```

An independent count of snippet-bearing bundles gave:

```
base snippet count Counter({0: 280, 1: 200, 2: 120})
twins snippet count Counter({1: 15})
all-three-distinct order/name/snippets 335 / 615
```

Two-pass hashes were identical: framed output `c5393666…6fdd5338` both times; loaded input `e261bc78…d85e0c2febd3` before and after.

For test sensitivity, my scratch mutation probe (/tmp/t03\_mutation\_probe.py) changed copies of the wording table. It obtained:

```
identity_denial: wording+neutral checks PASS; T02 cross-framing failures 0; affected alerts 8
risk_negation:   wording+neutral checks PASS; T02 cross-framing failures 0; affected alerts 1
neutral_directive ("Recommend CLOSE."): checks PASS; cross-framing failures 0; affected alerts 298
```

Those are checker blind spots, not claims that the staged wording contains those mutations. The document-presence test would flag a code-only wording edit; a corresponding document edit would not make these semantic checks stronger.

### Eight documentation claims checked

| Claim from the two framing docs | Check |
|---|---|
| Five note types and 25 originals | **Verified:** 5 keys, 25 templates. |
| Ten alternates, one per type per framing 2/3 | **Verified:** 10 lines; all appear in the wording document. |
| Framing 1 keeps original evidence | **Verified:** equality over all 615 bundles. |
| Framing 2 and 3 use the documented block orders | **Verified:** three distinct ID orders for all 615. |
| The documented title/name examples follow positional formatting | **Verified:** including `Dr. PLUKIL, Drigutek` and `Dr Plukil Drigutek`. |
| Five injected texts stay unchanged | **Verified:** all five occur once in each label group and remain byte-identical. |
| The same function handles 15 twins | **Verified:** 15 loaded through `worldgen.harness_twins`, with no framing exception. |
| Every alert has three framings differing in note wording | **Not verified:** 280 alerts have no note to reword. |

The repository’s tracked status remained the staged T03 set; I did not stage, commit or push.

DO NOT APPROVE (280 alerts cannot satisfy the recorded three-way framing requirement; alternate wording changes specific evidence facts under FR-21’s meaning-preservation requirement)
