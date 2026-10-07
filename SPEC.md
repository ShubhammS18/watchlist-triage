# Product specification — watchlist-triage

> Status: draft. A coding agent must not implement product code until this specification is approved through Genesis.

## Problem

AML/compliance analysts spend a lot of time manually clearing sanctions and PEP alerts, even though industry figures suggest around 90–95% of sanctions alerts are false positives. In our synthetic world, that false-positive rate is something we deliberately set for testing, not a result measured from this system.

## Users

Primarily L1 AML/compliance analysts in fintechs and banks who review sanctions and PEP screening alerts and decide whether an alert looks like a false positive or needs to be escalated. The L2 senior analyst receives the escalations, while the Head of Compliance/MLRO is more likely to be the buyer, and auditors or examiners may later review the reasoning behind the decisions.

## Functional requirements

- FR-1: The system generates a frozen synthetic world from a fixed seed. It contains 600 sanctions/PEP name-match alerts, each with a hidden truth label: 30 TRUE_MATCH, 60 AMBIGUOUS_BY_DESIGN and 510 CLEAR_FALSE_POSITIVE.
- FR-2: The world covers five hard-case families: name variants, common-name collisions, thin identifiers, PEP status problems, and contradictory evidence. Each family appears in at least 6 TRUE_MATCH alerts, and an alert may count toward more than one family. Every family except contradictory evidence appears among TRUE_MATCH, AMBIGUOUS_BY_DESIGN and CLEAR_FALSE_POSITIVE alerts. No contradictory-evidence alert is labelled CLEAR_FALSE_POSITIVE.
- FR-3: The world contains only synthetic people, entities, customer records, a synthetic watchlist and short synthetic text snippets as evidence. At least 10 alerts include a snippet containing instructions aimed at the agent (an injection attempt), spread across all three labels. Each such alert also exists as a control twin that is identical except that the injected text is removed.
- FR-4: A simple deterministic name matcher generates the alerts from the customer records and the watchlist. Improving detection is out of scope.
- FR-5: A short synthetic-world adjudication rubric is written and committed before the world generator is first committed. It defines the three labels, what evidence is sufficient to close, how former and current PEP status and dates are read, how conflicting identifiers are weighted, and for every alert the supporting evidence key: the evidence item IDs that support the correct action. Every record in the world carries an ID, an as-of date, and a source and version.
- FR-6: Given one alert and its supplied evidence bundle only, the agent returns CLOSE or ESCALATE, a written reason, and the IDs of the evidence items it cites. A result with no reason or no cited ID is rejected. The agent never receives truth labels or the supporting evidence key.
- FR-7: If the supplied evidence is unclear or contradictory, the agent recommends ESCALATE.
- FR-8: Any system failure never produces CLOSE. A system failure becomes ESCALATE flagged SYSTEM_FAILURE and is logged. Retries are bounded, and processing the same alert twice never yields two final dispositions.
- FR-9: The agent uses only the evidence supplied inside the frozen world. It has no web search, no external tools and no network access.
- FR-10: Every ESCALATE creates a record in an L2 queue containing the alert ID, the reason and the cited evidence IDs. Deciding L2 outcomes is out of scope.
- FR-11: Every agent recommendation is a proposal that a human reviewer approves, rejects or overrides. Each outcome records who decided, when, and the written reason.
- FR-12: The review policy is a setting. STRICT_FOUR_EYES is the default: a CLOSE becomes final only after confirmation by a second reviewer with a different identity. QA_SAMPLING requires second review of a sample of closes only. Reviewers are identities from a roster file, supplied by the caller, and v1 has no authentication. Every policy change is logged.
- FR-13: Every alert's lifecycle is appended to an append-only log in a canonical serialization. Each record contains the hash of the previous record. After every evaluation run, a checkpoint holding the latest hash and the record count is committed to the public git history. A verification command given the log and a trusted checkpoint detects any edited, reordered or deleted record, including deletion of the last records.
- FR-14: Log records contain identifiers, hashes, enumerated values, numbers, timestamps, cited evidence IDs, human decisions, the active review policy, the model identifier and version, and the written reason. They contain no copies of customer-record fields.
- FR-15: Model access goes through one model-agnostic interface, so the model can be changed by configuration without changing other code.
- FR-16: Through the command line and API, the reviewer can see the evidence and reason behind a recommendation, approve or reject it, replace it with their own decision and a written reason, and stop all processing.
- FR-17: The system never takes action on an account, never reports to a regulator, never closes an alert without a written reason, and never holds raw personal data in a central store. These limits are enforced by the absence of any capability or interface for them, not only by prompts.
- FR-18: An export command produces, for any alert, a readable record of its lifecycle: reason, cited evidence IDs, human decisions, review policy and model version. The export is verified against the audit chain.
- FR-19: An evaluation harness scores any agent version on the frozen world and reports, as separate figures: missed TRUE_MATCH alerts, AMBIGUOUS_BY_DESIGN alerts closed, over-escalation rate on CLEAR_FALSE_POSITIVE alerts, citation existence, citation accuracy against the supporting evidence key, SYSTEM_FAILURE count, and cost and latency per alert. Figures are broken down by run, by framing and by family.
- FR-20: The harness presents every alert in three framings that differ in field order, name formatting and snippet wording, produced by deterministic transformations that do not change meaning. It reports verdict consistency across the framings per alert and overall.
- FR-21: The harness computes a modelled human review time for manual clearing and for agent-assisted review, from stated parameters shown next to every result. The comparison is a labelled assumption, not a measurement.
- FR-22: The generator accepts a seed. Release acceptance is also run once on a world generated from a new seed that was not used during design.

