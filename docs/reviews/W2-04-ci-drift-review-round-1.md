# W2-04-ci-drift — Codex review, round 1

Range: `d7ca77b..9254a24` on `w2-04-ci`. Repository inspected read-only; no network calls. The owner's push and pull-request run checks are accepted as supplied.

## Findings

1. **BLOCKER — `tests/w2_04_ci/test_workflow.py:28-57`** — The static check accepts unrecognised indented YAML, despite the stated fail-closed rule. In-memory edits adding `if: false` to the drift job or run step, or `continue-on-error: true` to the run step, all return `workflow_problems(...) == []`. Those valid workflow keys can skip the check or make drift green while every gate test still passes. **Fix:** validate the complete permitted line/indentation structure (or parse YAML and validate the resulting structure), reject every unknown key, and add negative tests for job/step `if` and `continue-on-error`.

2. **SHOULD — `tests/w2_04_ci/test_drift.py:136-147`** — The unsupported-Python test proves the exit message and code, but does not prove its title's claim that the guard runs before imports. Moving a `worldgen` import above the guard could leave this test passing. The current script does guard before `worldgen` at `tools/check_world_drift.py:61-68`; standard-library imports already happen at lines 12-17, so it does not stop before *anything* is imported. **Fix:** test that `worldgen` is not imported on the unsupported-version path, for example with an import sentinel in a temporary copy; phrase the test claim as “before worldgen is imported.”

## Verified

- `tools/check_world_drift.py:29-58` compares regenerated and committed files both ways, independently recomputes the world hash, and checks the committed manifest against the fixed frozen hash. A re-seeded world committed with its new manifest therefore fails even when every file matches regeneration.
- `tests/w2_04_ci/test_drift.py:103-133` makes real temporary copies, changes a world byte, and separately re-seeds and regenerates the copied world before invoking the copied script. Both deliberate breaks are genuine end-to-end failures.
- `.github/workflows/world-drift.yml:3-15` has the stated push and pull-request triggers, read-only contents permission, five-minute limit, pinned checkout, disabled credential persistence, and one script run step. The current workflow is locked down; finding 1 concerns the static gate's ability to keep it that way.
- `docs/w2-04-ci-drift.md:68-84` honestly states the two points the tests cannot establish: GitHub may skip or hold runs, and local gates see the working tree while CI sees the pushed commit.
- Gates: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/w2_04_ci -q -p no:cacheprovider` — **34 passed**; same command for `tests/t02_world` — **699 passed**. Working tree remained clean.
