Independent review by a fresh Codex session (read-only). Pasted verbatim by the owner.

# Verdict: BLOCK

Version 2 closes several Round 1 findings, but release acceptance can still be passed by an always-escalate system, the injection test does not enforce the stated security requirement, and the fresh-seed/repeated-run requirements conflict.

## Part 1 — Round 1 closure

| \# | Status | Requirements addressing it | Assessment |
|---:|---|---|---|
| 1 | PARTIALLY FIXED | `FR-20`, `FR-21`, `AC-4`, `AC-15`, `AC-16` | Consistency and modelled manual comparison are now reported and thresholded. However, `AC-16` permits arbitrary post-baseline targets and says “cost **or** time,” so it does not require useful improvement over manual review or the baseline. |
| 2 | PARTIALLY FIXED | `FR-10`, `FR-16`, `FR-18`, Non-goals, Users | L1 review, L2 routing, auditor export, and exclusions are represented. The buyer is named, but no buyer need or buyer-facing success criterion is specified. |
| 3 | FIXED | Constraints, `FR-12`, `NFR-7` | The owner is now distinguished from product reviewer identities, and simulated reviewers are disclosed. |
| 4 | FIXED | `FR-2`, `FR-7`, Glossary: Contradictory evidence | Contradictory evidence is never labelled `CLEAR_FALSE_POSITIVE` and always requires escalation. |
| 5 | PARTIALLY FIXED | `FR-1`, `FR-2`, `NFR-7`, Glossary: False-positive rate | The label counts total 600 and the five-family minimum was raised to six. But 510/600 is 85%, while 95% is obtained only by counting ambiguous escalations as false positives; “about 6 per family” is also not implied by an “at least 6” overlapping-family rule. |
| 6 | FIXED | `FR-13`, `AC-7`, Risks: audit-log tamper-evidence | The trusted checkpoint contains both terminal hash and record count, so suffix deletion is detectable under the explicitly bounded threat model. |
| 7 | PARTIALLY FIXED | `AC-1`–`AC-21` | Most criteria are substantially more concrete and automated. `AC-9`, `AC-10`, `AC-13`, `AC-14`, `AC-18`, and `AC-19` still either prove less than the corresponding requirement or contain claims an automated check cannot establish. |
| 8 | PARTIALLY FIXED | `FR-5`, `FR-19`, `AC-2`, `AC-3`, `AC-16` | Citations now use stable IDs and a hidden supporting-evidence key. “Citation accuracy” has no formula, denominator, or treatment of multiple valid evidence subsets, so the threshold is not reproducible. |
| 9 | PARTIALLY FIXED | `FR-3`, `NFR-5`, `AC-10` | Control twins are a meaningful improvement. Nevertheless, `AC-10` allows injection-induced divergence for all non-`TRUE_MATCH` cases and therefore does not establish `NFR-5`. |
| 10 | ACCEPTABLY NARROWED | `FR-3`, `FR-14`, `FR-17`, `NFR-4`, `AC-14`, Glossary: Raw personal data/Central store | The synthetic-only scope and storage definitions make this a prototype limitation rather than an uncontrolled real-data requirement. A new inconsistency between `FR-14` and `AC-14` remains, addressed below. |
| 11 | PARTIALLY FIXED | `FR-8`, `AC-11`, Glossary: System failure | The listed model and input failures fail closed. Failures of logging, queueing, checkpointing, persistence, configuration, and finalization are not covered despite the words “any system failure.” |
| 12 | ACCEPTABLY NARROWED | `FR-12`, Constraints, Non-goals, `NFR-7`, Risks | The roster and distinct-string rule form a minimal identity model, while lack of authentication is clearly disclosed and excluded from v1. |
| 13 | PARTIALLY FIXED | `FR-6`, `FR-22`, `NFR-2`, `NFR-3`, `AC-8`, `AC-19`, `AC-21` | Inference payload isolation and manifests are improved. The fresh-seed mechanism does not prevent developer label leakage or post-result tuning, and repository history cannot prove that a seed was never used locally. |
| 14 | FIXED | `FR-5`, `FR-6`, `FR-7`, `FR-14`, Glossary label definitions | The synthetic adjudication policy now covers label semantics, sufficient evidence, PEP dates/status, conflicting identifiers, supporting evidence, and record provenance. Metric-level ambiguity remains separate from the decision policy. |
| 15 | PARTIALLY FIXED | `AC-6`, `AC-9`–`AC-15`, `AC-18`, `AC-20`, `AC-21` | Most previously uncovered behaviors gained acceptance coverage. `QA_SAMPLING`, universal export correctness, framing meaning preservation, buyer outcomes, and several failure paths remain uncovered. |
| 16 | PARTIALLY FIXED | Glossary, `FR-19`, `FR-20`, `AC-16` | The glossary resolves many core state and label terms. Metric formulas, family membership rules, sampling, reason limits, and evaluation-versus-operational processing remain undefined. |
| 17 | PARTIALLY FIXED | `NFR-7`, `NFR-8`, Constraints, Open questions | Claim boundaries are much clearer and sourcing is required before public use. The specification itself still states the 90–95% figure without a citation while specifying a public repository, and no acceptance criterion enforces the public-text review. |

