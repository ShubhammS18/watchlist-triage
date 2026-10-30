"""W2-03, T06 known issue 4: a run set's acceptance block is marked mechanism only when either table is a fixture,
not only the modelled-time file. The set's own mechanism_only block, one flag per table, is unchanged."""
import pytest

from conftest import FIXTURE, SOURCED, WORLD, write_config
from harness import run as harness_run
from harness import score


@pytest.mark.parametrize("prices, times", [("fixture", "fixture"), ("fixture", "sourced"), ("sourced", "fixture"),
                                           ("sourced", "sourced")])
def test_acceptance_is_mechanism_only_when_either_table_is_a_fixture(tmp_path, prices, times):
    tables = {"fixture": FIXTURE, "sourced": SOURCED}
    out = tmp_path.joinpath("out")
    config = write_config(tmp_path, agent="always_escalate", price_table=tables[prices]["price_table"],
                          modelled_time=tables[times]["modelled_time"])
    manifest = harness_run.run(config, out)
    report = score.score_all(out, WORLD)["sets"][manifest["run_set"]]
    assert report["mechanism_only"] == {"cost": prices == "fixture", "modelled_time": times == "fixture"}
    assert report["acceptance"]["mechanism_only"] is ("fixture" in (prices, times))
