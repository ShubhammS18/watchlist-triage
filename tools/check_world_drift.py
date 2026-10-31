"""The world drift check (W2-04; NFR-2, AC-10). The GitHub workflow and tests/w2_04_ci run this same file, from the
repository root, with the same command:

    python3 tools/check_world_drift.py

It regenerates the frozen world from its seed into a temporary folder outside the repository, compares every file
both ways with data/world, and checks the world hash, recomputed from data/world, and the committed MANIFEST.json's
world_hash against the frozen hash below. Standard library only. It prints paths and hashes, never file contents.
Exit codes: 0 no drift, 1 drift, 2 unsupported Python (only 3.12 is supported, so a runner change cannot look like
drift). Any other error ends it with a traceback and a non-zero exit code.
"""
import hashlib
import json
import platform
import sys
import tempfile
from pathlib import Path

PINNED = "b77a6804a52b1d41650e250a31ff64a701b1d315a674a1f1242d93cb6b15c9b0"
SUPPORTED = (3, 12)
REPO = Path(__file__).resolve().parent.parent
WORLD = REPO.joinpath("data", "world")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_tree(folder):
    """{relative path with forward slashes: bytes} for every file under `folder`."""
    folder = Path(folder)
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def world_hash(files):
    """The definition in MANIFEST.json's header_comment, worked out here and not by worldgen."""
    lines = sorted(f"{path}:{sha(data)}" for path, data in files.items() if path != "MANIFEST.json")
    return sha("".join(line + "\n" for line in lines).encode("utf-8"))


def problems(committed, regenerated):
    """Every way the committed world differs from the regenerated one or from the frozen hash; [] if none."""
    found = [f"missing from data/world: {p} (regenerated sha256 {sha(regenerated[p])})"
             for p in sorted(regenerated.keys() - committed.keys())]
    found += [f"not regenerated: {p} (committed sha256 {sha(committed[p])})"
              for p in sorted(committed.keys() - regenerated.keys())]
    found += [f"differs: {p} (committed sha256 {sha(committed[p])}, regenerated sha256 {sha(regenerated[p])})"
              for p in sorted(committed.keys() & regenerated.keys()) if committed[p] != regenerated[p]]
    recomputed = world_hash(committed)
    if recomputed != PINNED:
        found.append(f"world hash of data/world is {recomputed}, not the frozen {PINNED}")
    try:
        field = json.loads(committed["MANIFEST.json"])["world_hash"]
    except (KeyError, TypeError, ValueError):
        field = None
    if field != PINNED:
        found.append(f"MANIFEST.json world_hash is {field!r}, not the frozen {PINNED}")
    return found


def main():
    if sys.version_info[:2] != SUPPORTED:
        version = ".".join(str(part) for part in sys.version_info[:3])
        print(f"unsupported Python {version}: this check supports Python 3.12 only. It did not run; this is not drift.")
        return 2
    sys.path.insert(0, str(REPO))
    from worldgen import load_config
    from worldgen.build import generate, write

    print(f"Python {platform.python_version()} on {platform.platform()}")
    files, _ = generate()
    with tempfile.TemporaryDirectory() as out:
        if Path(out).resolve() == REPO or REPO in Path(out).resolve().parents:
            raise SystemExit(f"the temporary folder {out} is inside the repository; refusing to write there")
        write(files, out)
        regenerated = read_tree(out)
    committed = read_tree(WORLD)
    print(f"seed {load_config()['seed']}: {len(regenerated)} files regenerated, {len(committed)} committed; "
          f"world hash of data/world {world_hash(committed)}")
    found = problems(committed, regenerated)
    for line in found:
        print("DRIFT: " + line)
    print(f"FAILED: {len(found)} problem(s)" if found else f"OK: no drift; world hash {PINNED}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
