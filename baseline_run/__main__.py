"""Command line of task T07's commands; see baseline_run/__init__.py."""
import argparse
import sys

from . import copy_step, gitleaks, trial, wrapper


def main(arguments=None):
    parser = argparse.ArgumentParser(prog="python -m baseline_run")
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("run")
    one.add_argument("config")
    one.add_argument("out")
    one.add_argument("--rerun-cause")
    one = commands.add_parser("trial")
    one.add_argument("out")
    one.add_argument("--model-config", default=trial.MODEL_CONFIG)
    one.add_argument("--alerts", default=trial.ALERTS)
    one = commands.add_parser("gitleaks")
    one.add_argument("folder")
    one.add_argument("report_dir")
    one = commands.add_parser("copy")
    one.add_argument("source")
    args = parser.parse_args(arguments)
    if args.command == "run":
        return wrapper.main(args.config, args.out, rerun_cause=args.rerun_cause)
    try:
        if args.command == "trial":
            return trial.show(trial.trial(args.out, args.model_config, args.alerts))
        if args.command == "gitleaks":
            return gitleaks.scan(args.folder, args.report_dir)
        listed = copy_step.copy_baseline(args.source)
        print(f"copied {len(listed)} files into baseline/ and listed them in baseline/{copy_step.LIST}; all verified")
        return 0
    except (ValueError, OSError) as problem:
        print(f"refused: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
