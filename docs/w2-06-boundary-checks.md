# Boundary checks (W2-06)

Status: built, 1 Nov 2026; review round 1 found two SHOULDs and no blocker, both fixed. The task checks the boundary parts of FR-10, FR-15, FR-18, AC-11, AC-20
and AC-22 that exist without operational mode. Choices: `DEC-W2-06-CHOICES`, within `DEC-T06-MANIFEST-9`; the deliberate break for older aborted runs: `DEC-W2-06-LEGACY-ABORT`. Review
budget: `DEC-W2-06-REVIEW-BUDGET`. No model was called: the tests use T06's fake model, the T04 stub and the committed
run outputs, read only. The network part of AC-11 is unchanged; nothing under `model_interface/` changed.

The checks are tests in `tests/w2_06_boundary`, plus two small changes to error text (below).

## The two changes to error text

1. **The run's abort record and the index cause keep the error type and a hash of the exception text, never the
   text.** `manifest.aborted` is now `{item_id, error_type, message_sha256}` (`harness/manifest.py` `abort_record`),
   and the index cause is `"<error type>: message sha256 <hash>"` (`abort_cause`, used by the run step and by the
   score step's check of the index against the manifest). The reason: the framings refuse a one-word name with
   `ValueError("cannot reorder the name '<name>': …")` (`framings/names.py:28`), so a world with such a customer would
   have put the customer's name into the manifest and the index. It never happens on the frozen world.
2. **A refusal describes a bad value by its type and a hash, never quoting it.** `harness/schema.py` `shown` (was
   `_shown`, which quoted up to 200 characters) gives `"a str with sha256 <hash of its repr>"`. The score step's
   disagreements between the index and the manifest (`harness/score.py` `validate_manifest`) and a bad price in a
   table (`harness/cost.py` `_number`) use it too. Refusal reasons otherwise stay readable, as `DEC-T06-MANIFEST-9`
   says: the run ID, then the exception type and message. Left as they are: a field's name in a refusal (including an
   unknown key's name), and the names of models and table groups, which are identifiers.

A hash of a short value can be guessed by trying candidates; it keeps the value out of the text, not secret.

Old runs: every committed run (`baseline/`, `w2-02-runs/`) is completed, with `aborted: null`, so none holds the old
abort record and their figures do not move (the `w2_03` re-score suite shows it). A run-output folder elsewhere that
holds an aborted run written before this change now fails the shared schema; by `DEC-T06-MANIFEST-9`'s fail-closed rule
no set in that folder is then eligible. This break is deliberate (`DEC-W2-06-LEGACY-ABORT`, review round 1, finding 1):
the older shape is not kept valid, because it holds exactly the raw text this change removes. The release runs use new
output folders.

T06 tests changed to match (no behaviour they check changed otherwise): `tests/t06_harness/test_run.py`,
`test_parallel.py` and `test_score.py` now expect the hashed abort record and cause.

T06 mutation proof 36 ("the manifest records the environment", `tests/t06_harness/mutations.py`) now plants the
environment where the final manifest is assembled. It used to plant it among the inputs, which the start-up check of
W2-03 refuses, so the broken copy never made a run and `test_no_environment_variable_reaches_any_output` failed in its
fixture, not on its assertion (review round 1, finding 2). The untouched-copy and exact-reason requirements are kept.

## The checks

### Capability allowlist (`test_capabilities.py`; FR-18, AC-11)

Read statically with Python's `ast` module (`inventory.py`), compared for equality with reviewed lists in the test:
modules that can reach a network, modules that start programs or load libraries, reads of the environment, programs
started, URLs in the code, the providers, the command lines and the harness's subcommands, the keys of every tracked
configuration (and that a link in a configuration sits only under a cited source or note), tracked credential files,
the CI workflows and the third-party packages. A keyword scan of identifiers and configuration keys for account and
regulator terms finds only the snippet wording "company filing".

Shows: the outward capabilities are exactly the reviewed list: the model call (`https://api.anthropic.com`, or the
tests' own machine), its key `WT_ANTHROPIC_API_KEY`, the free key check, git, gitleaks, the agent's child process and
the T04 test probes. A new one fails the test. Does not show: that none of them serves account actions or regulator
reporting (that rests on reading the list), anything built at run time (`importlib` with a computed name, `getattr`,
`eval`), what the provider can do on its side, or where else a human uses the key. The keyword scan is a second signal.

### Closing without a written reason (`test_reasons.py`; FR-6, FR-18, AC-11)

Both agents, through the real child with a scripted model: a CLOSE (baseline) or NO_LINK (triage) whose reason is
empty, spaces, missing, not text or null ends as ESCALATE with SYSTEM_FAILURE. Forged child answers with no reason are
refused again by each parent (`child_crash`, `BadResult`); the same answers with a reason close, as controls. For the
triage agent the check is on the model's reason: the CLOSE it builds would carry its own rule text either way. Every
CLOSE the triage rules give on the frozen world, in all framings and twins, has a written reason, which counts as one.

Does not show: that a reason is meaningful or supported by its citations, or that the harness refuses one: the item
row's `reason` accepts any text (`harness/schema.py`). Both agents, not the harness, refuse it.

### No customer value in a structured field (`test_customer_values.py`, `test_error_records.py`; FR-15, AC-22)

Values: every customer-record value of the frozen world's public customer file, `data/world/agent/customers.jsonl`
(name, address, date of birth, ID number, nationality, customer ID; 3,452 distinct). Left out: the as-of date, source
and version, the same on every world record. A test fails if the file gains a field that is in neither list.

Match (`customer_values.py`): a text is normalised (NFC, case folded) and split into words on anything that is not a
letter or digit; it matches when it holds a whole value as a run of words, all the non-title words of a customer's name
in any order, or a name or address word of four or more letters that is not a title or one of the generator's street
words (Street, Road, Lane, Avenue). Titles never match alone: in the pre-flight scan, a plain substring match found 1,828
false hits, all titles inside English words, and this rule found none.

Records checked, every object key and every text or number: a whole fake-model evaluation run's index, set report,
manifest, report, checkpoint, audit log and item rows; the committed real-model runs in `baseline/` and `w2-02-runs/`,
whose manifests and attempts hold the real provider model names, requested and reported; the typed log record of every
failure kind; and the error records of a run aborted by the name-format error, forced on a copy of the world whose
customer name is one word, then scored. Left out, disclosed: the agent's reason in the audit log and the items file.
The same match finds the customer values those reasons quote in the committed runs.

Controls: each kind of value (the shortest nationality, a date of birth, an ID number, an address, a name raw, in
capitals, inside a sentence and as framings 2 and 3 write it, one name word, a customer ID) planted as a value and as a
key in each kind of record is caught; and as a model name, it is caught in the manifest, which keeps model names raw,
and in the audit log whenever `DEC-W2-05-MODEL-ID` keeps it raw. Hashes of those values, run IDs, timestamps, evidence
and alert IDs, titles, address words and the model names do not match. Breaking the hash in the abort record, or
putting the quoted value back in `shown`, fails 11 of the 12 tests in `test_error_records.py` (checked by hand).

Does not show: paths the tests do not exercise, a value split across two fields, a transformed value other than the
framings' name forms, or anything about watchlist values. A hash of a value is allowed.

### Stores and where a run writes (`test_stores.py`; FR-10, FR-18, AC-20 evaluation half)

A run folder is the isolated per-run log the specification describes. The evaluation run above is traced with Python's
audit hooks: it writes only inside its output folder (its run folder; the run-set index; the set reports, each through
a `.tmp` file), and starts no program but `git rev-parse` and `git status`. Statically, every call in the product code
that can write a file belongs to a listed store (audit log, `write_json`, the items file, the reports, the world
generator, and the owner's copy, trial and gitleaks steps), and no database module is used. No file or key the run
writes names an L2 queue, a disposition, a final state or an approval, except the pacer's `queue_s` and the modelled
L2 review time `l2`; the run's review policy is `none`; and no product code names a disposition or an enqueue.

Does not show: that an L2 record or disposition would be refused (there is none in the code), writes outside Python
(the evaluation run uses the in-process agent, so no child process writes) or by Python's bytecode cache, or what the
owner does with git.

## Gate timings

Measured on 1 Nov 2026 through `tools/timed_run.sh` (charger in, benchmark at most 1.2 s, memory guard at 3,000 MB),
one run each, in this order. Genesis stops a gate command after 120 s.

| Suite | Result | Time | Benchmark | Memory in use: before, peak |
|---|---|---|---|---|
| `tests/w2_06_boundary` (gate `tests`) | 127 passed | 7.73 s | 0.836 s | 1,487 MB, 1,590 MB |
| `tests/t04_model_interface` (gate `t04`) | 137 passed | 41.45 s | 0.845 s | 1,526 MB, 1,615 MB |
| `tests/t05_agent` (gate `t05`) | 291 passed | 65.55 s | 0.827 s | 1,580 MB, 1,668 MB |
| `tests/t06_harness` (not a gate; `harness/schema.py` changed) | 340 passed, 6 skipped | 68.18 s | 0.832 s | 1,562 MB, 1,759 MB |
| `tests/w2_03_harness_fixes` (re-score suite; not a gate) | 38 passed | 5.48 s | 0.832 s | 1,522 MB, 1,575 MB |

t06's 6 skipped tests are the mutation proofs, as at the W2-05 gate (340 passed, 6 skipped). The slowest gate, t05,
leaves about 54 s to the 120-second stop. The benchmark ran at 0.83 to 0.85 s, slower than the 0.77 to 0.81 s of the
T06 timings; the Windows power mode is not known.

A pass/fail run on battery the same morning, not a timing, had one t06 failure: a manifest whose `started_at` was
0.7 s after its `ended_at`, because the clock stepped back during the run (systemd-journald logged "Time jumped
backwards"). The run step takes both times from the wall clock; the timed run above passed.

After the round-1 fixes, measured on 1 Nov 2026 the same way, with the charger in:

| Suite | Result | Time | Benchmark | Memory in use: before, peak |
|---|---|---|---|---|
| `tests/w2_06_boundary` (gate `tests`) | 127 passed | 7.58 s | 0.834 s | 1,732 MB, 1,817 MB |
| `tests/t04_model_interface` (gate `t04`) | 137 passed | 41.42 s | 0.829 s | 1,770 MB, 1,847 MB |
| `tests/t05_agent` (gate `t05`) | 291 passed | 63.29 s | 0.836 s | 1,810 MB, 1,899 MB |
| `tests/t06_harness` | 340 passed, 6 skipped | 67.69 s | 0.850 s | 1,816 MB, 1,949 MB |
| `tests/w2_03_harness_fixes` | 38 passed | 5.52 s | 0.832 s | 1,738 MB, 1,779 MB |
| T06 mutation proofs (`T06_MUTATION=1`, `test_mutation.py`) | 7 passed | 34.43 s | 0.828 s | 1,709 MB, 2,407 MB |

The proof table (`python tests/t06_harness/mutations.py`, run once more under the memory guard) shows breakage 36
passing on its untouched copy and failing on its broken one, and 43 of 43 breakages caught, with the real files
unchanged.
