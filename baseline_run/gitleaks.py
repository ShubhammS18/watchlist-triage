"""The gitleaks scan of trial and run output (DEC-T07-RUN-SET, "Amendment after S3"): the exact recorded command
on one folder, with gitleaks' built-in rules, no config, no ignore file and inline allow comments ignored. It
refuses a folder that holds a .gitleaks.toml anywhere, since that could change the rules. Exit code 0 is clean,
1 is findings; anything else means the scan itself failed.
"""
import subprocess
from pathlib import Path

BIN = str(Path.home().joinpath(".cache/pre-commit/repocw4do5nh/golangenv-default/bin/gitleaks"))  # v8.30.1
NO_IGNORE = "/tmp/gitleaks-noignore"


def command(folder, report_dir, binary=BIN):
    folder = Path(folder).resolve()
    report = Path(report_dir).resolve().joinpath(f"gitleaks-{folder.name}.json")
    return ["env", "-u", "GITLEAKS_CONFIG", "-u", "GITLEAKS_CONFIG_TOML", binary, "dir", str(folder), "--no-banner",
            "--redact", "--verbose", "--ignore-gitleaks-allow", "-i", NO_IGNORE, "--report-format", "json",
            "--report-path", str(report)]


def scan(folder, report_dir, binary=BIN):
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError(f"{str(folder)!r} is not a folder")
    found = sorted(str(p) for p in folder.rglob(".gitleaks.toml"))
    if found:
        raise ValueError(f"the folder holds a gitleaks config, so the scan would not use the built-in rules: {found}")
    Path(NO_IGNORE).mkdir(parents=True, exist_ok=True)
    code = subprocess.run(command(folder, report_dir, binary)).returncode
    print({0: "gitleaks: clean", 1: "gitleaks: FINDINGS, stop (DEC-T07-RUN-SET)"}.get(
        code, f"gitleaks: the scan failed with exit code {code}"))
    return code
