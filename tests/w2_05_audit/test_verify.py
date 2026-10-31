"""The verify command (AC-9, DEC-W2-05-CHOICES): it passes on an untouched log with its checkpoint and, given the same
checkpoint, fails and names the first bad record for an edited record, a deleted middle record, a reordered pair and a
deleted last record. Every case is made on a copy of a real fake-model run's log."""
import hashlib
import json
import subprocess
import sys

import pytest

from audit_common import REPO
from harness import audit

MIDDLE = 900  # a recommendation record


def split(data):
    return data.split(b"\n")[:-1]


def joined(lines):
    return b"".join(line + b"\n" for line in lines)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def rehashed(record):
    return {**record, "hash": hashlib.sha256(canonical({k: v for k, v in record.items() if k != "hash"})).hexdigest()}


def edited(lines, seq, rehash=False, **changes):
    """`lines` with record `seq` changed by `changes`, its own hash re-computed if `rehash`."""
    record = {**json.loads(lines[seq]), **changes}
    return [*lines[:seq], canonical(rehashed(record) if rehash else record), *lines[seq + 1:]]


def verify_command(tmp_path, data, trusted):
    """The verify command run on `data` and `trusted` written to files: (exit code, what it printed)."""
    log, checkpoint = tmp_path.joinpath("audit.jsonl"), tmp_path.joinpath("checkpoint.json")
    log.write_bytes(data)
    checkpoint.write_text(json.dumps(trusted), encoding="utf-8")
    done = subprocess.run([sys.executable, "-m", "harness", "verify-log", str(log), str(checkpoint)], cwd=REPO,
                          capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


def flipped(lines, seq):
    """Record `seq` with its decision turned the other way."""
    old = json.loads(lines[seq])["recommendation"]
    return edited(lines, seq, recommendation="ESCALATE" if old == "CLOSE" else "CLOSE")


# ---- the four cases of AC-9, through the command

def test_the_untouched_log_passes(tmp_path, log_bytes, trusted):
    assert verify_command(tmp_path, log_bytes, trusted) == (0, f"OK: 1847 records, head {trusted['head']}\n")


def test_an_edited_record_fails_and_is_named(tmp_path, log_bytes, trusted):
    assert verify_command(tmp_path, joined(flipped(split(log_bytes), MIDDLE)), trusted) == (
        1, f"FAILED: record {MIDDLE}: its hash does not match its content\n")


def test_a_deleted_middle_record_fails_and_is_named(tmp_path, log_bytes, trusted):
    lines = split(log_bytes)
    assert verify_command(tmp_path, joined(lines[:MIDDLE] + lines[MIDDLE + 1:]), trusted) == (
        1, f"FAILED: record {MIDDLE}: missing or out of order: line {MIDDLE} holds record {MIDDLE + 1}\n")


def test_a_reordered_pair_fails_and_is_named(tmp_path, log_bytes, trusted):
    lines = split(log_bytes)
    swapped = [*lines[:MIDDLE], lines[MIDDLE + 1], lines[MIDDLE], *lines[MIDDLE + 2:]]
    assert verify_command(tmp_path, joined(swapped), trusted) == (
        1, f"FAILED: record {MIDDLE}: missing or out of order: line {MIDDLE} holds record {MIDDLE + 1}\n")


def test_a_deleted_last_record_fails_and_is_named(tmp_path, log_bytes, trusted):
    lines = split(log_bytes)
    assert verify_command(tmp_path, joined(lines[:-1]), trusted) == (
        1, "FAILED: record 1846: missing: the log ends after 1846 records, the checkpoint says 1847\n")


# ---- more ways to break a log, through the function

@pytest.mark.parametrize("seq", [0, MIDDLE, 1846], ids=["first", "middle", "last"])
def test_an_edit_anywhere_is_named_where_it_is(log_bytes, trusted, seq):
    lines = split(log_bytes)
    change = {0: {"dirty": not json.loads(lines[0])["dirty"]}, MIDDLE: {"reason": "changed"},
              1846: {"items_sha256": "f" * 64}}[seq]
    assert audit.verify(joined(edited(lines, seq, **change)), trusted) == f"record {seq}: its hash does not match its content"


def test_an_edit_whose_own_hash_is_recomputed_is_named_by_the_next_link(log_bytes, trusted):
    lines = split(log_bytes)
    assert audit.verify(joined(edited(lines, MIDDLE, rehash=True, reason="changed")), trusted) == \
           f"record {MIDDLE}: its hash is not the one record {MIDDLE + 1} follows"


def test_an_edited_last_record_with_its_hash_recomputed_is_caught_by_the_checkpoint(log_bytes, trusted):
    lines = split(log_bytes)
    assert audit.verify(joined(edited(lines, 1846, rehash=True, items_sha256="f" * 64)), trusted) == \
           "record 1846: the log's last hash is not the checkpoint's head"


def test_an_edit_with_every_later_record_rehashed_is_caught_but_the_last_record_is_named(log_bytes, trusted):
    """The limit stated in DEC-W2-05-CHOICES: the chain is whole again, and only the checkpoint shows the change."""
    records = [json.loads(line) for line in split(log_bytes)]
    records[MIDDLE]["reason"] = "changed"
    for seq in range(MIDDLE, len(records)):
        records[seq] = rehashed({**records[seq], "prev": records[seq - 1]["hash"]})
    assert audit.verify(joined([canonical(r) for r in records]), trusted) == \
           "record 1846: the log's last hash is not the checkpoint's head"


def test_the_last_two_records_deleted_names_the_first_missing(log_bytes, trusted):
    assert audit.verify(joined(split(log_bytes)[:-2]), trusted) == \
           "record 1845: missing: the log ends after 1845 records, the checkpoint says 1847"


def test_a_record_rewritten_in_another_form_is_caught(log_bytes, trusted):
    lines = split(log_bytes)
    spaced = json.dumps(json.loads(lines[MIDDLE]), sort_keys=True, ensure_ascii=False).encode("utf-8")
    assert audit.verify(joined([*lines[:MIDDLE], spaced, *lines[MIDDLE + 1:]]), trusted) == \
           f"record {MIDDLE}: not in the canonical form"


def test_a_torn_last_line_an_empty_log_and_an_extra_record_are_caught(log_bytes, trusted):
    lines = split(log_bytes)
    assert audit.verify(joined(lines[:-1]) + lines[-1][:40], trusted) == \
           "record 1846: incomplete: the log does not end with a line feed"
    assert audit.verify(b"", trusted) == "record 0: missing: the log ends after 0 records, the checkpoint says 1847"
    shorter = {**trusted, "records": 1846, "head": json.loads(lines[-2])["hash"]}
    assert audit.verify(log_bytes, shorter) == "record 1846: not covered by the checkpoint, which ends at 1846 records"


def test_a_checkpoint_of_another_run_or_of_no_known_form_fails(log_bytes, trusted):
    other = {**trusted, "run_id": "20261031T000000000000Z-00000000"}
    assert audit.verify(log_bytes, other) == \
           f"record 0: it belongs to run {trusted['run_id']}, the checkpoint to run {other['run_id']}"
    for bad in ({**trusted, "records": -1}, {**trusted, "extra": 1}, [], {**trusted, "head": "x"}):
        assert audit.verify(log_bytes, bad) == "the checkpoint is not a checkpoint of this log format"


def test_a_record_of_the_wrong_shape_is_caught_even_with_its_hash_right(log_bytes, trusted):
    lines = split(log_bytes)
    record = json.loads(lines[MIDDLE])
    record["framing"] = 1.0
    assert audit.verify(joined([*lines[:MIDDLE], canonical(rehashed(record)), *lines[MIDDLE + 1:]]), trusted) == \
           f"record {MIDDLE}: these fields do not have their type: ['framing']"


def test_an_event_edited_to_a_list_is_named_through_the_command(tmp_path, log_bytes, trusted):
    """Review round 1: an event that is not text was a crash, not a named record."""
    assert verify_command(tmp_path, joined(edited(split(log_bytes), MIDDLE, event=[])), trusted) == (
        1, f"FAILED: record {MIDDLE}: unknown event []\n")


def test_a_record_holding_a_lone_surrogate_is_named(log_bytes, trusted):
    """Valid JSON whose text cannot be encoded as UTF-8: named, never a crash."""
    lines = split(log_bytes)
    bad = lines[MIDDLE].replace(b'"reason":"', b'"reason":"\\ud800', 1)
    assert audit.verify(joined([*lines[:MIDDLE], bad, *lines[MIDDLE + 1:]]), trusted) == \
           f"record {MIDDLE}: not in the canonical form"


def test_a_checkpoint_whose_version_is_not_exactly_1_is_refused(tmp_path, log_bytes, trusted):
    """Review round 1: True and 1.0 equal 1 in Python, but are not version 1."""
    for version in (True, 1.0, "1", 2):
        assert audit.verify(log_bytes, {**trusted, "v": version}) == \
               "the checkpoint is not a checkpoint of this log format", version
    assert verify_command(tmp_path, log_bytes, {**trusted, "v": True}) == (
        1, "FAILED: the checkpoint is not a checkpoint of this log format\n")