## Non-functional requirements

- NFR-1: Safety failures are never averaged away. Missed true matches are reported as their own count and never folded into an accuracy score.
- NFR-2: Regenerating the world from the seed produces byte-identical files, and an automated check fails on any drift.
- NFR-3: Every evaluation run records a manifest: world hash, generator version, rubric version, model identifier and provider-reported version string, prompt text and hash, decoding parameters, retry policy, review policy, and the per-framing outputs. Results are reported over at least 3 repeated runs with the spread shown. Hosted models can change underneath, so the manifest records what was reported, not a guarantee.
- NFR-4: Only synthetic data is ever committed. Secret scanning runs before every commit, and no keys are stored in the repository.
- NFR-5: Text inside evidence snippets is treated as untrusted data and never as instructions to the agent.
- NFR-6: Cost is computed from provider-reported token counts and a dated price table kept in the manifest. Latency is wall-clock time per alert including retries.
- NFR-7: The README states what was demonstrated and what was not, including: 6 true matches per family at minimum, a synthetic world that may not represent real alerts, no real analyst timings, reviewer identities that are self-asserted, and reasons that would need redaction in production.
- NFR-8: Public text defines TRUE_MATCH as a synthetic benchmark label and makes no regulatory-compliance claim. The 90–95% industry statistic appears in public text only with a cited source.

## Constraints

- Public repository, Apache-2.0 licence, synthetic data only.
- One human owner makes all project decisions. Claude Code builds only approved slices. A fresh Codex session from a different provider performs independent review. The product itself uses two reviewer identities from a roster, and the demonstration uses simulated reviewers.
- Time budget: about 13 days, with up to one extra week if needed.
- Built by analogy to model-risk and human-oversight expectations. No claim of regulatory compliance, sufficiency or production fitness is made.
- No live web search and no real customer data. OpenSanctions data is not used.

## Non-goals

- Improving sanctions or PEP detection itself.
- Transaction-monitoring alerts.
- Real customer data.
- Live web searching for news.
- Research-level work.
- Taking action on accounts, filing reports with regulators, or any production deployment or certification.
- Authentication, authorization or identity verification for reviewers.
- Deciding L2 outcomes or running an L2 workflow.
- A review screen in v1. The command line and API come first, and a minimal screen comes in a later milestone.

## Acceptance criteria

- AC-1: On the frozen world, the release candidate recommends CLOSE for zero TRUE_MATCH alerts, in each of 3 repeated runs and in every framing. The same holds in the single run on the fresh-seed world.
- AC-2: Every CLOSE cites at least one evidence ID that exists in that alert's evidence bundle, checked automatically for 100% of closes.
- AC-3: Citation accuracy against the supporting evidence key is reported, and the release candidate meets the threshold set in the decision record described in AC-16.
- AC-4: Every TRUE_MATCH alert is escalated in all three framings. Overall verdict consistency across framings is reported, and the release candidate meets the threshold set in the decision record described in AC-16.
- AC-5: Zero AMBIGUOUS_BY_DESIGN alerts are closed.
- AC-6: Under STRICT_FOUR_EYES, automated tests show that self-confirmation by the same identity is rejected, a duplicate approval does not finalize, two concurrent confirmations produce exactly one final disposition, and a policy change is logged.
- AC-7: The audit-log verification command passes on an untouched log with its checkpoint. Given the same checkpoint, it fails and names the first bad record in each automated test case: an edited record, a deleted middle record, a reordered pair, and deletion of the last record.
- AC-8: An automated check confirms the world regenerates byte-identically from the seed.
- AC-9: Automated tests show that the agent process cannot open a network connection, that the codebase contains no interface for account actions or regulator filings (checked by a static scan), and that closing without a written reason is rejected.
- AC-10: For every injection alert and its control twin, the verdict and cited evidence IDs are compared. Zero TRUE_MATCH pairs diverge, and divergences in other labels are reported.
- AC-11: Fault-injection tests for malformed output, missing citations, model refusal, timeout, provider error, truncated evidence and unknown schema version each produce ESCALATE with the SYSTEM_FAILURE flag, a log entry, and never CLOSE.
- AC-12: Automated tests show that a human override and a rejection are each recorded with a reason, that stop halts processing and refuses new work, and that a stub model selected only by configuration runs without code changes.
- AC-13: For every alert in an evaluation run, the log holds a complete lifecycle record with input hash, recommendation, cited IDs, model identifier and version, human decisions and active review policy, checked automatically for 100% of alerts.
- AC-14: An automated schema check shows that log records, reports and error output contain no customer-record field values outside the free-text reason, and the limit on reason text is stated in the README.
- AC-15: Every evaluation run produces a report containing all figures named in FR-19, FR-20 and FR-21, plus the cost and the human-time assumption.
- AC-16: A decision record sets numeric targets for cost or time per alert, for over-escalation on clear false positives, for overall verdict consistency, and for citation accuracy. It is committed after the baseline milestone and before the first upgrade milestone, and the release candidate meets those targets.
- AC-17: The rubric file exists and was committed before the generator's first commit, and an automated schema check confirms that every world record has an ID, an as-of date, and a source and version.
- AC-18: For a sample of alerts, the export command's output matches the audit chain, and an altered export fails verification.
- AC-19: The single run on the fresh-seed world happens once at release, and the repository history shows that seed was not used before that run.
- AC-20: Every ESCALATE in an evaluation run has a matching L2 queue record with the reason and cited IDs, checked automatically for 100% of escalations.
- AC-21: An automated test shows that the payload sent to the agent contains no truth-label field and no supporting-evidence-key field.

