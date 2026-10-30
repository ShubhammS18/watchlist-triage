# Harness fixes (W2-03)

Status: Approved, 30 Oct 2026 (review round 2; `DEC-W2-03-REVIEW`, reports in `docs/reviews/`). The task fixes T06
known issues 2 to 5 (`docs/harness-design.md:708-724`). Choices: `DEC-W2-03-CHOICES`. No model was called.

## Supersedes

`docs/harness-design.md` stays as it was when T06 closed (`DEC-T07-DOCS-LEFT`). These lines in it are out of date.

| Line | What it says | Now |
|---|---|---|
| `docs/harness-design.md:708-711` | mixed numeric and text model IDs break the manifest | the manifest's `model.reported` keys a number as `"number:<value>"`; each attempt keeps its ID as reported |
| `docs/harness-design.md:712-716` | the run step accepts inputs the shared schema refuses | it checks the part of the manifest its inputs decide against the schema before any call; a non-finite reported model ID is the exception, below |
| `docs/harness-design.md:717-720` | acceptance `mechanism_only` follows the modelled-time file only | it is true when either table is a fixture |
| `docs/harness-design.md:721-724` | one reference-agent assertion compares the report with itself | it compares the whole `overall` block with values worked out from the world files |

## What changed

1. **Model IDs in the manifest summary** (`harness/run.py`). A provider that reported `123` on one call and
   `"fake-1"` on another made `json.dumps(..., sort_keys=True)` raise `TypeError` at the end of the run, after
   every call: no manifest, and an index entry left at "started". Now a text ID is its own key and a number is
   keyed as `"number:123"`, so the keys are always text. Each attempt in `items.jsonl` keeps its ID exactly as
   reported (`DEC-T06-MANIFEST-9`). The committed manifests report text IDs only, so nothing about them changes.
2. **The start check** (`harness/run.py`). The manifest's input-derived part is built once, before any call:
   - what it includes: run and run-set IDs and inputs, the re-run cause, the agent, the world's hash and versions,
     the model, prompt, decoding and retry settings, both tables, git, the hashes and the worker settings, and
     the infra-invalid threshold, the one input in the manifest's `infra_invalid` block (review round 1);
   - each of its fields is checked against the schema's own spec for that field;
   - a field that fails raises `ConfigError` before the run folder or the index entry exists;
   - at the end, the outputs are added to that same part, so the two can no longer disagree.

   The model settings code (`model_interface/Settings`) is unchanged, so other users of it still accept, for
   example, a model name of only spaces. Only the harness refuses one.
3. **A non-finite reported model ID** cannot be refused at start: it comes from the provider during the run. The
   only real adapter turns every reported ID into text (`model_interface/anthropic_api.py:184-193`), so no real run
   can hold one. A run that holds one anyway is written with `"number:nan"` in its summary, and is refused when it is
   scored, as before. The task's outcome lists this case under refusals at start; `DEC-W2-03-CHOICES` says how it is
   handled.
4. **Acceptance `mechanism_only`** (`harness/score.py`, one line). A run set with a fixture price table and a
   sourced modelled-time file now has `acceptance.mechanism_only: true`, as its own `mechanism_only.cost` already
   said. The release check was not affected: it already makes a fixture price table not eligible.
5. **The reference-agent assertion** (`tests/t06_harness/test_reference.py`, test only). A reference agent gives
   every item one verdict and cites its lowest evidence ID, so an alert and its twin differ only in citations, and
   only when the twin leaves out the alert's lowest ID. On the frozen world no twin does, so the expected block is 45
   pairs and nothing divergent. The test now works that out from the world files and labels, and compares the whole
   block.

## No committed figure moved

`tests/w2_03_harness_fixes/test_rescore.py` copies `baseline/` and `w2-02-runs/` to a temporary folder, re-scores
each there with the code as it is now (as if by the commit that wrote the committed reports), and checks:

- **`w2-02-runs/` (run set `8f4050be`):** every run report equals the committed one as a whole. The set report
  equals the committed one as well, acceptance and `mechanism_only` included, except for two things that depend
  only on which command scored last (`docs/evidence/t07/known-issues.md`, issue 3):
  - the order of its runs;
  - which tied fraction a spread minimum or maximum shows (for example 0/2 against 0/3).

  Every run's own value must be equal exactly. A minimum or maximum may differ from the committed one only when
  both are among those runs' own values and equal in value; otherwise the whole rate object must be equal (review
  round 1).
- **`baseline/` (run set `f2e614d2`):** it was scored in T07, before W2-01 added injection figures and rewrote one
  placeholder text. So the keys added since are left out of the new report, the notes are not compared, and the
  AC-6 text `"not determined: no AC-16 target exists yet"` is mapped to its W2-01 wording. Every other value the
  committed report holds must come back equal. W2-01's own test (`tests/w2_01_acceptance/test_baseline.py`)
  still compares the figures byte for byte.
- **Both folders' `SHA256SUMS`** still verify, so no committed file was rewritten.

The `w2-02` gate still shows the release check giving PASS (cost bounded under a stated assumption) on `8f4050be`.

## Evidence

`docs/evidence/w2-03/`:

- `before.txt`: the new suite on a `git archive` copy of `f030aba` (code as at `fdb4fd6`), with only the new tests
  copied in. 15 failed, 4 errors, 19 passed. Each failure or error is a fix's own test:
  - the `TypeError` above, in the 4 model-ID tests;
  - "DID NOT RAISE ConfigError" in the 8 start-check cases and the 6 threshold cases;
  - the fixture-price case of the `mechanism_only` test.

  The 19 passes are the positive controls, the adapter test and the re-score checks, which pass before and after
  because nothing they compare changed.
- `after.txt`: the same suite on the build. 38 passed.
- `issue5-break-old-assertion.txt` and `issue5-break-new-assertion.txt`: a copy of the build in which
  `harness/score.py` counts every reference-agent pair whose citations agree as divergent. The old assertion (as at
  `f030aba`) still passes. The new one fails: 45 divergent against 0 expected.
- `gate-timings.txt`: the four gate suites, each run alone through `tools/timed_run.sh` on the charger:

  | Suite | Result | Time | Peak memory |
  |---|---|---|---|
  | w2_03 | 38 passed | 4.2 s | 1994 MB |
  | t06 | 340 passed, 6 skipped | 59.5 s | 2171 MB |
  | w2_01 | 68 passed | 65.3 s | 2120 MB |
  | w2_02 | 68 passed | 5.5 s | 2016 MB |

  Every suite is below the 120-second gate limit.

## Limits

- A provider reporting the text `"number:123"` and the number `123` in one run would have them counted under one key.
  No real adapter reports numbers.
- The start check covers the manifest's input-derived part. Item rows are checked when they are scored, as before.
- The run configuration's own check already refuses every threshold the schema refuses, so no real input reaches the
  new threshold check. Its test makes the configuration hand a bad value over, as if that check had drifted.
- The re-score test compares reports as JSON values, not as bytes, because of T07 known issue 3.
- The issue-5 break and the before run were made by hand, outside the gate. Only their output is kept.
