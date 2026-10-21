"""Task T07's own commands around the harness: the run wrapper, the trial, the gitleaks scan and the copy into
baseline/ (DEC-T07-WRAPPER, DEC-T07-WRAPPER-CHECKS, DEC-T07-TRIAL, DEC-T07-BASELINE-DIR). Python standard
library only. Nothing here changes T06 code: it calls the harness as it is.

    python -m baseline_run run CONFIG OUT [--rerun-cause TEXT]   a paid run, after every pre-run check
    python -m baseline_run trial OUT [--model-config PATH] [--alerts PATH]
    python -m baseline_run gitleaks FOLDER REPORT_DIR
    python -m baseline_run copy SOURCE
"""
