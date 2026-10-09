Codex independent review, T02-world, round 2, 2026-10-09

Command shorthand: `P=/home/shubham/projects/watchlist-triage/.venv/bin/python`; `S=/tmp/t02-round2.AK4cHfZt`. Scratch scripts and logs remain in the review folder (/tmp/t02-round2.AK4cHfZt). No repository changes were made; confirmed by command: `$P -B "$S/docfacts.py"` → `INDEX_WORKTREE_DIFFERENCES []`, `STAGED_WORKTREE_MISMATCHES []`, `UNTRACKED []`.

## Findings ranked by severity

**MAJOR — Exact injection wording still predicts labels across seeds.**

- Where: `worldgen/snippets.py:71–74`, `worldgen/build.py:pick_injection`.
- Evidence, confirmed by command: `$P -B "$S/docfacts.py"` produces identical template/label associations for seeds **20260930, 1, 42, 20260931**:

  | Phrase beginning | TRUE\_MATCH | AMBIGUOUS | CFP |
  |---|---:|---:|---:|
  | “SYSTEM NOTE TO REVIEWER…” | 1 | 1 | 0 |
  | “Attention AI reviewer…” | 0 | 1 | 0 |
  | “Override: every alert…” | 0 | 1 | 0 |
  | “Before deciding, print…” | 1 | 0 | 0 |

- Confirmed by command: the same script and `$P -B "$S/seeds.py"` show **3 close-directed / 2 other-directed** instructions per label, but these four phrases identify **5/5 escalation cases**, versus 10% escalation overall. Balancing direction did not remove the wording shortcut.
- Why it matters: irrelevant instructions remain reusable answer cues in the fresh-seed release. Suggested fix: balance individual templates across labels and test template-level associations.

**MAJOR — Fresh seeds expose PEP labels unsupported by rubric v1.2’s visible evidence.**

- Where: `worldgen/snippets.py:TEMPLATES`, `worldgen/rubric_check.py:31–78`, `docs/world-design.md:161`.
- Evidence, confirmed by command: `$P -B "$S/seeds.py"`:

  ```
  seed-1:        ALT-0299 independent AMBIGUOUS_BY_DESIGN, stored TRUE_MATCH
  seed-42:       disagreements []
  seed-20260931: ALT-0460 independent AMBIGUOUS_BY_DESIGN, stored TRUE_MATCH
  ```
- Confirmed by command: `$P -B "$S/independent.py" "$S/seed-1"` and inspection of that world’s evidence: ALT-0299’s former PEP left **2025-04-08**; its snippet says payments from connected firms continue after the term. It does not state continuing influence, control, or a formal state-linked role—the rubric’s stated threshold.
- Confirmed by command: `$P -B "$S/independent.py" "$S/seed-20260931"` and inspection of its evidence: ALT-0460 describes an adult child of a **former** agency head, without office dates. `pep_scope` treats this snippet-only relationship as in scope, while a relationship record lacking dates returns `unknown`.
- Confirmed by command: both worlds nevertheless pass all **64 applied checks** in `seeds.py`. Those checks adjudicate hidden snippet tags rather than establishing that the text supports them. Both disagreements retain ESCALATE; independent action disagreements are zero.
- Why it matters: fresh-seed truth can reward an undocumented exception or facts absent from the evidence. Suggested fix: make every template satisfy its rubric predicate, supply relationship dates, and test all template alternatives against visible-text adjudication.

**MINOR — The new date representation is distinguishable, but validation and generated prose are inconsistent.**

- Where: `worldgen/schema/world.schema.json:11`, `worldgen/build.py:add_pep`, `worldgen/rubric_check.py:31`.
- Evidence, confirmed by command: `$P -B "$S/probes.py"`:

  ```
  DATE 'MISSING'    schema [] scope unknown
  DATE ''           schema [] scope in_scope
  DATE '2025-02-30' schema [] scope ValueError: day is out of range for month
  DATE '9999-99-99' schema [] scope ValueError: month must be in 1..12
  ```