## Part 2 — Fresh findings in version 2

1. **Blocker — `AC-1`, `AC-3`–`AC-5`, `AC-16`, `FR-19`, `FR-21`**

   An always-`ESCALATE` implementation can achieve zero missed true matches and zero ambiguous closes. Because `AC-16` imposes no floor or direction on its later-selected thresholds, the owner could set over-escalation to 100%, citation accuracy or consistency arbitrarily low, and choose cost rather than time.

   **Suggested fix:** Require immutable, pre-upgrade targets that enforce useful discrimination—for example, a maximum clear-false-positive escalation rate—and require a stated improvement against the baseline/manual model where such a benefit is claimed.
2. **Blocker — `NFR-5`, `FR-3`, `AC-10`**

   `NFR-5` says injection text is never treated as instruction, but `AC-10` only prohibits divergence for `TRUE_MATCH` twins. Every injected clear false positive could change from `CLOSE` to `ESCALATE`, or change its citations, and the candidate would still pass after merely reporting the divergence.

   **Suggested fix:** Establish a binary bound for every twin pair, or define narrowly justified permitted differences. Separately test that injected text cannot control verdict, citations, output structure, or tool behavior.
3. **Major — `NFR-3`, `FR-22`, `AC-1`, `AC-19`**

   `NFR-3` requires results over at least three repeated runs, while the fresh-seed release evaluation must happen once and `AC-1` calls it a single run. No frozen-world-only exception is stated, so the requirements cannot unambiguously all be met.

   **Suggested fix:** State explicitly that the three-run rule applies to the frozen world and define the fresh-seed run as the sole exception.
4. **Major — `FR-1`, Problem, Glossary: False-positive rate, `FR-19`**

   The numeric totals add correctly: 30 + 60 + 510 = 600. But `CLEAR_FALSE_POSITIVE` is only 510/600 = 85%; the claimed 95% counts 60 unresolved alerts whose correct action is escalation as false positives. That does not match the ordinary AML meaning used by the industry claim and makes performance comparisons misleading.

   **Suggested fix:** Call 95% the “non-`TRUE_MATCH` share,” or set the synthetic label distribution so the actual clear-false-positive share matches the claimed false-positive rate.
5. **Minor — `FR-1`, `FR-2`, `FR-3`, `NFR-7`, Risks: Small samples**

   Five families × at least six true-match memberships gives at least 30 memberships, not necessarily six alerts per family: overlaps can increase some family counts while leaving some true matches outside every family. Also, `FR-3` does not explicitly say whether control twins are included in the 600-alert and label totals.

   **Suggested fix:** Define whether every alert has one or more family memberships, give exact or bounded per-family counts, replace “about 6” with the actual invariant, and state that twins are inside or outside the 600.
