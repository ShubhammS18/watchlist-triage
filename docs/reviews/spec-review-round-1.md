Independent review by a fresh Codex session (read-only). Pasted verbatim by the owner.

# Verdict: BLOCK

The safety intent is strong, but the acceptance gates do not yet prove all four headline success criteria. Several controls are also underspecified or technically unachievable as written.

1. **Blocker — Success criteria are not fully traceable to acceptance gates**  
   **Requirements:** FR-15, FR-16, AC-3, AC-10, Open Questions (SPEC.md:29)  
   The brief requires identical verdicts across all three presentations and better time or cost than a manual baseline. FR-16 and AC-3 merely report overall consistency; only TRUE\_MATCH consistency must pass. NFR-6 models human time, but no manual-baseline protocol, comparison, or passing threshold exists. Deferring numeric targets until “after M2” leaves the present release without a binary value gate, and M2/M3 are not defined.  
   **Suggested fix:** Add acceptance thresholds requiring per-alert consistency across all three framings and a defined comparison against a reproducible manual baseline. If numeric efficiency targets must be deferred, make the baseline milestone and pre-release target-setting gate explicit.
2. **Major — Several brief items have no FR, NFR, or AC mapping**  
   **Requirements:** Users (SPEC.md:9), Non-goals (SPEC.md:50)  
   Unmapped or only narratively mentioned items are:
   - L1 versus L2 responsibility and routing of escalations.
   - Auditor access to reasoning and audit records.
   - Head of Compliance/MLRO buyer needs, even if only export/reporting needs are relevant.
   - Transaction-monitoring exclusion and research-level-work exclusion, which appear only as non-goals.
   - The requirement to beat a manual time/cost baseline.
   - The requirement for the same verdict across all three presentations, except for TRUE\_MATCH cases.

   **Suggested fix:** Add explicit trace links or requirements for the operational roles, exclusions, consistency gate, and baseline comparison. Buyer behavior need not become product functionality, but any claimed buyer/auditor need should map to a demonstrable output.
3. **Blocker — Strict four-eyes conflicts with the stated one-human constraint**  
   **Requirements:** FR-9 (SPEC.md:23), Constraint, line 45 (SPEC.md:45), AC-5 (SPEC.md:66)  
   STRICT\_FOUR\_EYES requires “a second, different reviewer,” while the constraints say “One human decision-maker.” If that means one operational reviewer, the default workflow cannot complete. If it means one project owner making development decisions, the wording is ambiguous.  
   **Suggested fix:** Distinguish project governance from product reviewer identities and state how two independent reviewer identities are provided in the synthetic demonstration.
4. **Major — “Contradictory evidence” has conflicting expected behavior**  
   **Requirements:** FR-2 (SPEC.md:16), FR-6 (SPEC.md:20), FR-15 (SPEC.md:29)  
   FR-2 requires the contradictory-evidence family to include CLEAR\_FALSE\_POSITIVE cases. FR-6 requires every case with contradictory evidence to be escalated. The harness then counts escalation of those clear false positives as over-escalation. A conforming implementation is therefore penalized for following FR-6.  
   **Suggested fix:** Define whether “contradictory evidence” always means insufficient evidence, or whether some contradictions have an objectively resolvable outcome. Align labels and over-escalation scoring with that rule.
5. **Major — Dataset proportions and per-family claims are internally ambiguous**  
   **Requirements:** FR-1 (SPEC.md:15), FR-2 (SPEC.md:16), NFR-7 (SPEC.md:40)  
   CLEAR\_FALSE\_POSITIVE is 510/600, or 85%, not 90–95%. The rate is 95% only if all 60 AMBIGUOUS\_BY\_DESIGN alerts are also counted as false positives, which is not stated. NFR-7 requires the README to say “about 6 true matches per family,” but FR-2 guarantees only four per family and permits multi-family cases, so “about 6” does not follow from the dataset constraints.  
   **Suggested fix:** Define the false-positive denominator and treatment of ambiguous cases. Specify exact or bounded family-membership counts that support the README statement.
