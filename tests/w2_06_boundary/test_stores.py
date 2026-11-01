"""Where an evaluation run writes, and what persists (FR-10, FR-18, AC-20 evaluation half, DEC-W2-06-CHOICES).

A run folder is the isolated per-run log the specification describes. An evaluation run writes only inside its output
folder: its run folder, the run-set index and the set reports. The persistent stores are the world store and the run
folders, with the index and set reports beside them. Only the audit log and the items file hold free text, the agent's
reason. There is no L2 queue and no final disposition in the code, so these checks show that none is written, not that
one would be refused. The trace comes from Python's audit hooks in the test process: Python's own bytecode cache and
anything outside Python are not seen; the evaluation run uses the in-process agent, so no child process writes."""
import json
import re
from pathlib import Path

import inventory
from conftest import REPO, lines_of
from harness import audit, schema

WRITES = {  # (file, function, call): every call in the product code that can write, move or remove a file
    ("harness/audit.py", "__init__", "open xb"), ("harness/audit.py", "close", "temp.write_bytes"),
    ("harness/audit.py", "close", "os.replace"),  # the audit log and its checkpoint, in the run folder
    ("harness/manifest.py", "write_json", "temp.write_text"), ("harness/manifest.py", "write_json", "os.replace"),
    # write_json writes the manifest, the run-set index, the run and set reports, and the trial results
    ("harness/run.py", "run", "run_dir.mkdir"), ("harness/run.py", "run", "run_dir.joinpath('items.jsonl').write_text"),
    ("harness/score.py", "score_all", "out.joinpath('sets').mkdir"),
    ("worldgen/build.py", "write", "target.parent.mkdir"), ("worldgen/build.py", "write", "target.write_bytes"),  # the world store
    # the owner's steps around a paid run: the copy into baseline/, the trial before it, the gitleaks report folder
    ("baseline_run/copy_step.py", "copy_baseline", "dest.joinpath(name).parent.mkdir"),
    ("baseline_run/copy_step.py", "copy_baseline", "shutil.copyfile"),
    ("baseline_run/copy_step.py", "copy_baseline", "dest.joinpath(LIST).write_text"),
    ("baseline_run/trial.py", "trial", "out.mkdir"), ("baseline_run/gitleaks.py", "scan", "Path(NO_IGNORE).mkdir"),
}
RUN_FILES = {"audit.jsonl", "checkpoint.json", "checkpoint.json.tmp", "manifest.json", "manifest.json.tmp", "items.jsonl",
             "report.json", "report.json.tmp"}
L2_WORDS = re.compile(r"(?<![a-z])(l2|queue|enqueue|enqueued|dispositions?|final|finali[sz]ed?|finali[sz]e|approv\w*)(?![a-z])")


def _written(evaluation):
    """Every path the run wrote, created, moved or removed, relative to its output folder; and those outside it."""
    out, inside, outside = evaluation["out"].resolve(), set(), set()
    for event, path in evaluation["trace"]:
        if event == "launch" or "__pycache__" in path:
            continue
        try:
            inside.add(str(Path(path).relative_to(out)))
        except ValueError:
            outside.add((event, path))
    return inside, outside


def test_an_evaluation_run_writes_only_inside_its_output_folder(evaluation):
    inside, outside = _written(evaluation)
    assert not outside
    run_id, run_set = evaluation["run_dir"].name, evaluation["manifest"]["run_set"]
    assert inside == {".", run_id, "index.json", "index.json.tmp", "sets", f"sets/{run_set}.json", f"sets/{run_set}.json.tmp",
                      *(f"{run_id}/{name}" for name in RUN_FILES)}


def test_an_evaluation_run_starts_no_program_but_git(evaluation):
    started = [program for event, program in evaluation["trace"] if event == "launch"]
    assert started and all(program[0] == "git" and program[1] in ("rev-parse", "status") for program in started)


def test_every_write_in_the_product_code_is_one_of_the_listed_stores():
    assert inventory.writes() == WRITES


def test_no_database_or_other_store_module_is_used():
    assert not inventory.imports(inventory.STORES)


def test_only_the_audit_log_and_the_items_file_hold_free_text():
    """The reason is the one free-text field of the audit log, and the abort record keeps a hash of the exception text,
    never the text."""
    assert audit.FREE_TEXT == {"reason"}
    aborted = schema.MANIFEST.specs["aborted"]["aborted"]
    assert set(aborted) == {"item_id", "error_type", "message_sha256"} and aborted["message_sha256"] is schema.HEX64


def _allowed(key, path):
    """queue_s is the pacer's waiting time; l2 is the modelled L2 review time, a parameter of the modelled-time file."""
    return key == "queue_s" or (key == "l2" and "modelled_time" in path)


def test_no_l2_queue_record_or_final_disposition_is_written(evaluation):
    """No file or key the run wrote names an L2 queue, a disposition, a final state or an approval, and the review
    policy of the run is none."""
    found = []

    def walk(value, path):
        if isinstance(value, dict):
            for key, inner in value.items():
                if L2_WORDS.search(key.lower()) and not _allowed(key, path):
                    found.append(f"{path}.{key}")
                walk(inner, f"{path}.{key}")
        elif isinstance(value, list):
            for inner in value:
                walk(inner, path)

    out, files = evaluation["out"], 0
    assert not [path.name for path in out.rglob("*") if L2_WORDS.search(path.name.lower())]
    for path in out.rglob("*"):
        if path.suffix in (".json", ".jsonl"):
            files += 1
            for record in (lines_of(path) if path.suffix == ".jsonl" else [json.loads(path.read_text(encoding="utf-8"))]):
                walk(record, path.name)
    assert files == 7 and not found
    log = lines_of(evaluation["run_dir"].joinpath(audit.LOG))
    assert log[0]["review_policy"] == "none" and {line["event"] for line in log} == {"run_started", "recommendation", "run_ended"}


def test_no_product_code_names_an_l2_queue_or_a_disposition():
    """Static: the words appear only as the modelled L2 time, the pacer's queue time and the thread queues of the run
    and the child pipe."""
    found = set()
    for name, tree in inventory.sources():
        text = REPO.joinpath(name).read_text(encoding="utf-8")
        found |= {(name, word) for word in re.findall(r"\b\w*(?:dispos|enqueue|finali[sz]|l2_queue|queue_record)\w*", text,
                                                       re.IGNORECASE)}
    assert found == set()
