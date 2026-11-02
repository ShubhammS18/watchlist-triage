"""W2-08: every release run's audit log (DEC-W2-08-CHECKPOINTS, DEC-W2-05-CHOICES; review round 1, findings 2, 4 and
7). A completed or aborted run needs its committed checkpoint and a log that verifies against it; a completed run's
log must end with its items file's hash and give, item by item, the answers its items file holds. A run that never
finished is counted from its log as it stands, marked unverified, but every record present is checked and bound to
its run, run set, freeze commit and world. A run folder the index does not list is caught, and counted."""
import json
from pathlib import Path

import release_common as rc


def published(cloned, pool, names, tmp_path, change=None, **options):
    """Assemble the named runs, let `change(out, chosen)` alter the output, and publish it."""
    clone, freeze = cloned
    out, chosen = rc.assemble(pool, names, tmp_path)
    if change is not None:
        change(out, chosen)
    rc.publish(clone, freeze, {"frozen": out}, **{key: [chosen[n] for n in value] if key == "skip_checkpoints" else value
                                                  for key, value in options.items()})
    return chosen


def test_a_completed_run_without_its_committed_checkpoint_is_not_eligible(cloned, frozen_pool, judge, tmp_path):
    chosen = published(cloned, frozen_pool, ["valid1", "valid2", "valid3"], tmp_path, skip_checkpoints=["valid2"])
    result = judge()
    assert result["result"] == "NOT ELIGIBLE"
    assert f"{chosen['valid2']}: its checkpoint is not committed at audit/checkpoints/{chosen['valid2']}.json" \
        in result["not_eligible_because"]
    assert result["targets"]["true_matches_closed"]["result"] == "pass"  # still worked out


def test_an_aborted_run_without_its_committed_checkpoint_is_not_eligible_and_still_counted(cloned, frozen_pool, judge,
                                                                                           tmp_path):
    chosen = published(cloned, frozen_pool, ["aborted_unsafe", "valid1", "valid2", "valid3"], tmp_path,
                       skip_checkpoints=["aborted_unsafe"])
    result = judge()
    assert result["result"] == "NOT ELIGIBLE" and result["failed"] == ["true_matches_closed"]
    assert any("its checkpoint is not committed" in p for p in result["not_eligible_because"])
    assert result["release"]["counted_from_logs"][chosen["aborted_unsafe"]] == "unverified: no checkpoint"


def test_an_edited_aborted_run_log_is_caught_by_its_checkpoint_and_still_counted(cloned, frozen_pool, judge, tmp_path):
    def edit(out, chosen):  # the reason of one record changed, nothing chained again: the checkpoint catches it
        path = Path(out, chosen["aborted_unsafe"], "audit.jsonl")
        path.write_bytes(path.read_bytes().replace(b'"reason":"Test candidate."', b'"reason":"Edited text."', 1))
    chosen = published(cloned, frozen_pool, ["aborted_unsafe", "valid1", "valid2", "valid3"], tmp_path, edit)
    result = judge()
    assert result["result"] == "NOT ELIGIBLE" and result["failed"] == ["true_matches_closed"]
    assert any(p.startswith(f"{chosen['aborted_unsafe']}: its audit log fails its check: record 1")
               for p in result["not_eligible_because"]), result["not_eligible_because"]
    assert result["release"]["counted_from_logs"][chosen["aborted_unsafe"]] == "unverified: its log fails its check"


def rewritten(run, change):
    """change(records) alters a run's log; the log is chained again and its checkpoint follows, so only the content
    can give it away."""
    def apply(out, chosen):
        found = rc.read_records(Path(out, chosen[run]))
        change(found)
        rc.write_records(Path(out, chosen[run]), found)
    return apply


def first_recommendation(found):
    return next(record for record in found if record["event"] == "recommendation")


def test_a_logged_answer_that_is_not_the_items_rows_is_not_eligible(cloned, frozen_pool, judge, tmp_path):
    def flip(found):
        record = first_recommendation(found)
        record["recommendation"] = "CLOSE" if record["recommendation"] == "ESCALATE" else "ESCALATE"
    chosen = published(cloned, frozen_pool, ["valid1", "valid2", "valid3"], tmp_path, rewritten("valid1", flip))
    result = judge()
    assert result["result"] == "NOT ELIGIBLE"
    assert any(p.startswith(f"{chosen['valid1']}: its log's answer for ") for p in result["not_eligible_because"])


