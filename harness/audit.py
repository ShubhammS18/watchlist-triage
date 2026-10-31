"""The audit log of one evaluation run (FR-14, FR-15, AC-9; DEC-W2-05-CHOICES, DEC-W2-05-AUDIT-FAULT). Python standard
library only, apart from the agent's own list of failure kinds.

The run step writes audit.jsonl in its run folder, one record per line: `run_started`, one `recommendation` per item
in the order the items finish, and `run_ended`, which holds the SHA-256 of the run's items.jsonl. Each record is
canonical JSON (sorted keys, no spaces, UTF-8, no floats) and holds `seq`, `prev` (the hash of the record before it,
or 64 zeros) and `hash`, the SHA-256 of its canonical form without `hash`. When the log is closed it is synced to
disk and checkpoint.json is written beside it: the run ID, the record count and the last hash. A copy of that
checkpoint, committed to git by the owner, is what a log is verified against; the harness never touches git.

Every field is typed (`FIELDS`), and a record that does not fit is refused, so structured fields hold only IDs,
hashes, enumerated values, numbers, timestamps, cited evidence IDs, decisions and model identifiers. The agent's
`reason` is the one free-text field, and it may contain synthetic customer values. Cited IDs outside the item's
bundle can be any text a model returned, so only their number and a hash of them are logged. A model name is logged
as it is when it fits the safe pattern, and as its hash otherwise (`model_name`, DEC-W2-05-MODEL-ID).
"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from baseline_agent.recommend import KINDS

LOG, CHECKPOINT = "audit.jsonl", "checkpoint.json"
VERSION = 1
START = "0" * 64  # the `prev` of the first record


class AuditWriteError(Exception):
    """The audit log could not be written. The run is aborted (DEC-W2-05-AUDIT-FAULT)."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def record_hash(record):
    return sha256(canonical({key: value for key, value in record.items() if key != "hash"}))


# ---- the types of the fields

def _match(pattern):
    compiled = re.compile(pattern)
    return lambda value: isinstance(value, str) and compiled.fullmatch(value) is not None


def _or_none(check):
    return lambda value: value is None or check(value)


def _list_of(check):
    return lambda value: isinstance(value, list) and all(map(check, value))


def _count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


HEX64 = _match(r"[0-9a-f]{64}")
ID = _match(r"[A-Z]{3}-[0-9]{2,6}")                      # an alert, twin, customer, watchlist or evidence ID
ITEM = _match(r"[A-Z]{3}-[0-9]{2,6}/[0-9]")              # an alert or twin in one framing
RUN = _match(r"[0-9]{8}T[0-9]{12}Z-[0-9a-f]{8}")
NAME = _match(r"[a-z][a-z0-9_]{0,63}")                   # an agent or provider name, as configured
ERROR = _match(r"[A-Za-z_][A-Za-z0-9_]{0,99}")           # an exception's type name, never its message
MODEL = _match(r"[A-Za-z0-9._:@/+-]{1,200}")             # the safe pattern of a model name: no spaces
AT = _match(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}\+00:00")
BOOL = lambda value: isinstance(value, bool)
TEXT = lambda value: value is None or isinstance(value, str)  # free text: the agent's reason only


def _one_of(*values):
    """Exactly one of `values`, of its own type: True is not 1, and 1.0 is not 1."""
    return lambda value: any(value == one and type(value) is type(one) for one in values)


COMMON = {"v": _one_of(VERSION), "run_id": RUN, "seq": _count, "at": AT, "prev": HEX64, "hash": HEX64,
          "event": _one_of("run_started", "recommendation", "run_ended")}