## Risks

- Small samples: about 6 true matches per family cannot support a per-family robustness claim. Mitigation: report per-family counts and state the limit in the README.
- Synthetic-world bias: we plant the cases, so the agent may fit our assumptions. Mitigation: the fresh-seed run tests overfitting to specific cases, but not our planting assumptions, and the README says so.
- Model nondeterminism and hosted-model drift. Mitigation: at least 3 repeated runs, the recorded manifest, and reported spread.
- Prompt injection through snippets. Mitigation: NFR-5, FR-3 and AC-10.
- Reasons may not be truly supported by the evidence they cite. Mitigation: citation accuracy against the key, plus a human spot-check sample, with the residual limit stated.
- Audit-log tamper-evidence is bounded. Mitigation: the checkpoint in public git history is the independent anchor, and an attacker who rewrites both the log and the checkpoint history is out of scope.
- Reviewer identities are self-asserted. Mitigation: stated as a limitation, with tests for duplicate and concurrent approvals.
- Overclaiming. Mitigation: NFR-7, NFR-8 and a review of all public text against the evidence.
- Four-eyes halves the time saved. Mitigation: measure it in the baseline milestone, and consider sampling as a measured upgrade.
- Genesis approvals are self-asserted names. Mitigation: independent Codex review, recorded as a decision record before approval.
- Schedule: building and verifying 600 labelled alerts is heavy. Mitigation: the extra week is allowed, and fixes to the review findings were kept minimal.

## Open questions

- The numeric targets named in AC-16 are set by a decision record after the baseline milestone and before the first upgrade milestone.
- The parameters of the human-minutes assumption are undecided.
- Which model providers are used for the first runs is undecided.
- A verifiable source for the 90–95% industry statistic must be found before any public use.
- How reason text would be redacted in a production setting is out of scope here and undecided.

## Glossary

- Alert: one name-match between a customer record and a watchlist entry, generated by the matcher.
- Evidence bundle: the set of evidence items supplied for one alert.
- Evidence item: one customer-record field, watchlist-entry field or text snippet in a bundle, with a stable ID.
- Supporting evidence key: for each alert, the evidence item IDs that the rubric says support the correct action. Hidden from the agent.
- Recommendation: the agent output of CLOSE or ESCALATE with a written reason and cited evidence IDs.
- Decision: a human approval, rejection or override of a recommendation.
- Final disposition: the state of an alert after the active review policy is satisfied.
- Close and escalate: CLOSE as a recommendation, a human decision or a final disposition are distinct states and are named explicitly wherever they matter.
- TRUE_MATCH: a synthetic benchmark label meaning the correct action is escalate because the alert is a planted real match. It is not a legal determination.
- AMBIGUOUS_BY_DESIGN: a synthetic benchmark label meaning the evidence is unclear by construction and the correct action is escalate.
- CLEAR_FALSE_POSITIVE: a synthetic benchmark label meaning the rubric resolves the alert as not a match and closing is correct.
- False-positive rate: in this specification, the share of alerts labelled CLEAR_FALSE_POSITIVE or AMBIGUOUS_BY_DESIGN, which is 95% of the world.
- Contradictory evidence: evidence items that support opposite actions where the rubric does not resolve the conflict.
- Framing: one of three deterministic presentations of the same alert that differ in field order, name formatting and snippet wording without changing meaning.
- Control twin: an alert identical to an injection alert except that the injected text is removed.
- Evaluation run: one pass over all alerts in all framings with one fixed configuration.
- Baseline milestone: the first milestone, in which a naive agent is scored on the frozen world.
- Release candidate: the final agent version submitted for acceptance against the acceptance criteria.
- System failure: malformed output, missing citations, model refusal, timeout, provider error, truncated evidence or an unknown schema version.
- Raw personal data: customer-record field values. Central store: any persistent store other than the world store and the audit log.
- Stop: halting all new processing so that no alert advances until the owner resumes it.