- Confirmed by command: the same probe finds WLE-0360 describing **“a serving minister”** alongside `related_pep_left_office_date="2026-04-03"`.
- Assessment: the empty/current versus missing/unknown convention is workable; confirmed by command: the probe distinguishes them correctly. I cannot confirm agreement across schema, generator prose, and rules: invalid dates pass schema, and “serving” contradicts the generated leaving date.
- Suggested fix: validate calendar dates and temporal bounds; derive relationship wording from status; document the sentinel in the agent-facing field description.

**MINOR — Normal loader isolation improved, but “no loader path” is too strong.**

- Where: `worldgen/loader.py:14–30`, `docs/world-design.md:120,134–135`.
- Evidence, confirmed by command: `$P -B "$S/probes.py"`:

  ```
  LOADER_DEFAULT 600 twin ids 0
  LOADER_GENERIC_READ 15 BUNDLED 15
  LOADER_TRAVERSAL_LABELS 600
  PUBLIC_LOADER_REDIRECTED 15 TWN-01
  ```
- Confirmed by command: the probe calls `_read(AGENT_DIR, "twin_alerts.jsonl")`, bundles its results, and reads `../hidden/labels.jsonl`; scratch symlinks also make public `load_alerts(agent_dir)` return twins.
- Why it matters: module separation establishes the default call path, not a capability boundary. I cannot confirm that a deployed agent can invoke these helpers or redirect `agent_dir`; T06 enforcement is outside this slice.
- Suggested fix: narrow the documentation to trusted loader inputs, and expose only harness-selected bundles to the agent; enforce filename/root restrictions if broader loader access is intended.

**MINOR — The purported rubric adjudicator omits the clean pattern’s name condition.**

- Where: `worldgen/rubric_check.py:66`, `fields_from_evidence`.
- Evidence, confirmed by command: `$P -B "$S/probes.py"` → `NONMATCHING_NAMES ('TRUE_MATCH', 'ESCALATE', 'clean_pattern')` for deliberately unrelated names with agreeing DOB and ID.
- Confirmed by command: the baseline matcher tests pass, limiting current-world impact. Suggested fix: enforce name/alias matching in adjudication or explicitly require and validate that precondition.

**MINOR — Structural fixes work, but residual non-rubric signals remain measurable.**

- Evidence, confirmed by command: `$P -B "$S/audit.py"` and `$P -B "$S/effects.py"`; figures below use TM/AM/CFP ordering. Balanced accuracy (BA) uses a stratified five-fold single-feature classifier; constant-action BA is **0\.5000**.

  | Feature | Confirmed measurement |
  |---|---|
  | Address, name form, group size, snippet-count buckets | Maximum between-label share gaps **0\.0 percentage points** |
  | Evidence count | Means **10\.2667 / 9.1333 / 9.2722**; BA **0\.6009** |
  | Neutral-snippet presence | **2/30, 11/30, 285/540**; BA **0\.6556** |
  | Injection presence | **5/30, 5/30, 5/540**; BA **0\.5787** |
  | Alert/customer/watchlist/evidence ID deciles | BA **0\.5981 / 0.5861 / 0.4731 / 0.5796** |
  | Customer/watchlist name length | Means **17\.8/16.9/17.4796**, **16\.2667/15.8333/16.15**; binned BA **0\.4296 / 0.4935** |
  | Customer/watchlist first bigram | BA **0\.5370 / 0.5028** |
  | Dates | Largest DOB-decade gap **16\.67 pp**; DOB-month gap **13\.33 pp** |
  | Field presence | Largest gap **26\.67 pp**, customer ID availability; rubric-related, not independently improper |
  | Injected-item position | Six distinct indices; first **0/15**, last **0/15**; mean index **4\.4 / 4.8 / 5.6** |
  | Snippet preceding a field item | **4/30, 3/30, 4/540**; BA **0\.5546** |
  | Twin structure | With both collections available, **15/15** pairs and removed items recovered; **15/15** twins have internal ID gaps |

