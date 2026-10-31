# Audit log (W2-05)

Status: Draft, for review. The task gives every evaluation run a hash-chained audit log and a checkpoint (FR-14,
AC-9), with structured fields that hold no customer values (FR-15, AC-22). Choices: `DEC-W2-05-CHOICES`. The fault:
`DEC-W2-05-AUDIT-FAULT`. Review budget: `DEC-W2-05-REVIEW-BUDGET`. No model was called.

## What a run writes

The run step (`harness/run.py`) now also writes, in its run folder outside the repository:

- **`audit.jsonl`** (`harness/audit.py`). It holds one record per line, in this order:
  - `run_started`, before the world check;
  - one `recommendation` per item, written as the item finishes, in finishing order;
  - `run_ended`.

  A whole run has 1 + 1,845 + 1 = 1,847 records.
- **`checkpoint.json`**, written when the log is closed: `{"v": 1, "run_id": …, "records": n, "head": <last hash>}`.

Every record holds:
- `v`, `run_id`, `seq` (from 0), `event` and `at` (a UTC time);
- `prev`, the previous record's hash, or 64 zeros for the first record;
- `hash`.

A record is canonical JSON: sorted keys, no spaces, UTF-8, no floats, one line ending in LF. Its `hash` is the
SHA-256 of that form without `hash`. The file is appended to and flushed record by record, and synced to disk once,
when it is closed.

What each event holds besides those fields:

| Event | Fields |
|---|---|
| `run_started` | run_set, commit, dirty, world_hash, agent, provider, requested_model, prompt_sha256, rule_code_sha256, config_sha256, framing_code_sha256, review_policy (`none`: evaluation mode) |
| `recommendation` | item_id, alert_id, framing, twin, input_sha256 (the framed bundle that was sent), recommendation, system_failure, failure_kind, citation_invalid, cited_ids, cited_outside_bundle, cited_outside_bundle_sha256, model_ids, attempts, reason |
| `run_ended` | state, items, items_sha256, aborted_item_id, error_type |

- **`run_ended.items_sha256`** is the SHA-256 of the `items.jsonl` the run then writes. So a committed checkpoint
  vouches for the log, and through it for the exact items that are scored.
- **Typed fields.** Every field has a type (`audit.FIELDS`): an ID pattern, a 64-hex hash, an enumerated value, a
  whole number, a boolean, a UTC time, or a model identifier with no spaces. A record that does not fit is refused
  before it is written.
  - `reason` is the one free-text field, and it may contain synthetic customer values.
- **Cited IDs.** Cited IDs outside the item's bundle can be any text a model returned, so they are logged only as a
  count and the SHA-256 of their list. The full result stays in `items.jsonl`.
- **What is not logged:**
  - exception messages: only the error type is logged;
  - scoring: it can be repeated later, and its figures follow from the items the log vouches for.

## Faults

A failure to write the log is a harness fault (`DEC-W2-05-AUDIT-FAULT`). This covers:
- creating the log or writing any record;
- the final sync, or writing the checkpoint;
- a record that does not fit its types.

What happens then:
- No item is handed off after that.
- The calls in flight are waited for, so the run's known cost stays complete. `hand_off` turns a failure to keep a
  finished item into that item's fault, with its calls, through `_keep`.
- The run ends aborted with `error_type` `AuditWriteError`.

The task's outcome says such a run is "marked failed". The harness has no failed state, so the run is aborted, and an
aborted run is never valid. It never counts toward the three valid runs, and the run-set report lists it under
`aborted`. `score.py`, `schema.py` and `release_check.py` are unchanged.

Every run that created its log closes it and writes a checkpoint of the records it did write, aborted runs included,
and an aborted run's log is never deleted. An aborted run whose log can still be written ends with `run_ended`
`state: "aborted"`. If closing the log fails after a completed `run_ended` was written, the run is aborted and has no
checkpoint, while its log's last record still says completed.

## Verifying

```
python -m harness verify-log LOG CHECKPOINT
```

It prints `OK: <n> records, head <hash>` and exits 0, or prints `FAILED: record <k>: …` and exits 1, naming the first
record that cannot be vouched for, counted from 0.

For each record, in this order, it checks:
1. the line is canonical JSON;
2. the record fits its types;
3. `seq` is its position;
4. `prev` is the previous record's hash;
5. `hash` matches its content;
6. it belongs to the checkpoint's run.

Then it compares the record count and the last hash with the checkpoint.

| Case (AC-9) | Named |
|---|---|
| an edited record *k* | *k*: its hash does not match its content |
| an edited record *k* with its own hash re-computed | *k*: its hash is not the one record *k+1* follows |
| a deleted middle record *k* | *k*: missing or out of order |
| a reordered pair *k*, *k+1* | *k*: missing or out of order |
| a deleted last record | the first record missing |

If someone edits a record and re-hashes every record after it, the chain is whole again. The change is still caught
through the checkpoint, but the last record is named instead (`DEC-W2-05-CHOICES`).

The checkpoint to verify against is the copy committed under `audit/checkpoints/`, not the one beside the log.

## Committing checkpoints (the owner's step)

The harness never touches git: a run only reads the commit and the status, and a test shows it. Committing each
checkpoint is the owner's step, so the log's anchor depends on that step. Every real-model run commits its checkpoint,
practice runs included. Runs with the fake model never do.

The run's commit is one of the inputs that define a run set. So a run is made from a separate checkout at the run
commit, and its checkpoint is committed from the main checkout. That way committing never moves the run's commit,
never splits a run set, and never leaves the run's tree dirty. For example:

