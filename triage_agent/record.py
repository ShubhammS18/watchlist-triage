"""What the harness records for the upgraded agent (DEC-W2-02-LAYOUT): the prompt text and hash it sends, and the hash
of its rule code: the rules, the parent's verdicts and citations, the child's reading of the answer and the building
of the prompt. Parent only."""
import hashlib
from pathlib import Path

from .prompt import PROMPT_SHA256, SYSTEM, USER

RULE_CODE = ("rules.py", "recommend.py", "child.py", "prompt.py")


def rule_code_sha256(folder=Path(__file__).parent):
    digest = hashlib.sha256()
    for name in RULE_CODE:
        digest.update(name.encode("utf-8") + b"\0" + folder.joinpath(name).read_bytes() + b"\0")
    return digest.hexdigest()


PROMPT = {"text": SYSTEM + "\n" + USER, "sha256": PROMPT_SHA256, "rule_code_sha256": rule_code_sha256()}