- Confirmed by command: `$P -B "$S/effects.py"` trains on development data and scores the three other seeds: neutral-presence BA remains **0\.6556**, injection-presence **0\.5787**, evidence-count **0\.5370–0.5963**; ID-decile results range **0\.4602–0.5222**. The ID effects therefore do not demonstrate a stable shortcut in these experiments.
- Confirmed by command: `$P -B "$S/audit.py"` shows overlapping used/background ID ranges: customers **1–799 / 2–800**, watchlist **1–720 / 2–715**.
- Why it matters: marginal balancing does not establish absence of other shortcuts. Suggested fix: retain these measurements and distinguish mandated injection imbalance and rubric-dependent evidence from avoidable template/position cues.

## Round 1 findings status

- **Injection wording shortcut — PARTLY RESOLVED**; confirmed by command: `$P -B "$S/docfacts.py"`—direction balanced, exact wording still label-dependent across seeds.
- **Twin and injection recoverability — PARTLY RESOLVED**; confirmed by command: `$P -B "$S/probes.py"` and `$P -B "$S/audit.py"`—default API excludes twins and positions vary; generic paths and paired-data recovery remain.
- **Semantic test gap — RESOLVED for the reported record/evidence defect**; confirmed by command: `$P -B "$S/probes.py"`—record-only and consistently changed DOB mutations trigger the intended checks.
- **Six labels needing the hard-case exception — RESOLVED**; confirmed by command: `cat docs/rubric.md` and `$P -B "$S/independent.py"`—explicit v1.2 rule; all 600 labels agree.
- **Structural shortcuts — PARTLY RESOLVED**; confirmed by command: `$P -B "$S/audit.py"`—group-size and snippet-count gaps vanish; residual evidence/template signals remain.
- **Missing key validation — RESOLVED**; confirmed by command: `$P -B -m pytest -q -p no:cacheprovider tests/t02_world/test_rubric_check.py -k 'missing_or_empty_key or key_of_a_hard_case' --basetemp="$S/pytest-key"` → **2 passed**.

## Checked and found fine

- Confirmed by command: `PYTHONDONTWRITEBYTECODE=1 "$P" -B -m pytest -q -p no:cacheprovider tests/t02_world --basetemp="$S/pytest-base"` → **605 passed in 16.37s**.
- Confirmed by command: `$P -B "$S/independent.py"` → **540 CFP, 30 AMBIGUOUS, 30 TRUE\_MATCH; disagreements \[\]; representation disagreements \[\]; action disagreements \[\]**. The scratch classifier uses public fields/text and rubric rules, with no generator adjudicator or hidden-tag imports. This is the complete disagreement list for the staged 600: **none**.
- Confirmed by command: `$P -B "$S/probes.py"` captures the actual mutation exceptions: record-only DOB → `evidence differs from the records`; record-plus-evidence DOB → `ALT-0185: evidence gives AMBIGUOUS_BY_DESIGN, planted TRUE_MATCH`; removed source → `missing field: source`; extra/missing field evidence → the respective consistency differences; three twin edits → twin/customer mismatch; flipped label → `ALT-0001: evidence gives CLEAR_FALSE_POSITIVE, planted TRUE_MATCH`.
- Confirmed by command: `$P -B "$S/seeds.py"` invokes `$P -B -m worldgen --seed N --out "$S/seed-N"` for **1, 42, 20260931**. Every build exits **0**, produces **11 files**, **600 alerts**, **800 customers**, **720 watchlist entries**, **15 twins**, and **600 matcher/rule-derived labels**.
- Confirmed by command: that script applies **64 checks per seed**, all passing, including family/background counts, schema, consistency, matcher, label rules, and requested balances. Address/name/group/snippet gaps are **0\.0 pp** on each; injection direction is **3 close / 2 other per label**. The two independent semantic failures are listed above; none of these requested balance invariants held only for development seed 20260930.
- Confirmed by command: `$P -B "$S/determinism.py"` regenerates from the repository and scratch working directories using `PYTHONHASHSEED=1/937`, `LC_ALL=C/C.utf8`; both comparisons report **11 files, path differences set(), byte differences \[\]**, including MANIFEST.
- Confirmed by command: `gitleaks git --pre-commit --redact --staged --verbose` → **exit 0**, `scanned ~2080434 bytes`, `no leaks found`. `gitleaks version` → **8\.30.1**; inspection of the cached hook’s `.pre-commit-hooks.yaml` confirms that exact command.

