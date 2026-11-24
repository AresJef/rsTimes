"""Package checked versioned HTML, machine evidence, and known legacy routes."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from html import escape
import importlib.metadata
import json
from pathlib import Path
import runpy
import shutil

DOC = Path(__file__).resolve().parents[1]
migration = runpy.run_path(str(DOC / "_tools/legacy_site.py"))
SITE_PREFIX = migration["SITE_PREFIX"]
digest = migration["digest"]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def copy_public_reports(source, destination):
    reports = {}
    for path in sorted(source.rglob("*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("status") != "pass" or report.get("failures"):
            raise ValueError("Only passing current reports belong in the site")
        relative = path.relative_to(source)
        report["identity"]["package_path"] = "verified-interpreter/site-packages/rstimes"
        report.pop("transcript", None)
        public = Path("verification/reports") / relative
        published = destination / public
        write_json(published, report)
        reports[relative.as_posix()] = (
            public.as_posix(), digest(path.read_bytes()), digest(published.read_bytes()),
            report.get("original_report_sha256"),
        )
    return reports


def publish_coverage(exact, gate, reports, identity, receivers, counts, *, preview=False, actions_run=False):
    manifest = json.loads((DOC / "_data/coverage.json").read_text())
    mapped = {row["path"]: row for row in manifest["entries"]}
    rows = []
    for record in gate["records"]:
        row = dict(record)
        proofs = []
        for item in record["evidence"]:
            public, source_hash, published, worker_hash = reports[item["report"]]
            if source_hash != item["report_sha256"]:
                raise ValueError("Page report differs from the checked evidence")
            proof = dict(item, report=public, report_sha256=published)
            if worker_hash:
                origin = "actions-producer"
                if preview:
                    origin = "preview-actions-producer" if actions_run else "historical-actions-producer"
                proof.update(report_origin=origin, ci_report_sha256=source_hash, original_report_sha256=worker_hash)
            elif preview:
                proof.update(report_origin="local-verifier", local_report_sha256=source_hash)
            else:
                raise ValueError("The Actions producer report is missing its worker receipt hash")
            proofs.append(proof)
        row["evidence"] = proofs
        row["examples"] = mapped[row["path"]]["examples"]
        row["profiles"] = mapped[row["path"]]["profiles"]
        rows.append(row)
    if receivers is not None:
        tool = runpy.run_path(str(DOC / "_tools/receiver_evidence.py"))
        cases = tool["bind_cases"](receivers, exact, reports, identity, tool["registrations"]())
        for row in rows:
            row["rendered_example_links"] = [dict(item, href=cases[item["id"]]["example_link"])
                                             for item in row["rendered_example_links"]]
        statuses = tool["add_reader_evidence"](rows, cases)
        write_json(exact / "verification/receivers.json", dict(
            version=gate["version"], scope="One observed registered profile per case",
            reader_status_counts=statuses, cases=cases,
        ))
    if counts is not None:
        if counts["registered_successes"] != gate["passed_case_profiles"]:
            raise ValueError("Registered worker success count differs from verified case/profile coverage")
        write_json(exact / "verification/execution-counts.json", counts)
    write_json(exact / "verification/coverage.json", dict(
        version=gate["version"], entries=len(rows), aliases=gate["aliases"], records=rows,
        scope=gate["verification_scope"], pending_case_profiles=gate["pending_case_profiles"],
        **({"receiver_index": "verification/receivers.json"} if receivers is not None else {}),
    ))
    fields = ("entry", "page", "kind", "origin", "scenarios", "examples", "profiles", "evidence", "pending", "status")
    reader_fields = ("receiver_index", "reader_status", "rendered_example_links", "reader_witnesses",
                     "other_visible_witnesses", "backend_witnesses") if receivers is not None else ()
    with (exact / "verification/coverage.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields + reader_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(
                entry=row["path"], page=row["page"] + ".html#" + row["anchor"],
                kind=row["kind"], origin=row["origin"], scenarios=json.dumps(row["scenarios"]),
                examples=json.dumps(row["examples"]), profiles=json.dumps(row["profiles"]),
                evidence=json.dumps(row["evidence"]), pending=json.dumps(row["pending"]), status=row["status"],
                **{field: json.dumps(row[field]) if isinstance(row[field], list) else row[field]
                   for field in reader_fields},
            ))
    return rows


def write_versions(site, versions, default):
    write_json(site / "versions.json", versions)
    links = "\n".join(
        f'<li><a href="{escape(item["url"], quote=True)}">rsTimes {escape(item["name"])}</a>'
        + (" (default)" if item["version"] == default else "") + "</li>"
        for item in versions
    )
    (site / "versions.html").write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Documentation versions — rsTimes</title>
<style>body{{font:1rem/1.65 system-ui;margin:4rem auto;padding:0 1.25rem;max-width:44rem}}a:focus-visible{{outline:3px solid #176b94;outline-offset:3px}}</style>
</head><body><main>
<h1>Documentation versions</h1>
<nav aria-label="rsTimes documentation versions"><ul>{links}</ul></nav>
</main></body></html>
""", encoding="utf-8")


def write_entry_pages(site, version):
    destination = SITE_PREFIX + version + "/"
    page = migration["redirect_html"](destination, {}, version)
    for directory in (site, site / "latest"):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "index.html").write_text(page, encoding="utf-8")
    routing = site / "_routing"
    routing.mkdir()
    shutil.copyfile(DOC / "_migration/moved.js", routing / "moved.js")
    (site / "404.html").write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/svg+xml" href="{destination}_static/favicon.svg">
