"""Verify the frozen stage A archive and compare an artifact-only reupload."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import zipfile


STAGE_A = "985e9505acefbb4fc24d96d40091b7367ad9e555"
ZIP_SHA = "bf215a5cfb6bc6e6e243e7b2689dbfa5d99b23969038344d01a1b067057bc046"
TAR_SHA = "41fb8d512e7457eb1136723efd9f17c6e7c5ef95a9e2d05cf6bb33eebcfdd2cb"


def unpack(tar_bytes, destination=None):
    files = {}
    with tarfile.open(fileobj=BytesIO(tar_bytes)) as archive:
        for member in archive:
            path = PurePosixPath(member.name.removeprefix("./"))
            assert not path.is_absolute() and ".." not in path.parts, member.name
            if member.isdir():
                continue
            assert member.isfile() and path.parts and str(path) not in files, member.name
            data = archive.extractfile(member).read()
            files[str(path)] = sha256(data).hexdigest()
            if destination is not None:
                local = destination.joinpath(*path.parts)
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(data)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("site", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuploaded-tar", type=Path)
    args = parser.parse_args()

    zip_bytes = args.original.read_bytes()
    assert sha256(zip_bytes).hexdigest() == ZIP_SHA
    with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
        assert archive.namelist() == ["artifact.tar"]
        tar_bytes = archive.read("artifact.tar")
    assert sha256(tar_bytes).hexdigest() == TAR_SHA
    if args.reuploaded_tar is None:
        args.site.mkdir(parents=True)
        files = unpack(tar_bytes, args.site)
    else:
        files = unpack(tar_bytes)
    manifest_file = "_meta/files.json"
    manifest = json.loads((args.site / manifest_file).read_text(encoding="utf-8"))["files"]
    assert len(manifest) == 1429 and files == {**manifest, manifest_file: files[manifest_file]}
    metadata = json.loads((args.site / "_meta/build.json").read_text(encoding="utf-8"))
    assert metadata["documentation_commit"] == STAGE_A
    assert metadata["default_documentation_version"] == "1.0.0"
    redirects = {
        "index.html": "/rsTimes/1.0.0/",
        "latest/index.html": "/rsTimes/1.0.0/",
    }
    for leaf, target in redirects.items():
        assert f'id="documentation-destination" href="{target}"' in (args.site / leaf).read_text()
    for version in ("1.0.0", "1.1.0"):
        assert f"{version}/index.html" in manifest
        exact = json.loads((args.site / version / "_meta/build.json").read_text(encoding="utf-8"))
        assert exact["product_version"] == version
    legacy_page = "0.2.0b3/api/inherited-pldt-reference.html"
    source = (args.site / legacy_page).read_text()
    fragments = json.loads(re.search(r'id="documentation-fragments" type="application/json">(.*?)</script>', source).group(1))
    old_targets = {
        key: "/rsTimes/1.0.0/api/inherited-pldt-reference.html#" + key
        for key in ("rstimes.Pldt.scatter", "rstimes.Pldt.diff")
    }
    for fragment, target in old_targets.items():
        assert fragments[fragment] == target
        assert f'id="{fragment}"' in (args.site / target.split("#")[0].removeprefix("/rsTimes/")).read_text()

    result = {
        "original_run": 44928578308,
        "original_artifact_id": 14716258539,
        "original_commit": STAGE_A,
        "original_zip_sha256": ZIP_SHA,
        "original_tar_sha256": TAR_SHA,
        "manifest_rows": len(manifest),
        "manifest_sha256": files[manifest_file],
        "original_members": len(files),
        "default": metadata["default_documentation_version"],
        "redirects": redirects,
        "exact": ["1.0.0", "1.1.0"],
        "legacy_page": legacy_page,
        "legacy_targets": old_targets,
    }
    if args.reuploaded_tar is not None:
        output = args.reuploaded_tar.read_bytes()
        after = unpack(output)
        assert after.keys() == files.keys(), {"missing": sorted(files.keys() - after.keys()),
                                              "extra": sorted(after.keys() - files.keys())}
        differences = [name for name in files if files[name] != after[name]]
        assert not differences, differences
        result.update(reuploaded_tar_sha256=sha256(output).hexdigest(), compared_members=len(after),
                      differences=differences, per_file_sha256=after)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Verified {len(files)} site files")


if __name__ == "__main__":
    main()
