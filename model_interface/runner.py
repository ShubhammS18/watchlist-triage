"""Parent side of the agent process. The parent owns the model; the child is given a pipe to ask for it.

The pipe carries one JSON message per line:
    parent -> child   {"payload": ...}                   once, at the start
    child -> parent   {"call": {"messages", "settings"}} each time the child wants the model
    parent -> child   {"result": {...}} or {"error": {"type", "message"}}
    child -> parent   {"done": ...} or {"failed": traceback text}, which ends the run

Each model call runs in a worker thread, so the wall-clock limit also ends a run whose model call never returns.
"""
import queue
import subprocess
import sys
import threading
from dataclasses import asdict
from pathlib import Path

from . import ModelError, receive, request_from, send

CHILD = Path(__file__).with_name("child.py")


class ChildError(RuntimeError):
    """The agent process crashed, stopped early or sent something that is not part of the protocol."""


class ChildTimeout(ChildError):
    """The agent process ran past the wall-clock limit and was killed."""


def _call(model, request):
    try:
        return {"result": asdict(model(request))}
    except ModelError as error:
        return {"error": {"type": type(error).__name__, "message": str(error)}}


def _answer(model, call, inbox):
    try:
        request = request_from(call)
    except (KeyError, TypeError, ValueError) as error:
        raise ChildError(f"the agent process sent a request of the wrong shape: {error}") from error

    def work():
        try:
            inbox.put((_call(model, request), None))
        except BaseException as error:  # a fault in the model itself goes back to the caller of run_child
            inbox.put((None, error))

    # A daemon thread: if the limit runs out first it is abandoned, and lingers until its call returns.
    threading.Thread(target=work, daemon=True).start()
    answer, error = inbox.get()  # the timer puts (None, None) here when the limit runs out
    if error is not None:
        raise error
    if answer is None:
        raise ChildError("the limit ran out during a model call")
    return answer


def _talk(process, payload, model, inbox):
    send(process.stdin, {"payload": payload})
    while True:
        message = receive(process.stdout)
        if not isinstance(message, dict):
            raise ChildError("the agent process stopped without finishing")
        if "done" in message:
            return message["done"]
        if "failed" in message:
            raise ChildError(f"the agent process failed:\n{message['failed']}")
        if "call" not in message:
            raise ChildError(f"the agent process sent an unknown message with keys {sorted(message)}")
        send(process.stdin, _answer(model, message["call"], inbox))


def run_child(module, payload, model, limit_s=60):
    """Run `module.main(model, payload)` in a child process with the network guard, and return what it returns.

    `payload` and the return value must be JSON values. The child gets an empty environment, so the parent's
    environment variables are not passed to it. The guard stops ordinary, accidental and prompt-led network use,
    not code written to defeat it.

    The whole run, model calls included, may take `limit_s` seconds by the wall clock. After that the child is
    killed and ChildTimeout is raised, even if a model call has not returned. This is a safety net against a run
    that never ends, not a timeout policy.
    """
    process = subprocess.Popen(
        [sys.executable, "-I", str(CHILD), module],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, env={}, text=True, encoding="utf-8")
    expired = threading.Event()
    inbox = queue.SimpleQueue()

    def expire():
        expired.set()
        process.kill()  # the blocked read or write in _talk then ends at once
        inbox.put((None, None))  # and so does a wait for a model call

    timer = threading.Timer(limit_s, expire)
    timer.start()
    try:
        return _talk(process, payload, model, inbox)
    except (OSError, ValueError, ChildError) as error:
        if expired.is_set():
            raise ChildTimeout(f"the agent process was killed after {limit_s} seconds") from None
        if isinstance(error, ChildError):
            raise
        raise ChildError(f"the pipe to the agent process broke: {error}") from error
    finally:
        timer.cancel()
        process.kill()
        process.wait()
        for stream in (process.stdin, process.stdout):
            try:
                stream.close()
            except OSError:  # unsent bytes for a child that is already gone
                pass
