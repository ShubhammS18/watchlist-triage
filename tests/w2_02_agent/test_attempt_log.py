"""W2-02: the attempt log, docs/w2-02-attempts.md (DEC-W2-02-ATTEMPTS, DEC-W2-02-SPEND-PLAN). Its limit is six, its
attempt rows stay within it, every committed run set is logged, and the spend adds up and stays below USD 25.

The acceptance test needs a committed run set. It accepts a plain PASS, or a PASS (cost bounded under a stated
assumption) only with the owner's Console sign-off for that run set in the log (DEC-W2-01-PASS-LABEL). Until one
exists under w2-02-runs/ it is marked xfail (strict): it is expected to fail and shows as "xfailed" in every gate run;
once a run set is committed, it is an ordinary test.

The sign-off row is checked as far as the repository can check it: its harness amount is the committed run set's own
cost, rounded to the places written; its Console amount is within 5% of that cost; and its sign-off cell says
"matches". The Console reading itself stays the owner's check: no test can see the Console."""
import json
import re
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

import pytest

from conftest import LOG, PRACTICE_HASH, PRACTICE_SEED, REPO

RUNS = REPO.joinpath("w2-02-runs")
CEILING = Decimal("25.00")


def table(text, heading):
    """(header, data rows) of the table under `## heading`, each a list of cells."""
    body = text.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in body.split("\n") if line.startswith("|")]
    return rows[0], rows[2:]  # rows[1] is the separator


def section(text, heading):
    return table(text, heading)[1]


def spend(text, heading):
    header, rows = table(text, heading)
    return sum((Decimal(row[header.index("Spend USD")]) for row in rows), Decimal("0"))


def test_the_log_states_the_limit_the_ceiling_and_the_practice_world():
    text = LOG.read_text(encoding="utf-8")
    assert "- Attempt limit: 6\n" in text and "- Spend ceiling, all of wave 2: USD 25.00\n" in text
    assert f"seed {PRACTICE_SEED}, world hash `{PRACTICE_HASH}`" in text


def test_attempts_stay_within_the_limit_and_are_numbered_in_order():
    attempts = section(LOG.read_text(encoding="utf-8"), "Frozen-world attempts")
    assert len(attempts) <= 6
    assert [row[0] for row in attempts] == [str(number) for number in range(1, len(attempts) + 1)]


def test_the_spend_adds_up_and_stays_below_the_ceiling():
    text = LOG.read_text(encoding="utf-8")
    found = re.search(r"Wave-2 spend: USD (\d+\.\d\d) \(before this log (\d+\.\d\d) \+ attempts (\d+\.\d\d) "
                      r"\+ practice (\d+\.\d\d) \+ release (\d+\.\d\d)\)", text)
    total, before, attempts, practice, release = (Decimal(value) for value in found.groups())
    assert before == Decimal("0.00")  # the Console figure the log starts from
    assert attempts == spend(text, "Frozen-world attempts") and practice == spend(text, "Practice runs")
    assert total == before + attempts + practice + release and total < CEILING


def committed_run_sets():
    if not RUNS.exists():
        return set()
    index = json.loads(RUNS.joinpath("index.json").read_text(encoding="utf-8"))
    return {run["run_set"] for run in index["runs"]}


def test_every_committed_run_set_is_logged():
    logged = {row[4] for row in section(LOG.read_text(encoding="utf-8"), "Frozen-world attempts")}
    assert all(any(run_set.startswith(cell.strip("`")) and cell.strip("`") for cell in logged)
               for run_set in committed_run_sets())