FIELDS = {
    "run_started": {"run_set": HEX64, "commit": _or_none(_match(r"[0-9a-f]{40}")), "dirty": BOOL, "world_hash": HEX64,
                    "agent": NAME, "provider": _or_none(NAME), "requested_model": _or_none(MODEL),
                    "prompt_sha256": _or_none(HEX64), "rule_code_sha256": _or_none(HEX64), "config_sha256": HEX64,
                    "framing_code_sha256": HEX64, "review_policy": _one_of("none")},
    "recommendation": {"item_id": ITEM, "alert_id": ID, "framing": _one_of(1, 2, 3), "twin": BOOL,
                       "input_sha256": HEX64, "recommendation": _one_of("CLOSE", "ESCALATE"), "system_failure": BOOL,
                       "failure_kind": _or_none(_one_of(*KINDS)), "citation_invalid": BOOL,
                       "cited_ids": _list_of(ID), "cited_outside_bundle": _count,
                       "cited_outside_bundle_sha256": _or_none(HEX64), "model_ids": _list_of(MODEL),
                       "attempts": _count, "reason": TEXT},
    "run_ended": {"state": _one_of("completed", "aborted"), "items": _count, "items_sha256": _or_none(HEX64),
                  "aborted_item_id": _or_none(ITEM), "error_type": _or_none(ERROR)},
}
FREE_TEXT = {"reason"}  # the fields an AC-22 check leaves out


def problem(record):
    """What is wrong with the shape of one record, or None."""
    if not isinstance(record, dict):
        return "not a JSON object"
    event = record.get("event")
    if not isinstance(event, str) or event not in FIELDS:
        return f"unknown event {event!r}"
    expected = {**COMMON, **FIELDS[event]}
    if set(record) != set(expected):
        return f"its fields are not those of {event}: missing {sorted(set(expected) - set(record))}, " \
               f"unknown {sorted(set(record) - set(expected))}"
    wrong = sorted(key for key, check in expected.items() if not check(record[key]))
    return f"these fields do not have their type: {wrong}" if wrong else None


def model_name(value):
    """A model identifier, requested or reported, as the log holds it (DEC-W2-05-MODEL-ID): as it is when it fits
    the safe pattern, otherwise "sha256:" and the hash of its text, so an odd label can neither abort the log nor put
    raw text in it. A number is first written as "number:<value>", as in the manifest (DEC-T06-MANIFEST-9). A real
    name that starts with "sha256:" is hashed too, so it can never be mistaken for the hash of another name (W2-05
    review round 2)."""
    text = value if type(value) is str else f"number:{value}"
    keep = MODEL(text) and not text.startswith("sha256:")
    return text if keep else "sha256:" + sha256(text.encode("utf-8", "surrogatepass"))


def recommendation(line, input_sha256):
    """The record body for one finished item of items.jsonl, its framed bundle hashing to `input_sha256`."""
    result, sent = line["result"], set(line["sent_ids"])
    outside = [cited for cited in result["cited_ids"] if cited not in sent]
    reported = (one["model_id"] for one in line["attempts"] if one["model_id"] is not None)
    return {"item_id": line["item_id"], "alert_id": line["alert_id"], "framing": line["framing"], "twin": line["twin"],
            "input_sha256": input_sha256, "recommendation": result["recommendation"],
            "system_failure": result["system_failure"], "failure_kind": result["failure_kind"],
            "citation_invalid": result["citation_invalid"],
            "cited_ids": [cited for cited in result["cited_ids"] if cited in sent],
            "cited_outside_bundle": len(outside), "cited_outside_bundle_sha256": sha256(canonical(outside)) if outside else None,
            "model_ids": sorted({model_name(one) for one in reported}),
            "attempts": len(line["attempts"]), "reason": result["reason"]}


# ---- writing