6. **Blocker — The audit-log deletion guarantee cannot be met by a hash chain alone**  
   **Requirements:** FR-10 (SPEC.md:24), AC-6 (SPEC.md:67)  
   AC-6 requires detection when “any record” is deleted. Deleting the final record leaves the remaining chain internally valid. An attacker able to edit storage may also rewrite a record and recompute all later hashes. No trusted head, signed checkpoint, expected record count, key, or external anchor is specified.  
   **Suggested fix:** Define the threat model and add an independently protected chain head/checkpoint, signature or MAC strategy, canonical serialization, key ownership, and expected terminal state. Narrow claims to the tampering that the chosen mechanism can actually detect.
7. **Major — The ACs are not uniformly binary and automatable**  
   **Requirements:** AC-1–AC-10 (SPEC.md:62)

   | AC | Assessment |
   |---|---|
   | AC-1 | Conditional: “release candidate,” “closes,” run configuration, and whether all framings are included are undefined. |
   | AC-2 | Conditional: automatable only after “evidence item” and citation identity/format are defined. It proves existence, not evidentiary support. |
   | AC-3 | Partly binary for TRUE\_MATCH cases; “Overall verdict consistency … is reported” has no passing threshold. |
   | AC-4 | Conditional: “closed” and whether the rule applies across every framing and repeated run are unstated. |
   | AC-5 | Partly binary: the self-confirmation test is clear, but reviewer identity and distinctness are not trustworthy without an identity model. |
   | AC-6 | Not provable as written; suffix deletion is invisible to a standalone hash chain. |
   | AC-7 | Conditional: the exact generated file set, serialization rules, and allowed environment-dependent bytes are undefined. |
   | AC-8 | Not provable by tests: “no code path” is a universal absence claim. Ordinary automated tests prove only exercised paths. |
   | AC-9 | Not provable: “as a result of instructions” is causal, and FR-3 does not require injection snippets in any TRUE\_MATCH alert, so the test may pass vacuously. |
   | AC-10 | Field presence is binary, but units, aggregation, pricing source, latency boundary, and required run/framing breakdown are undefined. |

   **Suggested fix:** Give every AC an exact fixture, scope, oracle, expected output, and pass threshold. Replace universal or causal claims with enforceable capability and counterfactual tests.
8. **Major — Citation validity is too weak for the stated auditability goal**  
   **Requirements:** FR-5 (SPEC.md:19), FR-15 (SPEC.md:29), AC-2 (SPEC.md:63)  
   AC-2 only checks that a cited item exists. An agent can cite an irrelevant item, misstate its content, or give a reason unsupported by it and still pass. “Citation validity” in FR-15 is not defined.  
   **Suggested fix:** Define stable evidence IDs and separate metrics for citation existence, citation accuracy, relevance, and whether the reason is entailed by the cited evidence. Specify an automated or calibrated human-labelled oracle.
9. **Major — Prompt-injection acceptance is vacuous and does not prove NFR-5**  
   **Requirements:** FR-3 (SPEC.md:17), NFR-5 (SPEC.md:38), AC-9 (SPEC.md:70)  
   FR-3 only requires ten injection-bearing alerts, without label distribution. AC-9 only guards TRUE\_MATCH closure. A model could obey an injected instruction to escalate everything, alter its reason, omit evidence, or close an ambiguous case while still passing. The phrase “as a result of” cannot be inferred from a single output.  
   **Suggested fix:** Require injection cases across all labels and paired versions with and without the injected text. Assert invariant verdict, citations, and reasoning except for legitimate evidence changes.
10. **Major — Raw-data minimization is neither defined nor accepted**  
    **Requirements:** FR-11 (SPEC.md:25), FR-14 (SPEC.md:28), AC-8 (SPEC.md:69)  
    The “never holds raw personal data in a central store” prohibition has no acceptance check or defined storage boundary. The frozen world itself contains synthetic customer records, so it is also unclear whether this prohibition applies structurally to synthetic person-like data or only to future real data. Logs may leak personal fields through reasons or evidence citations even if inputs are represented by hashes.  
    **Suggested fix:** Define raw data, central store, transient processing, derived data, reason/log redaction, and retention boundaries. Add automated schema/data-flow checks covering the world store, model requests, reports, errors, and audit logs.
11. **Major — Missing fail-safe behavior for model and pipeline failures**  
    **Requirements:** FR-5–FR-8, FR-12, AC-1–AC-4  
    There is no required outcome for malformed structured output, missing citations, model refusal, timeout, provider error, truncated evidence, unknown label/schema version, or partial processing. In a safety-sensitive triage workflow, a builder must guess whether these block, retry, close, or escalate.  
    **Suggested fix:** Specify a fail-closed state machine: invalid or unavailable recommendations must never become CLOSE, must be visibly escalated or stopped, and must be audited. Define retry and idempotency behavior.
