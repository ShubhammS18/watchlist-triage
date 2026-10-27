"""The upgraded agent for task W2-02, rules first (DEC-W2-02-RULES-FIRST, DEC-W2-02-LAYOUT). Python standard library
only. It imports nothing from the generator (worldgen) or the framings; tests/w2_02_agent checks that.

`recommend.recommend` is the way in. The rubric's rules, written from docs/rubric.md alone (`rules`), decide every
alert that the structured fields settle: one the rubric can never close is escalated, and one it can close with no
snippet is closed, each citing the decisive evidence items, with no model call. Every other alert, whose close turns
on reading a snippet, goes to the baseline agent's model call with its prompt unchanged.

PROMPT is what the harness records for this agent: the prompt text and hash it sends, and the hash of its rule code.
"""
import hashlib
from pathlib import Path

from baseline_agent import prompt

RULES_SHA256 = hashlib.sha256(Path(__file__).with_name("rules.py").read_bytes()).hexdigest()
PROMPT = {"text": prompt.SYSTEM + "\n" + prompt.USER, "sha256": prompt.PROMPT_SHA256, "rule_code_sha256": RULES_SHA256}