```
git worktree add --detach ../watchlist-triage-at-<commit> <commit>
cd ../watchlist-triage-at-<commit>
<main checkout>/.venv/bin/python -m harness run-and-score CONFIG OUT
cd <main checkout>
cp OUT/<run_id>/checkpoint.json audit/checkpoints/<run_id>.json
git add audit/checkpoints/<run_id>.json && git commit -m "Checkpoint <run_id>" && git push
```

A checkpoint is an anchor only once it is pushed: until then a commit can be amended. Release runs are already made
from a clean checkout of the freeze commit (`DEC-W2-RELEASE-RULES`). After the freeze, a file under
`audit/checkpoints/` is a checkpoint file, and a published log with its `checkpoint.json` is run output. The existing
copy step copies both with the run folder.

## What the log can and cannot show

It can show, against a checkpoint that was committed and pushed:
- that the log is the one the harness wrote by then: no record edited, removed, reordered or cut off the end;
- through `items_sha256`, that the scored items are the ones that run wrote.

It cannot show:
- that the harness or the model told the truth;
- that a run nobody checkpointed never happened;
- when anything happened, beyond the time of the push;
- anything about human decisions. There is no operational mode (`DEC-W2-SCOPE`), so the log records the agent's
  recommendations and nobody approves them, and the operational half of FR-14's checkpoint rule never applies.

Its anchor is only as strong as the public git history.

Runs made before this task, in `baseline/` and `w2-02-runs/`, are not chained and have no log.

## Tests (`tests/w2_05_audit/`)

- `test_log.py`: a whole fake-model run.
  - Its events, order and chain; every line canonical with no floats.
  - `run_started` against the manifest.
  - Each recommendation against its item, with the bundle hash worked out from the world files.
  - `run_ended` against the hash of `items.jsonl`, and the checkpoint.
  - The fake's `EVD-UNKNOWN` citations appear only as a count and a hash.
  - The verify command passes.
  - The run's only git commands are `rev-parse` and `status`.
- `test_verify.py`:
  - the four AC-9 cases through the command;
  - edits of the first, middle and last record;
  - an edit with its own hash re-computed, and with every later record re-hashed (the stated limit);
  - the last two records deleted;
  - a record in another form, a torn last line, an empty log, a record beyond the checkpoint;
  - a checkpoint of another run or of no known form;
  - a float in place of a whole number.
- `test_fault.py`, with a model that counts its calls:
  - a failed write mid-run, on the sequential path and with four workers. With four workers, no call is still
    running when the run returns, and every call made is in the cost;
  - a failed first write, a failed last write, and a failed sync, which leaves no checkpoint;
  - a log-aborted run beside a good one in one run set: one valid run, and the aborted one listed;
  - a record of the wrong type refused, with the log stopped.
- `test_fields.py`:
  - no structured string of the run's log contains any name, address, date of birth, ID number or nationality of
    the world's customers;
  - the reason is the only field that accepts free text;
  - the types refuse free text, floats, booleans, unknown fields and missing fields.

### Changes to earlier tests

Four t06 assertions listed the files a run leaves. Each now includes `audit.jsonl` and `checkpoint.json`:

- `tests/t06_harness/test_manifest.py:78`: a whole run leaves 5 files, not 3. The same test checks that no
  environment variable reaches any of them.
- `tests/t06_harness/test_score.py:1074`: the files present when the score step first opens the hidden folder.
- `tests/t06_harness/test_run.py:266` and `tests/t06_harness/test_parallel.py:319`: an aborted run's folder holds its
  manifest, log and checkpoint, and no `items.jsonl`.

The owner agreed to the first two at the pre-flight, and to the other two during the build.

## Evidence

`docs/evidence/w2-05/`:

- `breaks.txt`: three deliberate breaks made by hand and then undone. Each is caught by the new tests:
  - verify without its `seq` check: the deleted-middle and reordered-pair tests fail;
  - the parallel hand-off without `_keep`: the in-flight test fails;
  - `run_ended` without the items hash: the events test fails.
- `gate-timings.txt`: the four gate suites and the W2-03 re-score suite, each run alone through
  `tools/timed_run.sh` on the charger.

  | Suite | Result | Time | Peak memory (whole machine) | At W2-03 |
  |---|---|---|---|---|
  | w2_05_audit | 38 passed | 7.4 s | 1602 MB | new |
  | t06 | 340 passed, 6 skipped | 67.1 s | 1764 MB | 59.5 s |
  | w2_01 | 68 passed | 70.5 s | 1736 MB | 65.3 s |
  | w2_02 | 68 passed | 6.2 s | 1637 MB | 5.5 s |
  | w2_03 (evidence) | 38 passed | 5.5 s | 1618 MB | 4.2 s |

  Every suite is below the 120-second gate limit. t06 and w2_01 took about 8 and 5 seconds longer than at W2-03,
  with the fixed benchmark the same, 0.82 s. Writing the log costs about 0.08 s per whole run (1,845 records and
  the close, timed alone), so most of that difference is not explained; it was not measured further.

  `tests/w2_03_harness_fixes` is not one of this task's gates. It is run as evidence that the committed `baseline/`
  and `w2-02-runs/` figures did not move.

## Limits

- **Model identifiers.** One with a space or other unusual character does not fit its type, so a run whose provider
  reported one would be aborted. The only real adapter reports IDs such as `claude-haiku-5-5`.
- **Completed log, aborted run.** If closing the log fails after `run_ended` was written, the run is aborted with no
  checkpoint while the log says completed (see Faults).
- **Aborted runs and the safety counts.** An aborted run writes no items, so the release check never sees its
  answers. Its log still holds the recommendations made before the fault. Whether the release counts them under
  `DEC-W2-01-RUN-RULE` ("every run that produced output") is for the release task.
- **The fake model only.** The AC-22 scan covers the fake model's records. The types make the rule hold for every
  structured field; for the reason it is disclosed, not tested.