class Log:
    """The audit log of one run, open for appending. Every failure to write raises AuditWriteError, and after one
    every later write raises it too."""

    def __init__(self, folder, run_id):
        self.folder, self.run_id, self.seq, self.head, self.broken = Path(folder), run_id, 0, START, None
        try:
            self._file = open(self.folder.joinpath(LOG), "xb")
        except OSError as error:
            raise AuditWriteError(f"cannot create the audit log: {error}") from error

    def _emit(self, data):
        self._file.write(data)
        self._file.flush()

    def write(self, event, make=dict, **body):
        """Append one record of `event`: the fields `make()` returns, and `body`. Building, checking, hashing,
        encoding and writing it are one step, and any failure in it raises AuditWriteError (DEC-W2-05-AUDIT-FAULT)."""
        if self.broken:
            raise AuditWriteError(f"the audit log failed earlier: {self.broken}")
        try:
            record = {"v": VERSION, "run_id": self.run_id, "seq": self.seq, "event": event,
                      "at": datetime.now(timezone.utc).isoformat(timespec="microseconds"), "prev": self.head,
                      **make(), **body}
            record["hash"] = record_hash(record)
            refused = problem(record)
            if refused:
                raise ValueError(f"record {self.seq} ({event}) is refused: {refused}")
            self._emit(canonical(record) + b"\n")
        except Exception as error:
            self.broken = f"{type(error).__name__}: {error}"
            raise AuditWriteError(self.broken) from error
        self.seq, self.head = self.seq + 1, record["hash"]

    def close(self):
        """Sync the log to disk, close it and write the checkpoint of the records written."""
        try:
            if not self._file.closed:
                self._file.flush()
                os.fsync(self._file.fileno())
                self._file.close()
            temp = self.folder.joinpath(CHECKPOINT + ".tmp")
            temp.write_bytes(canonical(checkpoint(self.run_id, self.seq, self.head)) + b"\n")
            os.replace(temp, self.folder.joinpath(CHECKPOINT))
        except OSError as error:
            raise AuditWriteError(f"cannot close the audit log or write its checkpoint: {error}") from error


def checkpoint(run_id, records, head):
    return {"v": VERSION, "run_id": run_id, "records": records, "head": head}


# ---- verifying

def verify(log, trusted):
    """None if `log` (bytes) is the log that the checkpoint `trusted` vouches for; otherwise the first problem,
    naming the first record that cannot be vouched for, counted from 0."""
    if not isinstance(trusted, dict) or set(trusted) != set(checkpoint(0, 0, 0)) or not COMMON["v"](trusted["v"]) \
            or not RUN(trusted["run_id"]) or not _count(trusted["records"]) or not HEX64(trusted["head"]):
        return "the checkpoint is not a checkpoint of this log format"
    *lines, tail = log.split(b"\n")
    head = START
    for seq, line in enumerate(lines):
        try:
            record = json.loads(line.decode("utf-8"))
        except (ValueError, RecursionError):
            return f"record {seq}: not a JSON line"
        try:
            same = isinstance(record, dict) and canonical(record) == line
        except (ValueError, RecursionError):  # a lone surrogate cannot be encoded: UnicodeEncodeError is a ValueError
            same = False
        if not same:
            return f"record {seq}: not in the canonical form"
        found = problem(record)
        if found:
            return f"record {seq}: {found}"
        if record["seq"] != seq:
            return f"record {seq}: missing or out of order: line {seq} holds record {record['seq']}"
        if record["prev"] != head:
            return f"record {seq - 1}: its hash is not the one record {seq} follows"
        if record["hash"] != record_hash(record):
            return f"record {seq}: its hash does not match its content"
        if record["run_id"] != trusted["run_id"]:
            return f"record {seq}: it belongs to run {record['run_id']}, the checkpoint to run {trusted['run_id']}"
        head = record["hash"]
    count = len(lines)
    if tail:
        return f"record {count}: incomplete: the log does not end with a line feed"
    if count < trusted["records"]:
        return f"record {count}: missing: the log ends after {count} records, the checkpoint says {trusted['records']}"
    if count > trusted["records"]:
        return f"record {trusted['records']}: not covered by the checkpoint, which ends at {trusted['records']} records"
    if head != trusted["head"]:
        return f"record {count - 1}: the log's last hash is not the checkpoint's head"
    return None
