"""The capability allowlist check (FR-18, AC-11, DEC-W2-06-CHOICES): the repository's outward capabilities, read
statically from the product code and its configuration, equal the reviewed lists below. A new capability fails here
until it is added on purpose. Each listed one is the model call, its key, git, gitleaks, the agent's own child process
or a test probe; that none serves account actions or regulator reporting rests on that review, not on this test.
The keyword scan is a second signal only. Static analysis cannot see code built at run time."""
import ast
import fnmatch
import json
import re
import subprocess
import sys

import pytest

import inventory
from conftest import REPO
from model_interface import anthropic_api, providers
from baseline_run import wrapper

# ---- the reviewed lists

NETWORK = {  # modules that can reach a network
    ("model_interface/anthropic_api.py", "http"), ("model_interface/anthropic_api.py", "urllib"),  # the model call
    ("baseline_run/wrapper.py", "http"), ("baseline_run/wrapper.py", "urllib"),  # the free key check before a paid run
    ("model_interface/probe_child.py", "socket"),  # test probe: proves inside the guarded child that a socket is refused
}
PROCESSES = {
    ("baseline_run/gitleaks.py", "subprocess"), ("baseline_run/wrapper.py", "subprocess"),
    ("harness/manifest.py", "subprocess"), ("harness/release_check.py", "subprocess"),
    ("model_interface/runner.py", "subprocess"),  # starts the agent's child process
    ("model_interface/child.py", "subprocess"), ("model_interface/child.py", "_posixsubprocess"),  # replaced by refusals
    ("harness/run.py", "concurrent"),  # the worker threads of a run
    ("model_interface/probe_child.py", "subprocess"), ("model_interface/probe_child.py", "ctypes"),  # test probes
}
ENVIRONMENT = {
    ("model_interface/anthropic_api.py", "KEY_VARIABLE"),  # WT_ANTHROPIC_API_KEY, the one credential
    ("baseline_run/wrapper.py", "KEY_VARIABLE"),  # the same key, for the key check
    ("baseline_run/wrapper.py", "the whole environment"),  # passed on to the run it starts, plus its own settings
}
LAUNCHES = {
    ("harness/manifest.py", "subprocess.run", "git"), ("harness/release_check.py", "subprocess.run", "git"),
    ("baseline_run/wrapper.py", "subprocess.run", "git"),
    ("baseline_run/wrapper.py", "subprocess.run", "command"),  # tools/timed_run.sh python -m harness run-and-score
    ("baseline_run/gitleaks.py", "subprocess.run", "command(folder, report_dir, binary)"),  # gitleaks, a secret scan
    ("model_interface/runner.py", "subprocess.Popen", "[sys.executable, '-I', str(CHILD), module]"),  # the agent child
    # test probes, each tried inside the guarded child to show that starting a program is refused
    ("model_interface/probe_child.py", "subprocess.run", "[PROGRAM]"), ("model_interface/probe_child.py", "os.system", "PROGRAM"),
    ("model_interface/probe_child.py", "os.execv", "PROGRAM"), ("model_interface/probe_child.py", "os.posix_spawn", "PROGRAM"),
    ("model_interface/probe_child.py", "os.spawnv", "os.P_WAIT"), ("model_interface/probe_child.py", "os.fork", ""),
}
HARNESS_COMMANDS = "{run,run-and-score,check-hidden,score,supersede,acceptance,verify-log}"
ENTRY_POINTS = {"baseline_run/__main__.py", "harness/__main__.py", "worldgen/__main__.py", "tools/bench_reference.py",
                "tools/check_world_drift.py", "tools/memory_guard.sh", "tools/power_check.sh", "tools/timed_run.sh"}
