"""Prepare the exact installed releases used by the packaged Chrome routes."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys


DOC = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--candidate-distributions", type=Path)
    args = parser.parse_args()
    build = json.loads((args.site / "_meta/build.json").read_bytes())
    current = build["product_version"]
    work = args.work.resolve()
    work.mkdir(parents=True)
    runtimes = {}
    for version in build.get("exact_versions", {current: True}):
        exact = json.loads((args.site / version / "_meta/build.json").read_bytes())
        assert exact["product_version"] == version
        identities = exact["package"]["profile_identities"]
        wheels = work / version / "wheels"
        sources = ()
        if version == current and args.candidate_distributions is not None:
            sources = ("--no-index", "--find-links", str(args.candidate_distributions.resolve()))
        subprocess.run([sys.executable, "-m", "pip", "download", "--disable-pip-version-check",
                        "--only-binary=:all:", "--no-deps", "--dest", str(wheels), *sources,
                        "rsTimes==" + version], check=True)
        (wheel,) = wheels.glob("*.whl")
        digest = sha256(wheel.read_bytes()).hexdigest()
        runtimes[version] = {}
        for profile in ("full", "core") if version == current else ("full",):
            identity = identities[profile]
            if wheel.name != identity["wheel_filename"] or digest != identity["wheel_sha256"]:
                raise ValueError(f"Reader wheel differs from the verified site identity: {version}/{profile}")
            (native_sha,) = identity["native"].values()
            env = work / version / profile
            subprocess.run([sys.executable, "-m", "venv", str(env)], check=True)
            python = env / "bin/python"
            subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                            "-r", str(DOC / "requirements" / (profile + ".txt"))], check=True)
            subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "--no-deps",
                            str(wheel)], check=True)
            runtimes[version][profile] = {"python": str(python), "wheel": str(wheel),
                                          "wheel_sha256": digest, "native_sha256": native_sha}
    args.output.write_text(json.dumps(runtimes, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