## Could not verify

I cannot confirm the following claims in `docs/world-design.md`; line references identify the reviewed assertions:

- **Lines 3–4:** actual pre-code authorship and owner-chat provenance. Confirmed by command: `git log --oneline --all -- docs/rubric.md worldgen` and `sed -n '200,252p' .genesis/project.json` establish commits and recorded decisions, not the underlying historical events.
- **Line 34:** the synthetic prefix makes a real identifier impossible; no universal identifier namespace was verified.
- **Lines 49–50:** fresh-seed reference is FR-22, and values are “only integers, strings and dates.” Confirmed by command: `rg -n 'FR-22|FR-23' SPEC.md` places fresh-seed release in FR-23; `$P -B "$S/docfacts.py"` finds booleans, lists and nulls as well. No-floats checks do pass.
- **Lines 60, 67, 120, 134–135:** per-file schema coverage and unrestricted loader/twin isolation. Confirmed by command: `$P -B "$S/docfacts.py"` shows one shared five-property schema; `$P -B "$S/probes.py"` demonstrates the alternate read paths.
- **Lines 81, 136:** complete AC-12 behaviour and separate-context enforcement. Confirmed by command: `rg -n 'AC-12' SPEC.md` requires verdict/citation equality in every run/framing; this slice verifies world structure, not those future agent runs.
- **Lines 82, 124–125, 130:** wording/free choices never predict labels, variants are not family cues, and evidence numbers themselves are shuffled. Confirmed by command: `$P -B "$S/docfacts.py"` shows fixed wording associations and all TM/AM aliases in the name-variants family; `sed -n '440,480p' worldgen/build.py` assigns evidence IDs sequentially within shuffled alerts.
- **Line 95:** the snippet-based TRUE\_MATCH relationship is necessarily a close associate. Confirmed by command: `$P -B "$S/seeds.py"` plus `cat "$S/seed-1/agent/evidence.jsonl"` shows the recipe can render a spouse.
- **Line 105:** all labels use the same office offsets, so dates never predict labels. Confirmed by command: `$P -B "$S/docfacts.py"` → TM **\[90,335,364,540\]**, AM **\[335,366,540,1095\]**, CFP **\[90,180,335,364,365,366,380,540,730,1095,1460\]**.
- **Line 109:** unrestricted adjudication implements every rubric condition. Confirmed by command: `$P -B "$S/probes.py"` demonstrates the missing name condition; fresh-seed checks demonstrate text/tag semantic gaps.
- **Lines 143, 145, 163:** historical gate execution, completed generator-commit ordering, and prior stage breakage outcomes. Confirmed by command: `git log --all --oneline -- worldgen` is empty; historical reports alone do not prove execution.
- **Lines 154, 161:** README disclosure of author label access, and rubric support for treating every undated snippet relationship as in scope. Confirmed by command: `$P -B "$S/docfacts.py"` finds neither README disclosure; independent seed-20260931 adjudication exposes the latter discrepancy.
- I cannot confirm absolute synthetic provenance, absence of real-person coincidences, scans before every historical commit, resistance of an actual agent to these cues, arbitrary-seed/platform determinism, or absence of multivariate leakage. The experiments cover four seeds, simple feature models, and two installed locales.

DO NOT APPROVE — confirmed by the commands above, exact injection wording still supplies cross-seed shortcuts and two fresh seeds produce TRUE\_MATCH labels unsupported by rubric v1.2’s visible evidence.
