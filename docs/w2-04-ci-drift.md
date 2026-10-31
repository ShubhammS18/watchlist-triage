# CI drift check (W2-04)

Status: Draft, for review. The task adds the check that the frozen world regenerates byte-identically on every push
and pull request (NFR-2, AC-10), deferred to wave 2 by `DEC-CI-DRIFT-WAVE2`. Choices: `DEC-W2-04-CHOICES`. Review
budget: `DEC-W2-04-REVIEW-BUDGET`. No model was called.

## What was added

1. **The script, `tools/check_world_drift.py`.** It uses only the standard library and is run from the repository root
   as `python3 tools/check_world_drift.py`, with no arguments.
   - It refuses to run on any Python but 3.12: it prints `unsupported Python X.Y.Z: this check supports Python 3.12
     only. It did not run; this is not drift.` and exits with 2. It does this before `worldgen` is imported.
   - It regenerates the world from the seed in `worldgen/config.json` with `worldgen.build.generate` and `write`, into
     a temporary folder outside the repository. It refuses a temporary folder inside the repository.
   - It compares every file both ways with `data/world`: a file regenerated but not committed, a file committed but
     not regenerated, and a file whose bytes differ.
   - It recomputes the world hash from `data/world` by the definition in `MANIFEST.json`'s `header_comment`, in its
     own code and not with `worldgen`, and requires it to equal the frozen hash
     `b77a6804a52b1d41650e250a31ff64a701b1d315a674a1f1242d93cb6b15c9b0`. It also requires the committed manifest's
     `world_hash` field to equal it. The regenerated manifest is covered by the byte comparison. So a world
     re-seeded and committed together with its new manifest, where every byte agrees, still fails. The t02
     determinism test compares only with what is committed and does not catch that case.
   - It prints the Python version and platform, the seed, the file counts and the recomputed hash, then `OK` and exits
     with 0, or one `DRIFT:` line per problem and exits with 1. A line names a path and SHA-256s, never file
     contents. Any other error ends it with a traceback and a non-zero exit code.
   - It reads the committed `hidden/` files only as bytes to hash and compare. They are public and the world hash
     covers them.
2. **The workflow, `.github/workflows/world-drift.yml`.**
   - It runs on `[push, pull_request]`, with no branch, path or tag filters, and never on `pull_request_target`.
   - Its permissions are `contents: read` and nothing else.
   - One job on `ubuntu-24.04`, with a five-minute limit.
   - One action: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1), with
     `persist-credentials: false`. Before it was used, `gh api repos/actions/checkout/git/ref/tags/v7.0.1` showed the
     tag pointing straight at that commit, and the v7.0.1 release, published 20 Jul 2026, is not a pre-release.
   - One run step, the command above, on the runner's own `python3`. Ubuntu 24.04's system Python is 3.12. There is
     no `setup-python`, no package install, no secret and no `${{ }}` expression.
3. **The gate tests, `tests/w2_04_ci/`.**
   - `drift_common.py` defines the command once. The drift tests run it, and the static test requires the workflow's
     run line to equal it.
   - `test_drift.py`:
     - the script on the repository: exit 0, the seed, 11 files each side, the frozen hash, `OK`;
     - its comparison finds nothing on the committed world, and catches, each with the exact lines expected:
       - a changed byte in an `agent/`, a `hidden/` and the README file;
       - an extra committed file and a missing one;
       - a re-seeded world committed with its own manifest;
       - a manifest with another hash;
       - a manifest that is not JSON, not an object, or has no `world_hash`;
     - **end to end**, on a copy of `worldgen/`, `data/world`, `docs/rubric.md` and the script in a temporary
       folder outside the repository:
       - one flipped world byte fails the copied script with exit 1;
       - so does a re-seeded world: the copy's seed is changed to 1, and its world regenerated and written in place;
     - Python 3.11 and 3.13 are refused with the message above and exit 2, before `worldgen` is imported: the test
       lists the `worldgen` modules loaded when the script stops, and requires none. Only 3.12 is installed here, so
       the test replaces `sys.version_info` before the script runs. As the positive control, the same probe on
       Python 3.12 sees `worldgen.build` imported and the script reach `OK` (review round 1).
   - `test_workflow.py`, the static test:
     - exactly one workflow file, and its content must equal the text pinned in full in the test, so any change to
       the workflow fails the gate until the pinned text is deliberately updated (review round 1);
     - the line rules, which explain why the pinned text is acceptable and say what a bad edit breaks:
       - the top-level keys are `name`, `on`, `permissions` and `jobs`;
       - the trigger line is exactly `on: [push, pull_request]`;
       - one permissions block, at the top level, holding only `contents: read`;
       - `runs-on: ubuntu-24.04` and a timeout of at most five minutes;
       - one action, `actions/checkout` pinned to a 40-hex SHA, with `persist-credentials: false`;
       - one run step equal to the command;
       - no `if:` and no `continue-on-error:` on the job or a step, since either can skip the check or turn drift
         green (review round 1);
       - no `secrets`, `${{`, `pull_request_target` or `workflow_run` anywhere.

     There is no YAML library here, so the file is kept flat and the rules read it line by line after comments are
     removed. On their own they do not reject every key they do not know; the pinned text does. Twenty-one bad
     workflows show that each rule catches something; each also differs from the pinned text.
   - `tests/t02_world` is unchanged and is the second gate.

## What the tests cannot show

These are stated here instead of in the task outcome (`DEC-W2-04-CHOICES`).

1. **GitHub can skip or hold some runs.** The static test shows that the workflow is triggered by every push and
   pull request event. It cannot show that GitHub runs it every time:
   - GitHub skips push and pull-request runs for a commit whose message contains `[skip ci]`, `[ci skip]`,
     `[no ci]`, `[skip actions]` or `[actions skip]`;
   - the repository's setting holds runs on pull requests from first-time contributors' forks until the owner
     approves them;
   - Actions can be turned off in the repository settings.
2. **The gate checks the working tree; CI checks the pushed commit.** The gate test and the workflow run the same
   script with the same command, not the same check:
   - locally the script compares whatever is in `data/world`, uncommitted or untracked files included; on GitHub it
     compares the files of the commit that was pushed;
   - this difference fails closed: a stray untracked file fails locally and not on GitHub;
   - that the interpreter matches (Python 3.12 in both places) is held by the script's refusal, not by the same build.

## Evidence

`docs/evidence/w2-04/gate-timings.txt`: both gate suites, each run alone through `tools/timed_run.sh` on the charger:

| Suite | Result | Time | Peak memory |
|---|---|---|---|
| w2_04_ci | 40 passed | 9.2 s | 1805 MB |
| t02 | 699 passed | 28.1 s | 1820 MB |

Peak memory is the memory in use on the whole machine, as `tools/memory_guard.sh` reports it.

The deliberate breaks are in the gate itself (the end-to-end tests above), so the reviewer can re-run them.

A green run on GitHub, for a push and for a pull request, is the owner's check at review, and pushing the workflow
is the owner's step. The gate cannot see GitHub.

## Limits

- The claim is byte-identical regeneration under Python 3.12 only. No other Python version was tested. For example,
  `unicodedata` changes between minor versions.
- The script trusts `worldgen` to regenerate. It checks the result, not the generator's code.
- The static test reads a flat file with fixed rules, not YAML. Any other content, however GitHub would read it,
  fails the pinned-text check; it does not pass unchecked.
- On GitHub the check guards only what is pushed. It does not block a merge: `main` has no branch rule requiring it.
