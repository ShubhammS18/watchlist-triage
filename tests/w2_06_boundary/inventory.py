"""Static inventories of the product code for the W2-06 checks: outward capabilities and file writes, read with Python's
ast module, never by running the code. Test-only. Static analysis cannot see code built at run time (importlib with a
computed name, getattr, eval); that limit is stated in docs/w2-06-boundary-checks.md."""
import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACKAGES = ("baseline_agent", "baseline_run", "framings", "harness", "model_interface", "triage_agent", "worldgen", "tools")
NETWORK = {"socket", "ssl", "http", "urllib", "urllib3", "smtplib", "ftplib", "xmlrpc", "telnetlib", "poplib", "imaplib",
           "asyncio", "socketserver", "requests", "httpx", "aiohttp", "websocket", "websockets", "paramiko", "email"}
PROCESSES = {"subprocess", "multiprocessing", "pty", "_posixsubprocess", "ctypes", "concurrent"}
STORES = {"sqlite3", "shelve", "dbm", "pickle", "marshal"}
LAUNCHES = {"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call", "subprocess.check_output",
            "os.system", "os.popen", "os.execv", "os.execve", "os.execvp", "os.execl", "os.spawnv", "os.spawnl",
            "os.posix_spawn", "os.fork"}
WRITES = {"write_text", "write_bytes", "mkdir", "makedirs", "rename", "unlink", "rmdir", "rmtree", "copy2", "copyfile",
          "copytree", "touch", "truncate", "symlink_to", "hardlink_to"}
# names that a string or a list also has: a write only when called on os or shutil
SHARED = {"replace", "remove", "copy", "move", "link", "symlink"}


def sources():
    """(path relative to the repository, parsed tree) for every Python file of the product code."""
    for package in PACKAGES:
        for path in sorted(REPO.joinpath(package).rglob("*.py")):
            yield path.relative_to(REPO).as_posix(), ast.parse(path.read_text(encoding="utf-8"))


def _functions(tree):
    """Each node with the name of the function or class it lies in ("<module>" at the top)."""
    def visit(node, where):
        for child in ast.iter_child_nodes(node):
            inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else where
            yield child, inner
            yield from visit(child, inner)
    yield from visit(tree, "<module>")


def imports(groups):
    """{(file, module)} for every import of a top-level module in `groups`."""
    found = set()
    for name, tree in sources():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found |= {(name, alias.name.split(".")[0]) for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                found.add((name, node.module.split(".")[0]))
    return {(name, module) for name, module in found if module in groups}


def environment():
    """{(file, what is read)} for every read of the environment: os.environ, os.getenv, os.environ.get."""
    found = set()
    for name, tree in sources():
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript) and ast.unparse(node.value) == "os.environ":
                found.add((name, ast.unparse(node.slice)))
            elif isinstance(node, ast.Call) and ast.unparse(node.func) in ("os.environ.get", "os.getenv"):
                found.add((name, ast.unparse(node.args[0])))
            elif isinstance(node, ast.Dict) and any(key is None and ast.unparse(value) == "os.environ"
                                                    for key, value in zip(node.keys, node.values)):
                found.add((name, "the whole environment"))
    return found


def environ_uses():
    """Every place os.environ or os.getenv is named at all, as (file, line): the reads above must account for each."""
    return {(name, node.lineno) for name, tree in sources() for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and ast.unparse(node) in ("os.environ", "os.getenv", "os.putenv")}


def launches():
    """{(file, call, first argument)} for every call that starts a program."""
    found = set()
    for name, tree in sources():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and ast.unparse(node.func) in LAUNCHES:
                first = node.args[0] if node.args else None
                if isinstance(first, ast.List) and first.elts and isinstance(first.elts[0], ast.Constant):
                    shown = first.elts[0].value
                else:
                    shown = ast.unparse(first) if first is not None else ""
                found.add((name, ast.unparse(node.func), shown))
    return found


def writes():
    """{(file, function, call)} for every call that can write, move or remove a file, and every open() for writing."""
    found = set()
    for name, tree in sources():
        for node, where in _functions(tree):
            if not isinstance(node, ast.Call):
                continue
            func = ast.unparse(node.func)
            attr = node.func.attr if isinstance(node.func, ast.Attribute) else func
            if attr == "open" or func == "open":
                mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == "mode"), None)
                mode = mode.value if isinstance(mode, ast.Constant) else ("?" if mode is not None else "r")
                if func == "os.open" or set(str(mode)) & set("wax+?"):
                    found.add((name, where, f"open {mode}"))
            elif attr in WRITES or (attr in SHARED and func.startswith(("os.", "shutil."))):
                found.add((name, where, func))
    return found
