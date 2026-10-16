"""Test-only: the positive control of the file-system recorder. It is the recorded agent with one thing added:
it opens a file while the recorder is armed. Every call through it must therefore fail."""
from baseline_agent import agent
from tests.t06_harness import recording_agent


def _agent_that_reads_a_file(model, job):
    with open(__file__, encoding="utf-8") as file:
        file.read(1)
    return agent.main(model, job)


def main(model, job):
    return recording_agent.watched(lambda: _agent_that_reads_a_file(model, job))
