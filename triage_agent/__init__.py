"""The upgraded agent for task W2-02, rules first (DEC-W2-02-RULES-FIRST, DEC-W2-02-LAYOUT). Python standard library
only. It imports nothing from the generator (worldgen) or the framings; tests/w2_02_agent checks that.

`recommend.recommend` is the way in. The rubric's rules, written from docs/rubric.md alone (`rules`), decide every
alert that the structured fields settle: one the rubric can never close is escalated, and one it can close with no
snippet is closed, each citing the decisive evidence items, with no model call. For every other alert the rules have
already found that a decisive identifier conflicts and none agrees; whether it closes turns on its snippets. The model
is asked only that, in the guarded child process (`child`, `prompt`): it sees the names and the snippets, quoted as
data, never the decisive fields, and answers LINK, NO_LINK or UNSURE. Only NO_LINK closes.

This file runs in the child process too, so it holds nothing but this text. What the harness records for the agent,
its prompt and the hash of its rule code, is in `record`, which only the parent imports.
"""