def test_a_logged_citation_that_is_not_the_items_rows_is_not_eligible(cloned, frozen_pool, judge, tmp_path):
    def cite(found):
        first_recommendation(found)["cited_outside_bundle"] = 1
    published(cloned, frozen_pool, ["valid1", "valid2", "valid3"], tmp_path, rewritten("valid1", cite))
    assert any("its log's answer for" in p for p in judge()["not_eligible_because"])


def test_a_completed_log_missing_an_item_is_not_eligible(cloned, frozen_pool, judge, tmp_path):
    def drop(found):
        found.remove(first_recommendation(found))
    published(cloned, frozen_pool, ["valid1", "valid2", "valid3"], tmp_path, rewritten("valid1", drop))
    assert any("do not hold the same items" in p for p in judge()["not_eligible_because"])


def test_a_completed_log_that_does_not_end_with_the_items_hash_is_not_eligible(cloned, frozen_pool, judge, tmp_path):
    def rehash(found):
        found[-1]["items_sha256"] = "0" * 64
    published(cloned, frozen_pool, ["valid1", "valid2", "valid3"], tmp_path, rewritten("valid1", rehash))
    assert any("does not end with the completed run's items file hash" in p for p in judge()["not_eligible_because"])


def killed(run, change=None):
    def apply(out, chosen):
        rc.kill(out, chosen[run])
        if change is not None:
            change(Path(out, chosen[run]))
    return apply


def test_a_killed_run_is_counted_unverified_and_replaced(cloned, frozen_pool, judge, tmp_path):
    chosen = published(cloned, frozen_pool, ["aborted", "valid1", "valid2", "valid3"], tmp_path, killed("aborted"))
    result = judge()
    assert (result["result"], result["not_eligible_because"]) == ("PASS", [])
    assert result["release"]["counted_from_logs"] == {chosen["aborted"]: "unverified: no checkpoint"}
    assert result["release"]["runs"]["replaced"] == {chosen["aborted"]: "never finished"}


def test_an_unsafe_answer_in_a_killed_run_fails_the_set(cloned, frozen_pool, judge, tmp_path):
    published(cloned, frozen_pool, ["aborted_unsafe", "valid1", "valid2", "valid3"], tmp_path, killed("aborted_unsafe"))
    result = judge()
    assert (result["result"], result["failed"], result["not_eligible_because"]) == ("FAIL", ["true_matches_closed"], [])


def test_a_killed_runs_cut_off_last_line_is_left_out(cloned, frozen_pool, judge, tmp_path):
    def cut(run_dir):
        path = run_dir.joinpath("audit.jsonl")
        path.write_bytes(path.read_bytes() + b'{"v":1,"run_id":')
    published(cloned, frozen_pool, ["aborted", "valid1", "valid2", "valid3"], tmp_path, killed("aborted", cut))
    assert judge()["result"] == "PASS"


def broken_log(change):
    def apply(run_dir):
        found = rc.read_records(run_dir)
        change(found)
        rc.write_records(run_dir, found, checkpoint=False)
    return apply


def test_a_killed_runs_log_is_bound_to_its_run_set_freeze_and_world(cloned, frozen_pool, judge, tmp_path):
    cases = {"run_set": ("run_set", "1" * 64, "its log names run set 11111111"),
             "commit": ("commit", "2" * 40, "its log's commit is not the release's"),
             "world_hash": ("world_hash", "3" * 64, "its log's world_hash is not the release's")}
    for number, (name, (field, value, expected)) in enumerate(cases.items()):
        def change(found, field=field, value=value):
            found[0][field] = value
        folder = tmp_path.joinpath(str(number))
        published(cloned, frozen_pool, ["aborted", "valid1", "valid2", "valid3"], folder,
                  killed("aborted", broken_log(change)))
        result = judge()
        assert result["result"] == "NOT ELIGIBLE", name
        assert any(expected in p for p in result["not_eligible_because"]), (name, result["not_eligible_because"])


