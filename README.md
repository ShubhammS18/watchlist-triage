# watchlist-triage

An L1 triage agent for sanctions and PEP name-match alerts. For each alert it recommends CLOSE or ESCALATE and cites
its evidence. A human always decides. All data is synthetic: "true match" is a label I planted in a synthetic world,
not a real hit, and I make no claim of regulatory compliance.

## Status

Wave 1, the evaluation harness and a naive baseline, is done. Wave 2, the upgrades meant to meet the release
targets, is in progress, starting with planning.

## Baseline results

Claude Haiku 5.5, one fixed prompt, three runs over 600 alerts in three framings (`docs/baseline-report.md`, from
the output in `baseline/`).

- **It missed 3 true matches**: one in each run, always in the second framing and the common-name family. One
  reading of the hidden labels shows all three are one alert carrying injected text. In these runs it was closed
  only in that version; with the injected text removed it was escalated every time. (Corrected 23 Oct 2026;
  `docs/baseline-report.md`, Correction.)
- **It closed 1 alert that is ambiguous by design.**
- It escalated 52.7% of clear false positives (2562/4860).
- The three framings of an alert agreed for 68.8% of alerts (1239/1800).
- Every close of a clear false positive cited the supporting evidence (2298/2298).
- Model cost was about USD 0.00019 per alert-framing item, USD 1.04 for all three runs.
- On modelled review times, assisted review was slower than manual: 71.70 minutes per alert against 20.00 at the
  base settings with every close second-reviewed. It would save time only by escalating fewer than about 3.95% of
  clear false positives. The times are assumptions, mostly from vendor sources (`config/modelled_time.json`), not
  measurements.

## How it is evaluated

- A frozen world of 600 alerts: 30 true matches, 30 ambiguous, 540 clear false positives (`docs/world-design.md`).
  The labels are in hidden files the agent's loader does not read.
- Three framings of each alert, differing only in field order, name format and note wording.
- Three runs, because the model's answers vary.
- The time assumptions and the rules for the targets were committed before any result existed.
- A fresh session from a different AI provider reviews each task (`docs/reviews/`).

## Release targets

From `targets/release-targets.json` and `SPEC.md`:

- no true match and no ambiguous alert closed, in any run or framing;
- a valid citation set on every close, and 100% citation accuracy;
- at most 3.9% of clear false positives escalated;
- framings agreeing for at least 68.84% of alerts (1239/1800);
- at most USD 0.20 per alert-framing item;
- assisted review faster than manual on the modelled times.

## Main limits

- One synthetic world, which may not represent real alerts; 6 true matches per family.
- No real analyst timings.
- I built the world, so I can see the labels.
- Three runs show the variation; they do not bound it.
- Model reasons in `baseline/` may quote synthetic customer details.
- Each check is narrow: the citation checks test which evidence is cited, not whether the reason is right.

## Running the tests

No test needs an API key; the adapter is tested against a fake local API. Installing pytest needs the network once.
The T07 tests read the git history, so use a git clone, not a downloaded archive. I run them with Python 3.12, on
Linux (WSL).
`tests/w2_07_isolation/` needs unprivileged user namespaces (`unshare -rnm`) on Linux and fails without them.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
for t in tests/t0*/ tests/w2_*/; do .venv/bin/python -m pytest "$t" -q -p no:cacheprovider; done
```

## Repository map

- `worldgen/`, `data/world/`: world generator and frozen world
- `framings/`, `model_interface/`, `baseline_agent/`, `harness/`: framings, model adapter, agent, harness
- `baseline_run/`, `baseline/`: run wrapper and committed baseline output
- `config/`, `targets/`: settings and release targets
- `docs/`, `tests/`: design docs, reviews, evidence; tests per task

See `docs/baseline-report.md` for the full baseline and `docs/README.md` for which design docs are current.

## Licence

Apache-2.0 (`LICENSE`).
