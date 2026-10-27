"""Command line of the evaluation harness.

    python -m harness run CONFIG OUT [--rerun-cause TEXT]   one run; OUT must lie outside the repository. It
                                                            writes no report, by design: the run step never
                                                            loads the truth
    python -m harness run-and-score CONFIG OUT [--rerun-cause TEXT]
                                                            an evaluation run (AC-24): the run, then the score
                                                            step for OUT against the run's own world
    python -m harness check-hidden WORLD                    only checks the hidden files against the world manifest
    python -m harness score OUT WORLD [--rescore]           writes a report for every completed run under OUT that
                                                            has none; --rescore replaces the reports that exist
    python -m harness supersede OUT OLD NEW --cause TEXT    a human records that run set OLD is superseded by NEW
    python -m harness acceptance OUT RUN_SET [--world WORLD]
                                                            judges run set RUN_SET under OUT against the release
                                                            targets; writes nothing, prints the result as JSON, and
                                                            exits 0 only on PASS
"""
import argparse
import json
import sys
from pathlib import Path

from . import manifest as records
from .run import WorldMismatch, _json, check_world, load_config, run


def main(arguments=None):
    parser = argparse.ArgumentParser(prog="python -m harness")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "run-and-score"):
        one = commands.add_parser(name)
        one.add_argument("config")
        one.add_argument("out")
        one.add_argument("--rerun-cause")
    one = commands.add_parser("check-hidden")
    one.add_argument("world")
    one = commands.add_parser("score")
    one.add_argument("out")
    one.add_argument("world")
    one.add_argument("--rescore", action="store_true")
    one = commands.add_parser("supersede")
    one.add_argument("out")
    one.add_argument("old")
    one.add_argument("new")
    one.add_argument("--cause", required=True)
    one = commands.add_parser("acceptance")
    one.add_argument("out")
    one.add_argument("run_set")
    one.add_argument("--world", default=str(records.REPO.joinpath("data", "world")))
    args = parser.parse_args(arguments)
    try:
        if args.command in ("run", "run-and-score"):
            manifest = run(args.config, args.out, rerun_cause=args.rerun_cause)
            print(f"{manifest['run_id']}: {manifest['state']}")
            if manifest["state"] != "completed":
                return 1
            if args.command == "run":
                return 0
            args.world = load_config(args.config)["world"]  # the world the run itself was made on
            args.rescore = False
        if args.command == "check-hidden":
            check_world(args.world, _json(Path(args.world).joinpath("MANIFEST.json")), hidden=True)
            print("the hidden files match the world manifest")
        elif args.command in ("score", "run-and-score"):
            # not at the top: the run step must never load the scoring code, so it is loaded only after the run
            from .score import score_all
            first = manifest["run_id"] if args.command == "run-and-score" else None  # scored and written first
            done = score_all(args.out, args.world, rescore=args.rescore, first=first)
            print(f"wrote {len(done['written'])} reports, kept {len(done['kept'])}, "
                  f"for {len(done['sets'])} run sets")
            for run_id, reason in done["excluded"].items():  # refused one by one; the others were scored
                print(f"excluded {run_id}: {reason}", file=sys.stderr)
            if done["excluded"]:
                return 1
        elif args.command == "acceptance":
            from .release_check import check  # loads the scoring code, like the score command
            result = check(args.out, args.run_set, args.world)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["result"] == "PASS" else 1
        else:
            records.supersede(args.out, args.old, args.new, args.cause)
            print(f"run set {args.old[:8]} is superseded by {args.new[:8]}")
    except (WorldMismatch, ValueError, OSError) as problem:  # ConfigError and ScoreRefused are ValueErrors
        print(f"refused: {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