CONFIG_KEYS = {
    "config/model.json": {"max_tokens", "model", "options", "provider", "temperature", "thinking", "timeout_s"},
    "config/modelled_time.json": {"BASE", "HIGH", "LOW", "kind", "l2", "manual_clearing", "note", "proposal_review",
                                  "second_review", "sets", "sources", "unit"},  # l2: the modelled L2 review time
    "config/prices.json": {"claude-haiku-5-5", "currency", "date", "input", "kind", "models", "note", "output", "source",
                           "sources", "unit"},
    "config/run.json": {"agent", "infra_invalid_threshold", "model_config", "modelled_time", "pacer_per_minute",
                        "price_table", "workers", "world"},
    "config/run-triage.json": {"agent", "infra_invalid_threshold", "model_config", "modelled_time", "pacer_per_minute",
                               "price_table", "workers", "world"},
    "model_interface/config.json": {"max_tokens", "model", "provider", "temperature", "timeout_s"},
    "trial/model.json": {"max_tokens", "model", "options", "provider", "temperature", "thinking", "timeout_s"},
    "targets/release-targets.json": {"baseline", "baseline_pooled", "baseline_source", "citation_accuracy",
                                     "cost_per_alert", "denominator", "direction", "kind", "note", "numerator",
                                     "over_escalation", "report", "rule", "run_commit", "run_set", "set_report",
                                     "set_report_sha256", "target", "target_decimal", "targets", "unit", "valid_runs",
                                     "verdict_consistency"},
    "worldgen/config.json": {"AMBIGUOUS_BY_DESIGN", "CLEAR_FALSE_POSITIVE", "TRUE_MATCH", "alerts", "ambiguous_per_family",
                             "as_of_date", "background_customers", "background_watchlist_entries",
                             "clear_false_positive_hard_families", "clear_false_positive_hard_per_family",
                             "clear_false_positive_plain", "counts", "dob_year_max", "dob_year_min", "families",
                             "id_prefix", "injection_per_label", "labels", "pep_offset_days",
                             "secondary_family_true_matches_per_primary_family", "seed", "source",
                             "true_match_per_primary_family", "version"},
}
SECRET_FILES = (".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "credentials*.json")  # the .gitignore patterns
CREDENTIAL_WORDS = {"key", "token", "secret", "password", "credential", "credentials", "url", "endpoint", "host", "webhook"}
# Account and regulator terms, matched as whole words of identifiers, text constants that are names, and config keys.
TERMS = {"account", "accounts", "freeze", "offboard", "offboarding", "regulator", "regulators", "regulatory", "goaml",
         "fincen", "filing", "sar", "fiu", "suspicious", "report_to_regulator", "debank"}
TERM_HITS = {("framings/wording.py", "filing")}  # the wording "company filing" in a synthetic snippet template


def test_the_modules_that_can_reach_a_network_are_the_reviewed_list():
    assert inventory.imports(inventory.NETWORK) == NETWORK


def test_the_modules_that_can_start_programs_or_load_libraries_are_the_reviewed_list():
    assert inventory.imports(inventory.PROCESSES) == PROCESSES


def test_the_environment_is_read_only_for_the_reviewed_key():
    assert inventory.environment() == ENVIRONMENT
    assert {name for name, _ in inventory.environ_uses()} == {name for name, _ in ENVIRONMENT}
    assert len(inventory.environ_uses()) == 3  # every use of os.environ is one of the reads above
    assert anthropic_api.KEY_VARIABLE == wrapper.KEY_VARIABLE == "WT_ANTHROPIC_API_KEY"


def test_the_only_network_destinations_are_the_model_api_and_the_tests_own_machine():
    assert anthropic_api.API_URL == wrapper.KEY_CHECK_URL == "https://api.anthropic.com"
    assert anthropic_api.LOCAL_HOSTS == ("127.0.0.1", "localhost")
    urls = {(name, url) for name, tree in inventory.sources() for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            for url in re.findall(r"[a-z]+://[^\s'\")]+", node.value)}  # in code and in docstrings
    assert urls == {("model_interface/anthropic_api.py", "https://api.anthropic.com"),
                    ("baseline_run/wrapper.py", "https://api.anthropic.com")}


def test_the_programs_started_are_the_reviewed_list():
    assert inventory.launches() == LAUNCHES


def test_the_providers_are_the_stub_and_the_model_call():
    """Read from the source: these tests register the test-only fake providers in the running process."""
    tree = ast.parse(REPO.joinpath("model_interface", "providers.py").read_text(encoding="utf-8"))
    listed, = (node.value for node in tree.body if isinstance(node, ast.Assign) and ast.unparse(node.targets[0]) == "PROVIDERS")
    assert {key.value for key in listed.keys} == {"stub", "anthropic"} and set(providers.PROVIDERS) >= {"stub", "anthropic"}


def test_the_command_lines_are_the_reviewed_list():
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    entry_points = {name for name in tracked if name.endswith("/__main__.py") or name.startswith("tools/")}
    assert {name for name in entry_points if not name.startswith("tests/")} == ENTRY_POINTS
    shown = subprocess.run([sys.executable, "-m", "harness", "--help"], cwd=REPO, capture_output=True, text=True,
                           check=True, env={"PYTHONDONTWRITEBYTECODE": "1"}).stdout
    assert HARNESS_COMMANDS in shown


def _keys(value, path=""):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key, path
            yield from _keys(inner, f"{path}.{key}")
    elif isinstance(value, list):
        for inner in value:
            yield from _keys(inner, path)


def _urls(value, path=""):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield from _urls(inner, f"{path}.{key}")
    elif isinstance(value, list):
        for inner in value:
            yield from _urls(inner, path)
    elif isinstance(value, str) and "://" in value:
        yield path


@pytest.mark.parametrize("name", sorted(CONFIG_KEYS))
def test_each_configuration_holds_only_its_reviewed_keys_and_no_endpoint_or_credential(name):
    value = json.loads(REPO.joinpath(name).read_text(encoding="utf-8"))
    keys = {key for key, _ in _keys(value)}
    assert keys == CONFIG_KEYS[name]
    assert not {word for key in keys for word in re.split(r"[_\W]+", key.lower())} & CREDENTIAL_WORDS
    # a link in a configuration is a cited source, read by people, never by the code
    assert all(re.search(r"\.(sources|source|note)(\.|$)", path) for path in _urls(value)), name


def test_every_tracked_configuration_is_in_the_reviewed_list():
    tracked = subprocess.run(["git", "ls-files", "*.json"], cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    configs = {name for name in tracked if name.split("/")[0] in ("config", "targets", "trial", "model_interface", "worldgen")}
    assert configs - {"trial/alerts.json", "worldgen/schema/world.schema.json"} == set(CONFIG_KEYS)


def test_no_credential_file_is_tracked():
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    assert not [name for name in tracked for pattern in SECRET_FILES if fnmatch.fnmatch(name.rsplit("/", 1)[-1], pattern)]
    assert not [name for name in tracked if "/secrets/" in f"/{name}"]


def test_the_only_ci_workflow_is_the_world_drift_check():
    assert sorted(path.name for path in REPO.joinpath(".github", "workflows").iterdir()) == ["world-drift.yml"]
    assert REPO.joinpath("requirements-dev.txt").read_text(encoding="utf-8").split() == ["pytest==9.1.1"]


def test_no_identifier_names_an_account_action_or_regulator_reporting():
    found = set()
    for name, tree in inventory.sources():
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Name):
                names = [node.id]
            elif isinstance(node, ast.Attribute):
                names = [node.attr]
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = [node.name]
            elif isinstance(node, ast.arg):
                names = [node.arg]
            elif isinstance(node, ast.keyword) and node.arg:
                names = [node.arg]
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and re.fullmatch(r"\w+", node.value):
                names = [node.value]
            found |= {(name, identifier) for identifier in names
                      if set(re.split(r"_+", identifier.lower())) & TERMS or identifier.lower() in TERMS}
    for config, keys in CONFIG_KEYS.items():
        found |= {(config, key) for key in keys if set(re.split(r"_+", key.lower())) & TERMS}
    assert found == TERM_HITS
