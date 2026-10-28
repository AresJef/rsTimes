"""Select a demo environment and verify its actual installed release once."""

from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys


def use_demo_runtime(script: str, *, direct: bool) -> None:
    """Use a named demo's environment without importing comparison libraries.

    Direct scripts may restart under the explicitly configured interpreter.
    Imports only validate; they never replace the caller's process.
    """
    entry = Path(script).resolve()
    root = entry.parents[1]
    config = json.loads((entry.parent / "runtime.json").read_text(encoding="utf-8"))
    selected = config.get("environments", {}).get(entry.stem, config["environment"])
    environment = (root / selected).resolve()
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        raise RuntimeError(f"Demo environment is missing: {python}. See demo/README.md.")
    different = Path(sys.prefix).resolve() != environment
    if direct and (different or not sys.flags.isolated):
        os.execv(str(python), [str(python), "-I", str(entry), *sys.argv[1:]])
    if different:
        raise RuntimeError(f"Import {entry.name} using {python}, or execute it directly.")

    # A launcher may start on Python3.10; read TOML after selecting the runtime.
    from tomllib import load

    with (root / "pyproject.toml").open("rb") as source:
        project_version = load(source)["project"]["version"]
    installed = version("rstimes")
    if config["version"] != project_version or installed != config["version"]:
        raise RuntimeError(
            f"Demo version mismatch: project={project_version}, "
            f"configured={config['version']}, installed={installed}."
        )
    import rstimes._native as native

    manifest = json.loads((root / config["release_manifest"]).read_text(encoding="utf-8"))
    if manifest["version"] != installed:
        raise RuntimeError("Demo manifest version does not match the installed package.")
    binary = Path(native.__file__).resolve()
    expected = {wheel["native_sha256"] for wheel in manifest["wheels"]}
    if not binary.is_relative_to(environment) or sha256(binary.read_bytes()).hexdigest() not in expected:
        raise RuntimeError("Demo native differs from the verified distribution manifest.")
