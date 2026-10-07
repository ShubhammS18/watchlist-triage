# Product specification — watchlist-triage

> Status: draft. A coding agent must not implement product code until this specification is approved through Genesis.

## Problem

AML/compliance analysts spend a lot of time manually clearing sanctions and PEP alerts, even though industry figures suggest around 90–95% of sanctions alerts are false positives. In our synthetic world, that false-positive rate is something we deliberately set for testing, not a result measured from this system.

## Users

Primarily L1 AML/compliance analysts in fintechs and banks who review sanctions and PEP screening alerts and decide whether an alert looks like a false positive or needs to be escalated. The L2 senior analyst receives the escalations, while the Head of Compliance/MLRO is more likely to be the buyer, and auditors or examiners may later review the reasoning behind the decisions.

## Functional requirements

- FR-1: The system generates a frozen synthetic world from a fixed seed. It contains 600 sanctions/PEP name-match alerts, each with a hidden truth label: 30 TRUE_MATCH, 60 AMBIGUOUS_BY_DESIGN (the correct action is escalate) and 510 CLEAR_FALSE_POSITIVE.
- FR-2: The world covers five hard-case families: name variants, common-name collisions, thin identifiers, PEP status problems, and contradictory evidence. Every family appears among TRUE_MATCH, AMBIGUOUS_BY_DESIGN and CLEAR_FALSE_POSITIVE alerts, with at least 4 TRUE_MATCH alerts per family. A case may combine families.
- FR-3: The world contains only synthetic people, entities, customer records, a synthetic watchlist and short synthetic text snippets as evidence. At least 10 alerts include a snippet containing instructions aimed at the agent (an injection attempt).
- FR-4: A simple deterministic name matcher generates the alerts from the customer records and the watchlist. Improving detection is out of scope.
- FR-5: Given one alert and its supplied evidence only, the agent recommends CLOSE or ESCALATE and returns a written reason that cites the evidence items it relied on. A recommendation without a reason and at least one cited evidence item is rejected.
- FR-6: If the supplied evidence is unclear or contradictory, the agent recommends ESCALATE.
- FR-7: The agent uses only the evidence supplied inside the frozen world. It has no web search and no external data access.
- FR-8: Every agent recommendation is a proposal that a human reviewer approves, overrides or stops. Each outcome records who decided, when, and the reason.
- FR-9: The review policy is a setting. STRICT_FOUR_EYES is the default: a CLOSE becomes final only after confirmation by a second, different reviewer. QA_SAMPLING requires second review of a sample of closes only.
- FR-10: Every alert's lifecycle (input hash, recommendation, evidence cited, model identifier and version, human decisions, active review policy) is appended to an append-only log. Each record contains the hash of the previous record. A verification command detects any edited, removed or reordered record.
- FR-11: The audit log stores identifiers and hashes of inputs, not copies of customer personal data.
- FR-12: Model access goes through one model-agnostic interface, so the model can be changed by configuration without changing other code.
- FR-13: Through the command line and API, the reviewer can see the evidence and reason behind a recommendation, approve or reject it, replace it with their own decision and a written reason, and stop all processing.
- FR-14: The system never takes action on an account, never reports to a regulator, never closes an alert without a written reason, and never holds raw personal data in a central store. These limits are enforced in code, not only in prompts.
- FR-15: An evaluation harness scores any agent version on the frozen world and reports, as separate figures: missed TRUE_MATCH alerts, ambiguous alerts closed, over-escalation of clear false positives, citation validity, and cost and latency per alert.
- FR-16: The harness presents every alert in three framings that differ in field order, name formatting and snippet wording without changing meaning, and reports verdict consistency across them.

## Non-functional requirements

