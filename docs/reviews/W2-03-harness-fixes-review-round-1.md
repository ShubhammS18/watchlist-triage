# W2-03 harness fixes — Codex review, round 1

Range: `fdb4fd6..HEAD` (`67b2f93`). Read-only repository review; no direct access to `data/world/hidden/`, network, or paid model calls.

## Findings

1. **SHOULD — `harness/run.py:375` (also `harness/run.py:419`): the preflight does not cover every input-derived manifest field.** It validates only the top-level keys manually placed in `from_inputs`. The input `config["threshold"]` is copied into `manifest.infra_invalid.threshold` after calls, outside that pass. `load_config` currently rejects the same invalid threshold values as the schema, so I found no present-day bad threshold that slips through; the stated construction guarantee is nevertheless incomplete and could regress if either rule changes. **Fix:** put the threshold in the preflight manifest skeleton, validate it against the shared `infra_invalid.threshold` rule before creating `run_dir`, and reuse that validated value in the final manifest. Add a test that asserts this path is validated through the schema.

2. **SHOULD — `tests/w2_03_harness_fixes/test_rescore.py:55` (used at line 100): the W2-02 spread allowance can hide a changed displayed figure.** `without_order` replaces each `spread.*.min` and `max` rate object with only `Fraction(numerator, denominator)`. It therefore ignores `not_applicable`, `decimal`, and `rounded`, and accepts an arbitrary fraction representation of the same value even if no tied run has that rate object. The exact per-run comparisons guard the underlying rates, but they do not guard what the set report displays for an extreme. The baseline has an additional byte-for-byte pooled/spread check in `tests/w2_01_acceptance/test_baseline.py:98`; this gap concerns the W2-02 set report. **Fix:** allow a min/max rate object to differ only when both exact objects are present among the tied extreme `per_run` entries; otherwise compare the full objects. Keep the run-order normalization.

## Outcome and evidence check

- **Mixed numeric/text IDs:** `harness/run.py:414` turns numeric IDs into text summary keys before sorted JSON hashing while item attempts retain their reported IDs. The documented `"number:123"` text/number key collision remains possible with a non-real provider; it does not prevent writing or hashing.
- **Start check:** the named invalid re-run causes, whitespace model name, non-finite temperature/timeout, and malformed world versions are refused before a call, run folder, or index entry in the new tests. The reported ID is provider output and cannot be checked at start; `model_interface/anthropic_api.py` converts it to text, and a non-finite fake ID is refused at scoring as DEC-W2-03-CHOICES specifies. Finding 1 limits the broader coverage claim.
- **Fixture acceptance:** `harness/score.py:704-715` marks acceptance mechanism-only if either table is a fixture; all four fixture/sourced combinations pass.
- **Issue 5:** `tests/t06_harness/test_reference.py:90-109` computes expected numeric counts from world alerts, twins, and truth, without calling scorer computation. It uses scorer constants only for category names. The old/new deliberate-break logs are consistent with the changed equality check and assertion: old passes, new catches 45 false divergences.
- **Re-score evidence:** `baseline/` committed figures are also checked byte-for-byte by W2-01; W2-02 run reports and acceptance are compared in full by the new test. Finding 2 limits the W2-02 set-spread claim. `SHA256SUMS` checks pass. The before/after logs (9 failed, 4 errors, 18 passed before; 31 passed after) match the diff and current gate result. The deliberate-break files contain only retained output from a manual copy, so their historical execution cannot be independently attested from these files alone; I found no inconsistency.
- **Scope:** `git diff fdb4fd6..HEAD -- model_interface tests/t06_harness` changes only `tests/t06_harness/test_reference.py`; model settings and all other T06 tests are unchanged.

## Gates run in this review

`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest <suite> -q -p no:cacheprovider --tb=short`

| Suite | Result |
| --- | --- |
| `tests/w2_03_harness_fixes` | 31 passed |
| `tests/t06_harness` | 340 passed, 6 skipped |
| `tests/w2_01_acceptance` | 68 passed |
| `tests/w2_02_agent` | 68 passed |

`git status --short` was empty after the gates.