def test_a_killed_runs_log_with_a_record_of_another_run_is_not_eligible(cloned, frozen_pool, judge, tmp_path):
    def change(found):
        found[2]["run_id"] = "20200101T000000000000Z-00000000"
    published(cloned, frozen_pool, ["aborted", "valid1", "valid2", "valid3"], tmp_path,
              killed("aborted", broken_log(change)))
    result = judge()
    assert result["result"] == "NOT ELIGIBLE"
    assert any("fails its check" in p or "another run" in p for p in result["not_eligible_because"])


def test_a_malformed_record_in_a_killed_runs_log_is_not_eligible(cloned, frozen_pool, judge, tmp_path):
    def spoil(run_dir):
        path = run_dir.joinpath("audit.jsonl")
        lines = path.read_bytes().split(b"\n")
        lines[3] = lines[3].replace(b'"recommendation":"', b'"recommendation":"X', 1)
        path.write_bytes(b"\n".join(lines))
    chosen = published(cloned, frozen_pool, ["aborted", "valid1", "valid2", "valid3"], tmp_path, killed("aborted", spoil))
    result = judge()
    assert result["result"] == "NOT ELIGIBLE"
    assert any(p.startswith(f"{chosen['aborted']}: its audit log fails its check: record 3")
               for p in result["not_eligible_because"]), result["not_eligible_because"]


def test_an_unlisted_run_folder_is_not_eligible_and_its_answers_count(cloned, frozen_pool, judge, tmp_path):
    def unlist(out, chosen):
        rc.kill(out, chosen["aborted_unsafe"])
        index = rc.records.read_index(out)
        index["runs"] = [entry for entry in index["runs"] if entry["run_id"] != chosen["aborted_unsafe"]]
        rc.records.write_json(Path(out, "index.json"), index)
    chosen = published(cloned, frozen_pool, ["aborted_unsafe", "valid1", "valid2", "valid3"], tmp_path, unlist)
    result = judge()
    run = chosen["aborted_unsafe"]
    assert result["result"] == "NOT ELIGIBLE" and result["failed"] == ["true_matches_closed"]
    assert f"{run} is a run folder that the index does not list" in result["not_eligible_because"]
    assert result["release"]["runs"]["replaced"][run] == "not listed in the index"


def test_output_that_does_not_match_its_sha256sums_is_not_eligible(cloned, frozen_pool, judge, tmp_path):
    def change(clone):
        path = Path(clone, "release", "frozen", "index.json")
        path.write_text(json.dumps(json.loads(path.read_text())) + "\n")
    published(cloned, frozen_pool, ["valid1", "valid2", "valid3"], tmp_path, before_commit=change)
    assert "index.json does not match its hash in SHA256SUMS" in judge()["not_eligible_because"]


def test_a_set_file_of_another_run_set_is_not_eligible(cloned, frozen_pool, judge, tmp_path):
    def change(out, chosen):
        Path(out, "sets").mkdir()
        Path(out, "sets", "4" * 64 + ".json").write_text("{}\n")
    published(cloned, frozen_pool, ["valid1", "valid2", "valid3"], tmp_path, change)
    assert f"sets/{'4' * 64}.json is not the set file of this run set" in judge()["not_eligible_because"]


def test_the_counts_from_a_log_equal_the_counts_from_its_items(frozen_pool, fresh, fresh_pool):
    from harness import release, release_check, score
    from worldgen.truth import load_truth
    for pool, truth, names in ((frozen_pool, load_truth(), ["valid1", "infra1", "unbounded"]),
                               (fresh_pool, rc.fresh_truth(fresh[0]), ["over1"])):
        for name in names:
            run_dir = pool["out"].joinpath(pool[name])
            lines = [json.loads(line) for line in run_dir.joinpath("items.jsonl").read_text().split("\n") if line]
            logged = [release.as_line(r) for r in rc.read_records(run_dir) if r["event"] == "recommendation"]
            from_items, from_log = score.figures(lines, truth), release.safety(logged, truth)
            for count, read in release_check.COUNTS.values():
                assert read(from_log) == read(from_items), (name, count)
    # and an unsafe close, a failure and an outside citation are seen the same way in both
    line = json.loads(frozen_pool["out"].joinpath(frozen_pool["valid1"], "items.jsonl").read_text().split("\n")[0])
    line["result"].update(recommendation="CLOSE", system_failure=False, cited_ids=["EVD-NOT-SENT"])
    record = release.audit.recommendation(line, "0" * 64)
    assert score.valid_citation_set(line) is score.valid_citation_set(release.as_line(record)) is False