12. **Major — Four-eyes is a policy statement without an identity or authorization model**  
    **Requirements:** FR-8, FR-9, FR-13 (SPEC.md:22), AC-5 (SPEC.md:66)  
    “Different reviewer” could be satisfied by two arbitrary names supplied through the CLI. Roles, authentication, authorization, reviewer eligibility, separation of duty, concurrent approvals, policy changes, and approval revocation are undefined. The risk section acknowledges self-asserted Genesis identities but not product reviewer identities.  
    **Suggested fix:** Define the minimum identity model and an explicit alert lifecycle/state machine. Test forged identity, duplicate approval, concurrent approval, policy switching, and finalization races.
13. **Major — Evaluation leakage and reproducibility controls are incomplete**  
    **Requirements:** NFR-2, NFR-3 (SPEC.md:35), Risk/Open Question on holdout (SPEC.md:76)  
    The hidden labels are not required to be inaccessible to the agent. The whole frozen world may be used while designing prompts, and the holdout is undecided, making zero misses vulnerable to tuning or memorization. Reproducibility omits generation code/version, prompt hash or contents, decoding parameters, retry policy, provider snapshot, and per-presentation outputs. Three calls to a changing hosted model are not necessarily comparable runs.  
    **Suggested fix:** Require label isolation, a frozen evaluation manifest, exact configuration capture, and a held-out or otherwise access-controlled final safety set before claiming performance.
14. **Major — AML decision policy and evidence provenance are underspecified**  
    **Requirements:** FR-1–FR-7  
    A builder must invent what makes a synthetic sanctions or PEP case a TRUE\_MATCH, what evidence is sufficient to close, how former/current PEP status and dates are interpreted, and how conflicting identifiers are weighted. Evidence source, record version, watchlist version/as-of date, and provenance are absent. Without a written adjudication policy, labels and rationales cannot be independently audited.  
    **Suggested fix:** Add a synthetic-world adjudication rubric and provenance schema covering watchlist/customer record IDs, as-of dates, source/version, identifiers, and the minimum facts supporting each label. Keep the simple alert matcher out of this adjudication logic.
15. **Major — Important required behaviors have no acceptance coverage**  
    **Requirements:** FR-7, FR-8, FR-11–FR-14 (SPEC.md:21)  
    No AC verifies lack of web/external access, human override and rejection recording, stop-all-processing behavior, model replacement without code changes, active-policy logging, raw-data exclusion, or complete lifecycle logging. AC-8 covers only account action, regulator reporting, and missing reasons.  
    **Suggested fix:** Add focused acceptance checks for each externally observable “must” requirement, including capability-denial tests rather than only prompt assertions.
16. **Minor — Key terms require normative definitions**  
    **Requirements:** Throughout  
    Undefined terms include “evidence item,” “cites,” “valid citation,” “unclear,” “contradictory,” “close,” “final,” “outcome,” “framing,” “without changing meaning,” “release candidate,” “evaluation run,” “verdict consistency,” “world hash,” “model version,” “prompt version,” “raw personal data,” “central store,” “stop all processing,” “sample,” “cost per alert,” “latency per alert,” and milestones “M2/M3.”  
    **Suggested fix:** Add a short glossary and metric definitions. Define CLOSE separately as agent recommendation, human decision, and final disposition.
17. **Minor — Explicit compliance disclaimer is good, but public claims still need tighter boundaries**  
    **Requirements:** Problem, line 7 (SPEC.md:7), Constraint, line 47 (SPEC.md:47), NFR-7 (SPEC.md:40)  
    The spec expressly says no regulatory-compliance claim is made, which is appropriate. However, “industry figures suggest around 90–95%” is unsourced, “TRUE\_MATCH” may be read as a real legal/watchlist determination, and “built by analogy to model-risk and human-oversight expectations” can imply validation against unspecified standards.  
    **Suggested fix:** Require sources or qualify/remove the industry statistic in public material; define TRUE\_MATCH as a synthetic benchmark label; name any referenced expectations precisely or retain a prominent statement that no regulatory sufficiency, certification, or production fitness was assessed.