- NFR-1: Safety failures are never averaged away. Missed true matches are reported as their own count and never folded into an accuracy score.
- NFR-2: Regenerating the world from the seed produces byte-identical files, and an automated check fails on any drift.
- NFR-3: Every evaluation run records the world hash, model identifier and version, prompt version and review policy. Results are reported over at least 3 repeated runs, because model output is not fully deterministic.
- NFR-4: Only synthetic data is ever committed. Secret scanning runs before every commit, and no keys are stored in the repository.
- NFR-5: Text inside evidence snippets is treated as untrusted data and never as instructions to the agent.
- NFR-6: Cost and latency per alert are measured on every run. Human review time is modelled with a stated assumption whose parameters are shown next to every result.
- NFR-7: The README states what was demonstrated and what was not, including: about 6 true matches per family, a synthetic world that may not represent real alerts, and no real analyst timings.

## Constraints

- Public repository, Apache-2.0 licence, synthetic data only.
- One human decision-maker. Claude Code builds only approved slices. A fresh Codex session from a different provider performs independent review.
- Time budget: about 13 days, with up to one extra week if needed.
- Built by analogy to model-risk and human-oversight expectations. No claim of regulatory compliance is made.
- No live web search and no real customer data. OpenSanctions data is not used.

## Non-goals

- Improving sanctions or PEP detection itself.
- Transaction-monitoring alerts.
- Real customer data.
- Live web searching for news.
- Research-level work.
- Taking action on accounts, filing reports with regulators, or any production deployment or certification.
- A review screen in v1. The command line and API come first, and a minimal screen comes in a later milestone.

## Acceptance criteria

- AC-1: On the frozen world, the release candidate closes zero TRUE_MATCH alerts, in each of 3 repeated runs.
- AC-2: Every CLOSE recommendation cites at least one evidence item that exists in that alert's supplied evidence, checked automatically for 100% of closes.
- AC-3: Every TRUE_MATCH alert is escalated in all three framings. Overall verdict consistency across framings is reported.
- AC-4: Zero AMBIGUOUS_BY_DESIGN alerts are closed.
- AC-5: Under STRICT_FOUR_EYES, a CLOSE cannot become final without a second, different reviewer. An automated test shows self-confirmation by the same reviewer is rejected.
- AC-6: The audit-log verification command passes on an untouched log and fails, naming the first bad record, when any record is edited, deleted or reordered. This is tested automatically.
- AC-7: An automated check confirms the world regenerates byte-identically from the seed.
- AC-8: Automated tests show that no code path takes account action or files a regulator report, and that closing without a written reason is rejected.
- AC-9: For the planted injection snippets, zero TRUE_MATCH alerts are closed as a result of instructions inside a snippet.
- AC-10: Every evaluation run produces a report containing all figures named in FR-15 and FR-16, plus the cost and the human-time assumption from NFR-6.

## Risks

- Small samples: about 6 true matches per family cannot support a per-family robustness claim. Mitigation: report per-family counts and state the limit in the README.
- Synthetic-world bias: we plant the cases, so the agent may fit our assumptions. Mitigation: keep a held-out subset that is not used when designing upgrades (see Open questions).
- Model nondeterminism: results can vary between runs. Mitigation: at least 3 repeated runs and reported spread.
- Prompt injection through snippets. Mitigation: NFR-5, FR-3 and AC-9.
- Overclaiming. Mitigation: NFR-7 and a review of all public text against the evidence.
- Four-eyes halves the time saved. Mitigation: measure it in M2, and consider sampling as a measured upgrade.
- Genesis approvals are self-asserted names. Mitigation: independent Codex review, recorded as a decision record before approval.
- Schedule: building and verifying 600 labelled alerts is heavy. Mitigation: the extra week is allowed.

## Open questions

- Numeric targets for cost or time per alert and for the maximum over-escalation rate on clear false positives are set by a decision record after M2 and before M3 begins.
- Whether to hold out a subset of the world, and its size, is undecided.
- The parameters of the human-minutes assumption are undecided.
- Which model providers are used for the first runs is undecided.