6. **Major — `FR-14`, `AC-14`, `NFR-7`**

   `FR-14` prohibits copies of customer-record fields anywhere in log records, but `AC-14` expressly permits them inside the logged free-text reason. These requirements are contradictory even in the synthetic world.

   **Suggested fix:** Choose one policy: prohibit field-value copies in reasons and validate them, or explicitly narrow `FR-14` to structured fields and disclose that reasons may contain copies.
7. **Major — `FR-8`, `FR-10`, `FR-11`, `FR-13`, `FR-19`, `FR-20`, `AC-13`, `AC-20`**

   The spec does not separate offline evaluation from the operational lifecycle. One frozen alert produces at least nine recommendations across three framings and three runs; taken literally, every recommendation requires human action, every escalation enters L2, and all outputs share one alert lifecycle despite the singular recommendation in `AC-13`.

   **Suggested fix:** Define an evaluation mode with isolated logs and no operational queue, final-disposition, or human-review side effects—or explicitly specify how repeated/framed recommendations map to lifecycle and queue records.
8. **Major — `FR-5`, `FR-19`, `FR-20`, `AC-3`, `AC-4`, `AC-16`**

   Release-gating metrics are undefined. Citation accuracy could mean precision, recall, exact-set match, or “at least one key ID”; verdict consistency could mean unanimous-three rate or pairwise agreement; family aggregation can double-count multi-family alerts. System-failure outputs further complicate citation denominators.

   **Suggested fix:** Define every metric mathematically, including numerator, denominator, aggregation across runs/framings, multi-family treatment, and handling of failures and multiple valid citations.
9. **Major — `FR-6`, `FR-22`, `AC-19`, `AC-21`, Risks: Synthetic-world bias**

   `AC-21` proves only that labels and keys are absent from the model payload. It does not prevent prompt or implementation authors from inspecting them. `AC-19` can show that a seed was absent from committed history, but cannot prove it was never generated locally, inspected, discarded, or followed by tuning.

   **Suggested fix:** Define a preregistered release protocol: freeze code/prompts/thresholds first, generate the seed through an auditable random commitment, isolate labels until scoring, record the attempt, and specify that a failed fresh-seed run cannot be replaced by another seed.
10. **Major — `FR-20`, `AC-4`, `AC-15`**

    Determinism does not establish that framing transformations preserve meaning. `AC-4` measures model agreement, and `AC-15` checks report presence; neither detects a transformation that changes a date, negation, transliteration, entity association, or injection semantics.

    **Suggested fix:** Add automated invariant/property tests for structured transformations and a frozen human-reviewed fixture set for wording transformations.
11. **Major — `AC-9`, `AC-13`, `AC-14`, `AC-18`, `AC-19`**

    Several stated “checks” cannot prove their full claims:
    - A static scan cannot prove the semantic absence of all account-action or regulatory-reporting capabilities.
    - Record presence cannot prove a decision was made by a human, particularly with simulated and unauthenticated identities.
    - A schema check cannot prove that arbitrary error strings contain no field values.
    - Testing an unspecified sample does not establish `FR-18` for any alert.
    - Git history cannot prove a seed was never used outside committed history.

    **Suggested fix:** Narrow each claim to what the check demonstrates, use explicit capability allowlists and typed error schemas, test all 600 exports, and describe fresh-seed integrity as a controlled procedure rather than a repository-history proof.
12. **Major — `FR-8`, `FR-10`, `FR-13`, `AC-11`**

    The fail-safe rule covers model/output faults but not critical pipeline faults. Audit-log write failure, L2 enqueue failure, checkpoint failure, crash during finalization, corrupted persistence, and invalid configuration are unspecified; some could leave a close finalized without its required audit evidence.

    **Suggested fix:** Define transactional ordering and safe states for each critical write, then add fault-injection tests showing that none can finalize `CLOSE`, lose an escalation, or produce duplicate dispositions.
13. **Major — Problem, Constraints: Public repository, `NFR-8`, Open questions**

    The specification contains the uncited 90–95% industry claim while requiring that it appear in public text only with a citation. Once this repository is public, the document violates its own requirement, and no acceptance criterion checks public claims.

    **Suggested fix:** Remove the statistic until sourced or cite it before publication, and add a release check covering all public-facing text.