<title>Page not found — rsTimes</title>
<style>body{{font:1rem/1.65 system-ui;margin:4rem auto;padding:0 1.25rem;max-width:44rem}}a:focus-visible{{outline:3px solid #176b94;outline-offset:3px}}</style>
</head><body><main>
<h1>Page not found</h1>
<p>Search the rsTimes {version} documentation for the page you need.</p>
<p><a href="{destination}">Documentation home</a> · <a href="{destination}api/index.html">API reference</a> · <a href="{destination}search.html">Search</a></p>
</main></body></html>
""", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--receivers", type=Path)
    parser.add_argument("--counts", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-url")
    parser.add_argument("--run-attempt")
    parser.add_argument("--preview-mode", choices=migration["MODES"])
    args = parser.parse_args()
    gate = json.loads(args.coverage.read_text(encoding="utf-8"))
    target = json.loads((DOC / "target.json").read_text())
    preview = args.preview_mode is not None
    if preview:
        if not gate["candidate_only"] or gate["problems"] or gate["slice"] != "all":
            parser.error("Local rehearsals require a current complete-scope local verification")
    elif gate.get("publication_authorized_by_this_result") is not True or not args.run_url or not args.run_attempt:
        parser.error("Publication requires a passing complete gate and actual workflow context")
    if args.run_url and (args.receivers is None or args.counts is None):
        parser.error("An Actions site requires its receiver observations and worker counts")
    version = target["version"]
    identity = json.loads(args.identity.read_text())
    if version != identity["product_version"] or version != gate["version"]:
        parser.error("Package and website version differ")
    html_record = (args.html / "_build-info.json").read_bytes()
    integrity = runpy.run_path(str(DOC / "_tools/build_integrity.py"))
    if (gate["html_build_sha256"] != digest(html_record)
            or json.loads(html_record)["outputs"] != integrity["html_outputs"](args.html)):
        parser.error("HTML build differs from the checked site")
    if args.output.exists() or any(path.is_symlink() for path in args.html.rglob("*")):
        parser.error("Use a fresh destination and a site without filesystem links")

    mode = args.preview_mode or target["publication_stage"]
    plan = json.loads((DOC / "_data/legacy-pages.json").read_text())
    snapshots = migration["retained_snapshots"](target)
    active_versions = [version, *snapshots]
    default_version = target.get("default_version", version)
    if plan["version"] not in active_versions:
        parser.error("Legacy route map does not target an exact version")
    if default_version not in active_versions:
        parser.error("Invalid documentation default")
    exact = args.output / version
    shutil.copytree(args.html, exact)
    reports = copy_public_reports(args.reports, exact)
    counts = json.loads(args.counts.read_bytes()) if args.counts is not None else None
    rows = publish_coverage(exact, gate, reports, identity, args.receivers, counts,
                            preview=preview, actions_run=bool(args.run_url))

    restored = migration["add_legacy_site"](args.output, plan, mode)
    write_entry_pages(args.output, default_version)
    write_json(args.output / "_meta/legacy-evidence.json", {
        "version": plan["old_version"], "archive_sha256": plan["archive"]["sha256"],
        "files": {name: plan["old_files"][name] for name in plan["retained_evidence"]},
    })
    if mode == "redirect" and plan["version"] == version:
        write_json(exact / "verification/legacy-redirects.json", {
            "from_version": plan["old_version"], "to_version": version, "pages": plan["pages"],
        })
    for retained_version, record in snapshots.items():
        migration["restore_old_files"](args.output, record, "preserve")
        archived_build = json.loads((args.output / retained_version / "_meta/build.json").read_text())
        if (archived_build["product_version"] != retained_version
                or archived_build["source_commit"] != record["source_commit"]
                or archived_build["documentation_commit"] != record["documentation_commit"]
                or archived_build["acceptance"] != "ci" or archived_build["pending_case_profiles"]):
            parser.error("Archived documentation lacks complete installation evidence")
    active_versions.sort(key=lambda item: item != default_version)
    versions = [dict(version=item, name=item, url=SITE_PREFIX + item + "/") for item in active_versions]
    if mode == "preserve":
        old = plan["old_version"]
        versions.append(dict(version=old, name=old, url=SITE_PREFIX + old + "/"))
    write_versions(args.output, versions, default_version)

    build = dict(
        schema=2, product_version=version, source_commit=target["source_commit"],
        documentation_commit=args.commit, workflow_url=args.run_url, workflow_attempt=args.run_attempt,
        prepared_at_utc=datetime.now(timezone.utc).isoformat(), acceptance="preview" if preview else "ci",
        publication_stage=mode, package=identity, public_entries=len(rows),
        verified_case_profiles=gate["passed_case_profiles"], pending_case_profiles=len(gate["pending_case_profiles"]),
        verified_profiles=sorted({item["profile"] for row in rows for item in row["evidence"]}),
        legacy_archive_sha256=plan["archive"]["sha256"], restored_historical_files=len(restored),
        product_functional_conformance_certified=False,
        build_tools={name: importlib.metadata.version(name)
                     for name in ("sphinx", "myst-parser", "pydata-sphinx-theme", "sphinx-autoapi")},
    )
    if snapshots:
        build["default_documentation_version"] = default_version
        build["exact_versions"] = {
            item: SITE_PREFIX + item + "/_meta/build.json" for item in active_versions
        }
    write_json(args.output / "_meta/build.json", build)
    write_json(exact / "_meta/build.json", build)
    (args.output / ".nojekyll").write_text("", encoding="utf-8")
    files = {path.relative_to(args.output).as_posix(): digest(path.read_bytes())
             for path in sorted(args.output.rglob("*")) if path.is_file()}
    write_json(args.output / "_meta/files.json", dict(files=files))
    print(json.dumps(dict(version=version, publication_stage=mode, preview=preview,
                          public_entries=len(rows), files=len(files) + 1)))


if __name__ == "__main__":
    main()
