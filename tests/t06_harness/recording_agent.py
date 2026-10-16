"""Test-only: the baseline agent's own code, run in the agent process under a recorder of file-system use
(DEC-T06-NO-FILES). Not shipped, and not used by any run outside the tests.

A test points baseline_agent.recommend.MODULE at this module, in the test process only. In the agent process the
recorder is armed just before the agent's `main` is called and disarmed when it returns. If a file was opened
or a directory was listed in between, the call fails, and the parent reports it as a crashed child.
"""
import sys

from baseline_agent import agent

WATCHED = ("open", "os.listdir", "os.scandir")  # opening a file, and the two ways of listing a directory
armed, seen = [], []


def _note(event, arguments):
    if armed and event in WATCHED:
        seen.append(f"{event} {arguments[0]!r}")


sys.addaudithook(_note)  # an audit hook cannot be removed; unarmed, this one does nothing


def watched(call):
    """Run `call` with the recorder armed. Raise if it opened a file or listed a directory."""
    del seen[:]
    armed.append(True)
    try:
        result = call()
    finally:
        del armed[:]
    if seen:
        raise RuntimeError("the agent used the file system: " + "; ".join(seen))
    return result


def main(model, job):
    return watched(lambda: agent.main(model, job))
