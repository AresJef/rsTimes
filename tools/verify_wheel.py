"""Verify this project's actual wheel in isolated provider environments.

Called on the native desktop runner or inside the matching Linux libc image.
This orchestrates existing smoke, regression and documentation commands; it
does not provide another testing engine or compile a replacement release wheel.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import sysconfig
import time
import tomllib
import venv

ROOT = Path(__file__).resolve().parents[1]


def main():
    """Run explicit installed-package lanes and retain every command and timing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("dist"))
    parser.add_argument("--platform-id", required=True)
    parser.add_argument("--python-minor", required=True)
    parser.add_argument("--mode", choices=("pilot", "full", "sdist", "public"), default="full")
    parser.add_argument("--evidence", type=Path, default=Path("evidence"))
    args = parser.parse_args()
    output = args.evidence.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "verification.json").exists():
        parser.error("Choose a new --evidence directory; previous attempts must be retained")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    package_version = project["version"]
    wheels = list(args.directory.resolve().glob("*.whl"))
    assert len(wheels) == 1, wheels
    wheel = wheels[0]
    assert struct.calcsize("P") == 8 and sys.implementation.name == "cpython"
    assert f"{sys.version_info.major}.{sys.version_info.minor}" == args.python_minor
    assert not sysconfig.get_config_var("Py_GIL_DISABLED")
    machine = platform.machine().lower()
    assert machine in ({"aarch64", "arm64"} if args.platform_id.endswith("arm64") else {"amd64", "x86_64"})
    ldd = subprocess.run(["ldd", "--version"], capture_output=True, text=True) if sys.platform == "linux" else None
    if ldd is not None:
        libc_text = ldd.stdout + ldd.stderr
        assert ("musl" in libc_text.lower()) == ("musl" in args.platform_id), libc_text
    receipt = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode, "platform_id": args.platform_id,
        "python": sys.version, "executable": sys.executable,
        "pointer_bits": struct.calcsize("P") * 8, "machine": machine,
        "libc": platform.libc_ver(),
        "ldd": None if ldd is None else ldd.stdout + ldd.stderr,
        "wheel": wheel.name, "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "version": package_version, "commands": [], "status": "RUNNING",
    }

    def save():
        (output / "verification.json").write_text(json.dumps(receipt, indent=2) + "\n")

    def run(name, command):
        log = output / (name + ".log")
        before = time.monotonic()
        print("VERIFY", args.platform_id, args.python_minor, name, flush=True)
        with log.open("w") as stream:
            result = subprocess.run([str(value) for value in command], cwd=ROOT,
                                    stdout=stream, stderr=subprocess.STDOUT, check=False)
        receipt["commands"].append({
            "name": name, "argv": [str(value) for value in command],
            "seconds": time.monotonic() - before, "exit": result.returncode,
            "log": log.name,
        })
        save()
        if result.returncode:
            print(log.read_text(errors="replace")[-16000:], flush=True)
            raise subprocess.CalledProcessError(result.returncode, command)

    def environment(label, requirements):
        folder = ROOT / ".local/wheel-verification" / args.mode / label
        # Only these tool-owned scratch environments are replaced on a new attempt.
        venv.EnvBuilder(with_pip=True, clear=True).create(folder)
        py = folder / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(label + "-pip", [py, "-m", "pip", "install", "--index-url", "https://pypi.org/simple",
                            "--no-cache-dir", "pip==26.2.2"])
        run(label + "-install", [py, "-m", "pip", "install", "--index-url", "https://pypi.org/simple",
                                "--no-cache-dir", "--only-binary=:all:", "-r", requirements, wheel])
        return py

    def inspect(py, label, absent=()):
        run(label + "-dependencies", [py, "-I", "-c",
            "import json,importlib.metadata as m;"
            "v={d.metadata['Name'].lower().replace('_','-'):d.version for d in m.distributions()};"
            f"assert not set({list(absent)!r}).intersection(v),v;"
            "print(json.dumps(v,sort_keys=True))"])
        run(label + "-pip-check", [py, "-m", "pip", "check"])

    def smoke(py, label, *flags):
        run(label + "-smoke", [py, "-I", "-B", ROOT / "tools/wheel_smoke.py",
                              "--expect-version", package_version, *flags])

    def regress(py, label, core=False, public=False):
        if public:
            run(label + "-tests", [py, "-I", "-B", "-m", "pytest", "-q",
                "tests/test_optional_dateutil.py", "tests/test_release_pandas_tail.py",
                "tests/test_astra_relative_live_rules.py", "tests/pddt/test_installation.py",
                "tests/parser/test_from_parserinfo.py",
                "--junitxml", output / (label + "-tests.xml")])
        else:
            run(label + "-tests", [py, "-I", "-B", ROOT / "tools/run_release_tests.py",
                *(["--core"] if core else []), "--junitxml", output / (label + "-tests.xml")])

    try:
        save()
        if args.mode != "sdist":
            core = environment("core", ROOT / "requirements-core-test.txt")
            inspect(core, "core", ("python-dateutil", "pandas", "polars"))
            smoke(core, "core", "--without-dateutil")
            regress(core, "core", core=True)
            run("core-polars-install", [core, "-m", "pip", "install", "--index-url",
                "https://pypi.org/simple", "--no-cache-dir", "--only-binary=:all:", "polars==2.0.0"])
            inspect(core, "core-polars", ("python-dateutil", "pandas"))
            smoke(core, "core-polars", "--without-dateutil", "--with-polars")
            regress(core, "core-polars", core=True)

        full = environment("pd3", ROOT / "requirements-test.txt")
        inspect(full, "pd3")
        smoke(full, "pd3", "--with-dateutil", "--with-pandas", "--with-polars")
        regress(full, "pd3", public=args.mode == "public")
        if args.mode == "full":
            if args.python_minor != "3.15" and args.platform_id != "windows-arm64":
                compatible = environment("pd2", ROOT / "requirements-pandas2-test.txt")
                inspect(compatible, "pd2")
                smoke(compatible, "pd2", "--with-dateutil", "--with-pandas", "--with-polars")
                regress(compatible, "pd2")
            if args.python_minor == "3.15":
                latest = environment("latest", ROOT / "requirements-latest-test.txt")
                inspect(latest, "latest")
                smoke(latest, "latest", "--with-dateutil", "--with-pandas", "--with-polars")
                regress(latest, "latest")
            if args.platform_id == "macos-arm64" and args.python_minor == "3.13":
                run("typing-install", [full, "-m", "pip", "install", "--index-url",
                    "https://pypi.org/simple", "--no-cache-dir", "-r", ROOT / "requirements-dev.txt"])
                run("public-docs", [full, "-I", "-B", ROOT / "tools/check_public_docs.py"])
                run("public-typing", [full, "-I", "-B", ROOT / "tools/check_typing.py"])
                run("demo-manifest", [full, ROOT / "tools/distribution_manifest.py",
                    "--directory", args.directory.resolve(), "--wheels", "1",
                    "--sdists", str(len(list(args.directory.glob("*.tar.gz")))),
                    "--output", output / "demo-distributions.json"])
                # Explicit CI-only runtime selection; never modify caller processes.
                (ROOT / "demo/runtime.json").write_text(json.dumps({
                    "environment": str(full.parent.parent.relative_to(ROOT)),
                    "version": package_version,
                    "release_manifest": str((output / "demo-distributions.json").relative_to(ROOT)),
                    "selection": "ci_installed_wheel",
                }))
                run("pddt-demo", [full, "-I", "-B", ROOT / "demo/pddt.py"])
        receipt["status"] = "PASS"
    except BaseException:
        receipt["status"] = "FAIL"
        raise
    finally:
        receipt["completed_at"] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == "__main__":
    main()