def test_a_symbolic_link_is_never_read_and_the_answers_still_count(cloned, frozen_pool, judge, tmp_path):
    """Review round 2, finding N3: a linked index or checkpoint is caught on disk before anything is read through it.
    The index is then not read, so every run is unlisted and counted from its log."""
    from test_freeze import linked
    clone, freeze = cloned
    out, chosen = rc.assemble(frozen_pool, ["aborted_unsafe", "valid1", "valid2", "valid3"], tmp_path)
    outside = tmp_path.joinpath("outside")
    outside.mkdir()

    def links(c):
        linked(c, "release/frozen/index.json", outside)
        linked(c, f"audit/checkpoints/{chosen['valid1']}.json", outside)
    rc.publish(clone, freeze, {"frozen": out}, before_commit=links)
    run_set = rc.records.read_index(frozen_pool["out"])["runs"][0]["run_set"]
    result = judge(run_set=run_set)
    because = result["not_eligible_because"]
    assert result["result"] == "NOT ELIGIBLE" and result["failed"] == ["true_matches_closed"]
    assert "release/frozen/index.json is a symbolic link; it is not read" in because
    assert f"audit/checkpoints/{chosen['valid1']}.json is a symbolic link; it is not read" in because
    assert f"{chosen['valid1']}: its checkpoint is not committed at audit/checkpoints/{chosen['valid1']}.json" in because
    assert set(result["release"]["counted_from_logs"]) == set(chosen.values())


def test_a_killed_runs_log_is_bound_to_the_full_run_set_id(cloned, frozen_pool, judge, tmp_path):
    """Review round 2, finding N2: another run-set ID with the same first eight characters is caught."""
    def change(found):
        found[0]["run_set"] = found[0]["run_set"][:8] + "f" * 56 if found[0]["run_set"][8:] != "f" * 56 else \
            found[0]["run_set"][:8] + "e" * 56
    chosen = published(cloned, frozen_pool, ["aborted", "valid1", "valid2", "valid3"], tmp_path,
                       killed("aborted", broken_log(change)))
    result = judge()
    assert result["result"] == "NOT ELIGIBLE"
    assert any(p.startswith(f"{chosen['aborted']}: its log names run set ") and "not the one its index entry names" in p
               for p in result["not_eligible_because"]), result["not_eligible_because"]


def changed_input(found):
    first_recommendation(found)["input_sha256"] = "5" * 64


def test_a_completed_logs_input_hash_is_made_again_from_the_checked_world(cloned, frozen_pool, judge, tmp_path):
    """Review round 2, finding N4: the log's own input hash is never the one it is compared with."""
    chosen = published(cloned, frozen_pool, ["valid1", "valid2", "valid3"], tmp_path, rewritten("valid1", changed_input))
    result = judge()
    assert result["result"] == "NOT ELIGIBLE"
    assert any(p.startswith(f"{chosen['valid1']}: its log's answer for ") for p in result["not_eligible_because"])


def test_a_killed_runs_input_hashes_are_checked_against_the_checked_world(cloned, frozen_pool, judge, tmp_path):
    chosen = published(cloned, frozen_pool, ["aborted", "valid1", "valid2", "valid3"], tmp_path,
                       killed("aborted", broken_log(changed_input)))
    result = judge()
    assert result["result"] == "NOT ELIGIBLE"
    assert any(p.startswith(f"{chosen['aborted']}: its log gives 1 input hashes that are not the checked world's")
               for p in result["not_eligible_because"]), result["not_eligible_because"]
