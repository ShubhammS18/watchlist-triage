# Design docs: which is current

Each task's design doc describes the state when that task closed and is not edited afterwards. Where a later task
made a line out of date, the line is listed here and in the later doc's "Supersedes" table. For the current state of
the baseline, read `baseline-report.md`.

| Doc | Task | Status | Lines now out of date |
|---|---|---|---|
| `rubric.md` | T01-rubric | Done; version 1.2 is the rubric the world is built on | none |
| `world-design.md` | T02-world | Done; final after three review rounds | none |
| `framings-design.md`, `framings/wording-set.md` | T03-framings | Done | none |
| `model-interface-design.md` | T04-model-interface | Done | `:46` (no real adapter) and `:174-175` (stub only): a real Anthropic adapter now exists |
| `baseline-agent-design.md` | T05-baseline-agent | Done | `:12-14` and `:300` (only run against the stub, no baseline numbers): the baseline has run |
| `harness-design.md` | T06-harness | Done | `:30-31` and `:635` (only a test-only fake model): the harness has run a real model; `:134-135` and `:681-682` (a `runs/` folder inside the repository): runs stay outside the repository and are copied into `baseline/` |
| `baseline-report.md` | T07-baseline-run | Draft, in review | the current doc; its "Supersedes" table repeats the lines above |

Review reports are in `reviews/`; the evidence behind the T07 report is in `evidence/t07/`.
