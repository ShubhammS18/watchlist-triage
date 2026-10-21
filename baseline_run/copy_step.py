"""The copy step (DEC-T07-BASELINE-DIR): the scored run output, from a folder outside the repository, into
baseline/, byte for byte, with a SHA-256 list of every copied file. It copies index.json, sets/*.json and every
file of every run folder that index.json lists, and nothing else. It refuses if baseline/ already has content.

The list is baseline/SHA256SUMS in the format `sha256sum -c` reads. After copying, every file is hashed again,
in the source and in baseline/, and both must equal the list.
"""
import shutil
from pathlib import Path

from harness import manifest as records

REPO = records.REPO
LIST = "SHA256SUMS"


def _files(source):
    """The paths to copy, relative to `source`, sorted."""
    index = records.read_index(source)
    if not source.joinpath("index.json").is_file():
        raise ValueError(f"{str(source)!r} has no index.json")
    names = ["index.json"] + sorted(f"sets/{p.name}" for p in source.joinpath("sets").glob("*.json"))
    for run in index["runs"]:
        folder = source.joinpath(run["run_id"])
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError(f"the run folder {run['run_id']} that index.json lists is missing or a link")
        for path in sorted(folder.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"{path.relative_to(source)} is a symbolic link")
            if path.is_file():
                names.append(path.relative_to(source).as_posix())
    return names


def copy_baseline(source, dest=REPO.joinpath("baseline")):
    """Copy, list, verify. Returns {relative path: sha256}."""
    source, dest = Path(source).resolve(), Path(dest)
    if source.is_relative_to(REPO):
        raise ValueError(f"the source must lie outside the repository, not {str(source)!r}")
    if dest.exists() and any(dest.iterdir()):
        raise ValueError(f"{str(dest)!r} already has content; the copy never overwrites")
    names = _files(source)
    for name in names:
        dest.joinpath(name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source.joinpath(name), dest.joinpath(name))
    listed = {name: records.sha256(source.joinpath(name).read_bytes()) for name in names}
    dest.joinpath(LIST).write_text("".join(f"{listed[name]}  {name}\n" for name in names), encoding="utf-8")
    for name in names:  # verify: the copy, and the source again, against the list
        for side in (source, dest):
            if records.sha256(side.joinpath(name).read_bytes()) != listed[name]:
                raise ValueError(f"{name} in {str(side)!r} does not match its listed SHA-256")
    return listed