@pytest.mark.xfail(not committed_run_sets(), strict=True, reason="no run set is committed under w2-02-runs/ yet")
def test_the_committed_run_set_passes_the_acceptance_check():
    run_sets = committed_run_sets()
    assert run_sets, "no committed run set"
    last = section(LOG.read_text(encoding="utf-8"), "Frozen-world attempts")[-1][4].strip("`")
    run_set = next(one for one in run_sets if one.startswith(last))
    done = subprocess.run([sys.executable, "-m", "harness", "acceptance", str(RUNS), run_set], cwd=REPO,
                          capture_output=True, text=True)
    result = json.loads(done.stdout)["result"]
    if (done.returncode, result) == (3, "PASS (cost bounded under a stated assumption)"):
        assert signed_off(run_set), f"a qualified pass needs the owner's Console sign-off for {run_set[:8]} in the log"
    else:
        assert (done.returncode, result) == (0, "PASS"), done.stdout[-2000:]


def run_set_cost(run_set):
    """The committed run set's own cost in USD, as the harness recorded it: the known cost of each of its runs, summed
    exactly."""
    index = json.loads(RUNS.joinpath("index.json").read_text(encoding="utf-8"))
    return sum((Fraction(run["cost"]["known_cost"]["numerator"], run["cost"]["known_cost"]["denominator"])
                for run in index["runs"] if run["run_set"] == run_set), Fraction(0))


def row_problem(row, header, cost):
    """Why a sign-off row does not sign off a run set that cost `cost` USD, or None."""
    console, harness = Decimal(row[header.index("Console USD")]), Decimal(row[header.index("Harness USD")])
    written = Decimal(cost.numerator) / Decimal(cost.denominator)
    if harness != written.quantize(harness, rounding=ROUND_HALF_UP):
        return f"its harness amount {harness} is not the run set's own cost {written}"
    if abs(Fraction(console) - cost) > cost * Fraction(5, 100):
        return f"its Console amount {console} is not within 5% of the run set's own cost {written}"
    if "matches" not in row[header.index("Sign-off")]:
        return 'its sign-off cell does not say "matches"'
    return None


def signed_off(run_set, cost=None):
    """The owner's Console sign-off for `run_set`: a row of the log's sign-off table naming it, which row_problem
    accepts. The Console figure in it is the owner's reading, which no test can check."""
    cost = run_set_cost(run_set) if cost is None else cost
    header, rows = table(LOG.read_text(encoding="utf-8"), "Console sign-off")
    return any(run_set.startswith(row[0].strip("`")) and row[0].strip("`") and row_problem(row, header, cost) is None
               for row in rows)


@pytest.mark.parametrize("row, accepted", [
    ("| `8f4050be` | 0.30 | 0.2998 | Owner, 29 Oct 2026: matches |", True),
    ("| `8f4050be` | 0.30 | 0.2998 |  |", False),  # no sign-off
    ("| `8f4050be` | 0.30 | 0.2998 | Owner: not checked |", False),  # no "matches"
    ("| `8f4050be` | 0.30 | 0.3100 | Owner: matches |", False),  # not the run set's own cost
    ("| `8f4050be` | 0.32 | 0.2998 | Owner: matches |", False),  # Console more than 5% away
    ("| `8f4050be` | 0.28 | 0.2998 | Owner: matches |", False),
    ("| `8f4050be` | 0.31 | 0.30 | Owner: matches |", True),  # rounded to the places written, within 5%
    ("| `1c8d128b` | 0.30 | 0.2998 | Owner: matches |", False),  # another run set
])
def test_a_sign_off_row_counts_only_with_the_run_sets_cost_a_close_console_amount_and_a_match(
        monkeypatch, tmp_path, row, accepted):
    log = tmp_path.joinpath("log.md")
    monkeypatch.setattr(sys.modules[__name__], "LOG", log)
    head = "## Console sign-off\n\n| Run set | Console USD | Harness USD | Sign-off |\n|---|---|---|---|\n"
    log.write_text(head + row + "\n", encoding="utf-8")
    assert signed_off("8f4050be" + "0" * 56, cost=Fraction(2997877, 10_000_000)) is accepted


def test_the_committed_run_sets_own_cost():
    assert run_set_cost("8f4050be0f28031f8ec64da2d193ecf12d9c5cb7aee868b4adda84e22c76f33e") == Fraction(2997877, 10_000_000)
