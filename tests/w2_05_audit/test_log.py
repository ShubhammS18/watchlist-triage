"""What a run's audit log holds (FR-14, DEC-W2-05-CHOICES): one run_started record, one recommendation per item, and
run_ended with the hash of items.jsonl, chained and canonical, and the checkpoint beside it. Expected values are worked
out from the world files and items.jsonl, not from the log code."""
import hashlib
import json
import subprocess
import sys

from audit_common import REPO, WORLD, lines_of
from framings import FRAMINGS, frame
from harness import audit
from worldgen.harness_twins import load_twins
from worldgen.loader import load_alerts


def records_of(data):
    return [json.loads(line) for line in data.decode("utf-8").split("\n") if line]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def test_a_run_leaves_its_log_and_checkpoint_and_the_log_verifies(full_run, log_bytes, trusted):
    folder, manifest, _ = full_run
    assert sorted(path.name for path in folder.iterdir()) == ["audit.jsonl", "checkpoint.json", "items.jsonl",
                                                              "manifest.json"]
    assert audit.verify(log_bytes, trusted) is None
    assert trusted["records"] == manifest["items"]["total"] + 2 == 1847


def test_the_events_are_one_start_one_per_item_and_one_end(full_run, log_bytes):
    folder, manifest, _ = full_run
    records = records_of(log_bytes)
    assert [r["event"] for r in records] == ["run_started"] + ["recommendation"] * 1845 + ["run_ended"]
    assert [r["seq"] for r in records] == list(range(len(records)))
    items = lines_of(folder.joinpath("items.jsonl"))
    assert sorted(r["item_id"] for r in records[1:-1]) == [line["item_id"] for line in items]   # each item once
    assert records[-1] == {**records[-1], "state": "completed", "items": 1845, "aborted_item_id": None,
                           "error_type": None, "items_sha256": sha(folder.joinpath("items.jsonl").read_bytes())}
    assert records[-1]["items_sha256"] == manifest["outputs"]["sha256"]


def test_the_start_record_names_what_the_manifest_names(full_run, log_bytes):
    _, manifest, _ = full_run
    start = records_of(log_bytes)[0]
    assert {key: start[key] for key in ("run_id", "run_set", "world_hash", "agent", "config_sha256",
                                        "framing_code_sha256", "commit", "dirty")} == {
        "run_id": manifest["run_id"], "run_set": manifest["run_set"], "world_hash": manifest["world"]["world_hash"],
        "agent": manifest["agent"], "config_sha256": manifest["config_sha256"],
        "framing_code_sha256": manifest["framing_code_sha256"], **manifest["git"]}
    assert (start["provider"], start["requested_model"], start["prompt_sha256"], start["review_policy"]) == (
        manifest["model"]["provider"], manifest["model"]["requested"], manifest["prompt"]["sha256"], "none")
    assert start["prev"] == "0" * 64


def test_each_recommendation_record_matches_its_item_and_the_bundle_sent(full_run, log_bytes):
    folder, _, _ = full_run
    items = {line["item_id"]: line for line in lines_of(folder.joinpath("items.jsonl"))}
    alerts = {a["id"]: a for a in [*load_alerts(WORLD.joinpath("agent")), *load_twins(WORLD.joinpath("agent"))]}
    for record in records_of(log_bytes)[1:-1]:
        line = items[record["item_id"]]
        result, sent = line["result"], set(line["sent_ids"])
        bundle = frame(alerts[line["alert_id"]], line["framing"])
        assert record["input_sha256"] == sha(canonical(bundle))
        assert {key: record[key] for key in ("alert_id", "framing", "twin")} == \
               {key: line[key] for key in ("alert_id", "framing", "twin")}
        assert {key: record[key] for key in ("recommendation", "system_failure", "failure_kind", "citation_invalid",
                                             "reason")} == \
               {key: result[key] for key in ("recommendation", "system_failure", "failure_kind", "citation_invalid",
                                             "reason")}
        assert record["cited_ids"] == [cited for cited in result["cited_ids"] if cited in sent]
        assert record["cited_outside_bundle"] == len([cited for cited in result["cited_ids"] if cited not in sent])
        assert record["attempts"] == len(line["attempts"])
        assert record["model_ids"] == sorted({one["model_id"] for one in line["attempts"] if one["model_id"]})
    assert {line["framing"] for line in items.values()} == set(FRAMINGS)


def test_cited_text_from_outside_the_bundle_is_only_counted_and_hashed(full_run, log_bytes):
    """The fake cites EVD-UNKNOWN on some escalations: that text is never logged, only its count and a hash."""
    folder, _, _ = full_run
    outside = [r for r in records_of(log_bytes)[1:-1] if r["cited_outside_bundle"]]
    assert outside and all(r["cited_outside_bundle_sha256"] == sha(canonical(["EVD-UNKNOWN"])) for r in outside)
    assert b"EVD-UNKNOWN" not in log_bytes and b"EVD-UNKNOWN" in folder.joinpath("items.jsonl").read_bytes()


def test_every_line_is_canonical_json_with_no_floats_and_is_chained(log_bytes):
    def refuse(text):
        raise AssertionError(f"float {text} in the log")

    head = "0" * 64
    for line in log_bytes.split(b"\n")[:-1]:
        record = json.loads(line, parse_float=refuse)
        assert canonical(record) == line
        assert record["prev"] == head
        assert record["hash"] == sha(canonical({k: v for k, v in record.items() if k != "hash"}))
        head = record["hash"]
    assert log_bytes.endswith(b"\n") and b"\r" not in log_bytes


def test_the_checkpoint_holds_the_run_the_count_and_the_last_hash(full_run, log_bytes, trusted):
    folder, manifest, _ = full_run
    last = records_of(log_bytes)[-1]
    assert trusted == {"v": 1, "run_id": manifest["run_id"], "records": 1847, "head": last["hash"]}
    assert folder.joinpath("checkpoint.json").read_bytes() == canonical(trusted) + b"\n"


def test_the_verify_command_passes_on_the_untouched_log(full_run, trusted):
    folder, _, _ = full_run
    done = subprocess.run([sys.executable, "-m", "harness", "verify-log", str(folder.joinpath("audit.jsonl")),
                           str(folder.joinpath("checkpoint.json"))], cwd=REPO, capture_output=True, text=True)
    assert (done.returncode, done.stdout) == (0, f"OK: 1847 records, head {trusted['head']}\n"), done.stderr


def test_the_run_step_never_writes_to_git(full_run):
    """The harness never touches git: the only git commands of a run read the commit and the status."""
    _, _, commands = full_run
    assert commands and all(command[0] == "git" and command[1] in ("rev-parse", "status") for command in commands)
