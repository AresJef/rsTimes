"""Check release-source hashes independently of the documentation branch."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

DOC = Path(__file__).resolve().parents[1]


def sha(content):
    return hashlib.sha256(content).hexdigest()


def git(directory, *args):
    return subprocess.check_output(["git", "--no-optional-locks", "-C", str(directory), *args])


def check_tag(directory, binding):
    tag = binding["source_tag"]
    commit = git(directory, "rev-parse", f"{tag}^{{commit}}").decode().strip()
    if commit != binding["source_commit"]:
        raise ValueError(f"{tag} points to {commit}; expected {binding['source_commit']}")
    checked = {}
    for name in binding["source_files"]:
        checked[name] = sha(git(directory, "show", f"{commit}:{name}"))
    return checked


def check_sdist(path, binding):
    digest = sha(path.read_bytes())
    if path.name != binding["source_archive"] or digest != binding["source_archive_sha256"]:
        raise ValueError("Source archive name or SHA-256 differs from the published release")
    checked = {}
    prefix = path.name.removesuffix(".tar.gz")
    with tarfile.open(path, mode="r:gz") as archive:
        for name in binding["source_files"]:
            member = archive.getmember(f"{prefix}/{name}")
            if not member.isfile():
                raise ValueError(f"Expected a regular archive file: {name}")
            with archive.extractfile(member) as stream:
                checked[name] = sha(stream.read())
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--tag-repository", type=Path)
    source.add_argument("--sdist", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binding = json.loads((DOC / "_data/source-checkout.json").read_text())
    if args.tag_repository:
        checked = check_tag(args.tag_repository, binding)
    else:
        checked = check_sdist(args.sdist, binding)
    expected = binding["source_files"]
    unequal = sorted(name for name in checked.keys() | expected.keys() if checked.get(name) != expected.get(name))
    result = {
        "status": "fail" if unequal else "pass",
        "source_tag": binding["source_tag"], "source_commit": binding["source_commit"],
        "checked_from": "tag" if args.tag_repository else "sdist",
        "checked_files": len(checked), "changed_files": unequal,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    return int(bool(unequal))


if __name__ == "__main__":
    raise SystemExit(main())
