I re-checked the round 2 findings without editing the repo. The three fresh seeds were **7, 271, and 8675309**. All five reported defects now pass direct probes. Residual label cues remain, so I rank that finding first.

| Severity | Round 2 finding | Re-check |
|---|---|---|
| **Minor** | **6\. Residual cues — PARTLY FIXED.** | My classifier, using only `agent/` records and note text, agreed with hidden labels on **600/600 alerts on each seed**. Yet a neutral note appeared on 285 clear false positives out of 299, 298, and 298 alerts with such a note: **95\.3–95.6%**, above the 90% clear-false-positive base rate. Injection presence also predicts escalation: 10 of 15 injection alerts escalate versus 60 of 600 alerts overall. A rule that escalates on injection presence and closes otherwise gets **545/600**, versus **540/600** for always closing. Evidence count means differed by label; alias use was balanced at 2/30, 2/30, and 36/540. A snippet appearing before a field item occurred in **3/5/2**, **5/4/3**, and **2/4/5** alerts by TRUE\_MATCH/AMBIGUOUS/CLEAR\_FALSE\_POSITIVE across the three seeds. These are measured cues, not evidence of incorrect labels. The design note discloses the injection and neutral-note limits at lines 161–166 (docs/world-design.md:161). |
| — | **1\. Exact injection wording — FIXED.** | On **each** new seed, each of the five exact texts appeared **once per label**: every text’s TRUE\_MATCH/AMBIGUOUS/CLEAR\_FALSE\_POSITIVE count was `[1, 1, 1]`. The assignment is in worldgen/snippets.py:58 and worldgen/build.py:321. |
| — | **2\. Rubric predicates in notes — FIXED.** | Independent checks found **5/5** continuing-risk templates state post-office influence, control, or a formal state-linked role; **5/5** relationship templates state a serving, sitting, or current official; and **5/5** identity-link templates name both people and say they are the same person. See worldgen/snippets.py:19. The agent-only classifier’s **1,800/1,800** agreement across new seeds provides a generated-world check as well. |
| — | **3\. Dates and relationship prose — FIXED.** | Invalid calendar dates and leaving dates after `as_of_date` were rejected in both records and evidence items. Missing relationship date returned `unknown`; empty returned `in_scope`; 2025-09-30 was inside 12 months and 2025-09-29 beyond. All **4 relationship records per seed** used “serving” with an empty date or “former” with a date, with **zero mismatches**. See worldgen/validate.py:28, worldgen/rubric\_check.py:39, and worldgen/build.py:332. |
| — | **4\. Loader reachability — FIXED for the loader path.** | `_read` returned 600 normal alerts and raised `ValueError` for the twin filename, hidden-file traversal, a hidden folder, `..` in the folder, a symlinked file, and a symlinked folder. The checks are at worldgen/loader.py:15. **I cannot confirm this** prevents an agent with arbitrary filesystem access from reading those files directly; the design note (docs/world-design.md:135) expressly limits the claim to the loader path and assigns harness isolation to T06. |
| — | **5\. Name condition — FIXED.** | Unrelated names with agreeing DOB, ID, and nationality returned `AMBIGUOUS_BY_DESIGN`; adding a matching watchlist alias returned `TRUE_MATCH`. Both clean and hard-case branches require `names_agree` in worldgen/rubric\_check.py:72. |

For **7\. Design-note claims**, I checked eight factual assertions in docs/world-design.md:1 against code and generated data:

| Claim | Result |
|---|---|
| 600 alerts split 30/30/540, with the stated family counts (lines 9–13 (docs/world-design.md:9)) | **Verified** on all three seeds: six per TRUE\_MATCH and AMBIGUOUS family; 30 per hard clear-false-positive family and 420 plain. |
| Forty watchlist entries each serve three alerts, with 20% of each label in such groups (line 27 (docs/world-design.md:27)) | **Verified**: 40 groups; grouped alerts 6/6/108. |
| One fixed `as_of_date`, 2026-09-30 (line 48 (docs/world-design.md:48)) | **Verified** across every JSONL record inspected in the committed and three new worlds. |
| No floats in world records (line 50 (docs/world-design.md:50)) | **Verified**: zero floats in those JSONL records. |
| Each twin removes exactly one evidence item from its original (line 81 (docs/world-design.md:81)) | **Verified**: 15/15 in each world. |
| Every label uses every exact injected text once (line 82 (docs/world-design.md:82)) | **Verified** on each new seed. |
| Relationship prose follows the related PEP’s dated status (line 83 (docs/world-design.md:83)) | **Verified**: zero mismatches in 12 new-seed relationship records. |
| Record and evidence dates are calendar-validated and bounded by the as-of date (line 84 (docs/world-design.md:84)) | **Verified** by invalid-date and future-date probes. |

Commands and key output:

```
cat docs/reviews/t02-review-round-2.md
cat docs/rubric.md
cat docs/world-design.md
rg --files worldgen tests/t02_world

python -m worldgen --seed 7 --out /tmp/t02-round3.eY2Fs9j6/seed-7
# bash: python: command not found

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m worldgen --seed 7 --out /tmp/t02-round3.eY2Fs9j6/seed-7
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m worldgen --seed 271 --out /tmp/t02-round3.eY2Fs9j6/seed-271
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m worldgen --seed 8675309 --out /tmp/t02-round3.eY2Fs9j6/seed-8675309
# Each: 11 files; 600 alerts; 15 injections; 600 rule-derived labels

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B /tmp/t02-round3.eY2Fs9j6/audit.py
# Classifier: 600/600, 600/600, 600/600; each injection text vector [1,1,1]

PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B /tmp/t02-round3.eY2Fs9j6/probes.py
# Loader attacks: ValueError; invalid/future dates: rejected; relationship mismatches: 0; unrelated names: AMBIGUOUS_BY_DESIGN

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B /tmp/t02-round3.eY2Fs9j6/facts.py
# Each world: 40 shared groups; twins_one_removed 15/15; one as-of date; floats 0

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/t02_world/test_seed_sweep.py tests/t02_world/test_text_support.py tests/t02_world/test_loader.py tests/t02_world/test_validate.py tests/t02_world/test_rubric_check.py tests/t02_world/test_injection.py --basetemp=/tmp/t02-round3.eY2Fs9j6/pytest
# 216 passed in 12.57s

git status --short
# Same staged state before and after review; no repo changes
```

The independent classifier is in /tmp/t02-round3.eY2Fs9j6/audit.py. It completes predictions from `agent/` before loading hidden labels solely to score agreement. My **assessment** is that the remaining cues are a disclosed benchmark limitation, not a blocker for this T02 re-check.

APPROVE
