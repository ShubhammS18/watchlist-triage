"""Shared fixtures of the W2-02 tests. The practice world is rebuilt from its recorded seed in a temporary folder, so
the tests do not depend on a copy kept anywhere; its labels may be read (DEC-W2-02-PRACTICE-WORLD). The frozen
world's labels are never read here."""
import pytest

from harness import manifest as records

REPO = records.REPO
LOG = REPO.joinpath("docs", "w2-02-attempts.md")
PRACTICE_SEED = 20261027
PRACTICE_HASH = "e2cbcb692714c1d334de63a0f6db184d51466029ac91cabdc60b89507026ecb8"


@pytest.fixture(scope="session")
def practice_world(tmp_path_factory):
    from worldgen.build import generate, write
    files, _ = generate(PRACTICE_SEED)
    folder = tmp_path_factory.mktemp("practice-world")
    write(files, folder)
    return folder
