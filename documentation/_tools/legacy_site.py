"""Restore the verified old site or replace its HTML with checked redirects."""
from __future__ import annotations

import hashlib
from html import escape
import json
from pathlib import Path, PurePosixPath
import tarfile

DOC = Path(__file__).resolve().parents[1]
SITE_PREFIX = "/rsTimes/"
SITE_ORIGIN = "https://aresjef.github.io"
MODES = ("preserve", "redirect")
REDIRECT_SCRIPT = SITE_PREFIX + "_routing/moved.js"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def redirect_html(target, fragments, version):
    path = escape(target, quote=True)
    canonical = escape(SITE_ORIGIN + target.split("#", 1)[0], quote=True)
    routes = json.dumps(fragments, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<link rel="canonical" href="{canonical}">
<title>rsTimes documentation moved</title>
</head>
<body><main>
<h1>rsTimes documentation moved</h1>
<p><a id="documentation-destination" href="{path}">Read the rsTimes {version} documentation</a></p>
</main>
<script id="documentation-fragments" type="application/json">{routes}</script>
<script src="{REDIRECT_SCRIPT}"></script>
</body>
</html>
"""


def restore_old_files(site, plan, mode):
    if mode not in MODES:
        raise ValueError("Unknown Pages migration mode")
    version_prefix = plan["old_version"] + "/"
    file = DOC / "_migration" / plan["archive"]["name"]
    if file.stat().st_size != plan["archive"]["size"] or digest(file.read_bytes()) != plan["archive"]["sha256"]:
        raise ValueError("Archived public site differs from the recorded snapshot")
    expected = plan["old_files"]
    selected = ({path for path in expected if path.startswith(version_prefix)}
                if mode == "preserve" else set(plan["retained_evidence"]))
    seen = set()
    with tarfile.open(file, "r:gz") as archived:
        for member in archived:
            name = member.name
            relative = PurePosixPath(name)
            if (name not in expected or name in seen or not member.isfile()
                    or relative.is_absolute() or ".." in relative.parts
                    or relative.as_posix() != name or "\\" in name):
                raise ValueError("Unexpected member in the archived public site: " + name)
            with archived.extractfile(member) as stream:
                content = stream.read()
            if digest(content) != expected[name]:
                raise ValueError("Archived public file digest mismatch: " + name)
            if name in selected:
                destination = site / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
            seen.add(name)
    if seen != expected.keys():
        raise ValueError("Archived site file list is incomplete")
    return sorted(selected)


def add_legacy_site(site, plan, mode):
    restored = restore_old_files(site, plan, mode)
    if mode == "redirect":
        for name, route in plan["pages"].items():
            destination = site / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                redirect_html(route["target"], route["fragments"], plan["version"]), encoding="utf-8"
            )
    return restored
