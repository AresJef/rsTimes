"""Join the canonical API, authored scenarios, current HTML and actual wheel runs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import runpy
from urllib.parse import unquote, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = re.compile(r"^\x60{3}\{doctest\} ([^\n]+)\n(.*?)^\x60{3}[ \t]*$", re.M | re.S)
SCAN = runpy.run_path(str(ROOT / "_tools/example_blocks.py"))["scan_examples"]
MAPPINGS = runpy.run_path(str(ROOT / "_tools/sync_coverage.py"))


class APISections(HTMLParser):
    """Read links attached to a signature or to a hand-written reference row."""

    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = {}
        self.sections = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in {"dl", "tr"}:
            self.sections.append((tag, []))
        if anchor := attributes.get("id"):
            self.ids.add(anchor)
            if self.sections:
                self.links[anchor] = self.sections[-1][1]
        if tag == "a" and self.sections and attributes.get("href"):
            self.sections[-1][1].append(attributes["href"])

    def handle_endtag(self, tag):
        if self.sections and self.sections[-1][0] == tag:
            self.sections.pop()


def linked_locations(page, links):
    """Resolve internal paths relative to the page that contains the API."""
    locations = []
    for href in links:
        if urlsplit(href).netloc or urlsplit(href).scheme:
            continue
        target = urlsplit(urljoin("/" + page, href))
        location = (unquote(target.path.lstrip("/")), unquote(target.fragment))
        if location[0].endswith(".html") and location != (page, "") and location not in locations:
            locations.append(location)
    return locations


def sha(content):
    return hashlib.sha256(content).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def release_identity_matches(reference, release):
    wheel = release["files"].get(reference["wheel_filename"], {})
    if wheel.get("packagetype") != "bdist_wheel" or reference["wheel_sha256"] != wheel["sha256"]:
        return False
    native = wheel["native"].removeprefix("rstimes/")
    if reference["product_version"] != release["version"] or reference["source_commit"] != release["source_commit"]:
        return False
    expected_native = {native: wheel["native_sha256"]}
    return reference["native"] == expected_native and reference["payload"] == release["common_package_files"] | expected_native


def report_matches_profile(report, identity, profiles, verifier_sha):
    actual = report["identity"]
    reference = identity.get("profile_identities", {}).get(report["profile"], identity)
    spec = profiles.get(report["profile"])
    if not spec:
        return False
    dependencies = {name: value for name, value in spec["dependencies"].items() if value is not None}
    return (actual.get("import_location_verified") is True
            and actual["version"] == reference["product_version"]
            and all(actual[k] == reference[k] for k in ("native", "stubs", "payload"))
            and actual["python_minor"] == spec["python_minor"]
            and actual.get("gil_enabled") is actual.get("gil_after_page") is spec["gil_enabled"]
            and actual["dependencies"] == dependencies
            and report.get("verifier_sha256") == verifier_sha)


def authored_cases(examples, rendered_pages):
    by_page = defaultdict(list)
    for example in examples.values():
        by_page[example["page"]].append(example)
    blocks, errors = {}, []
    for page, registrations in by_page.items():
        source = ROOT / page
        visible = {example.name: example for example in SCAN(source.read_text(encoding="utf-8"), source.suffix)}
        contract_file = ROOT / "_checks" / Path(page).with_suffix(".txt")
        contract_text = contract_file.read_text(encoding="utf-8") if contract_file.is_file() else ""
        contracts = dict(CONTRACT.findall(contract_text))
        rendered = rendered_pages.get(Path(page).with_suffix(".html").as_posix(), {})
        actual_html = {item["id"]: item for item in rendered.get("examples", [])}
        for registration in registrations:
            name = registration["id"]
            format = registration.get("format")
            if format == "python" and name in visible:
                example = visible[name]
                hashes = dict(sha256=sha(example.code.encode()), output_sha256=sha(example.output.encode()))
                observed = actual_html.get(name, {})
                if any(observed.get(key) != value for key, value in hashes.items()):
                    errors.append(f"Current rendered code or expected output missing: {name}")
                hashes["checks_sha256"] = sha("\n".join(registration["checks"]).encode())
                hashes["expected_output"] = example.output
            elif format == "contract" and name in contracts:
                body = contracts[name]
                hashes = {"sha256": sha(body.encode())}
                marker = ">>> # coverage: "
                if body.startswith(marker):
                    claim = json.loads(body.splitlines()[0][len(marker):])
                    for field in ("covers", "scenarios"):
                        if set(claim[field]) != set(registration[field]):
                            errors.append(
                                f"Executed witness ownership differs for {name}/{field}: "
                                f"authored {claim[field]}, registered {registration[field]}")
            else:
                errors.append(f"Registered case missing from its actual source: {name}")
                continue
            blocks[name] = {"format": format, **hashes}
        if set(visible) | set(contracts) != {example["id"] for example in registrations}:
            errors.append(f"Source registrations differ: {page}")
    return blocks, errors


def matching_reports(root, examples, blocks, identity, profiles, verifier_sha):
    found = defaultdict(list)
    page_hashes = {page: sha((ROOT / page).read_bytes()) for page in {case["page"] for case in examples.values()}}
    for path in sorted(root.rglob("*.json")):
        report = read_json(path)
        if report["page_sha256"] != page_hashes.get(report["page"]):
            continue
        if not report_matches_profile(report, identity, profiles, verifier_sha):
            continue
        profile = report["profile"]
        reference = identity.get("profile_identities", {}).get(profile, identity)
        for group in report["groups"]:
            example = examples.get(group["id"])
            if not example or example["page"] != report["page"] or profile not in example["profiles"]:
                continue
            block = blocks.get(group["id"])
            if not block or any(group.get(key) != value for key, value in block.items()):
                continue
            ok = (report["status"] == group["status"] == "pass" and not report["failures"]
                  and group["assertions"] > 0)
            if block["format"] == "python":
                actual = group["actual"]
                state = profiles[profile]["gil_enabled"]
                error_type = (actual["exception"] or {}).get("type")
                ok = (ok and actual["gil_before"] is actual["gil_after"] is state
                      and actual["output"] == block["expected_output"]
                      and error_type == example.get("raises")
                      and not (actual["checks_error"] or actual["stderr"]))
            found[(group["id"], profile)].append({
                "verified": ok, "example": group["id"], "profile": profile,
                "report": path.relative_to(root).as_posix(), "page_sha256": report["page_sha256"],
                "report_sha256": sha(path.read_bytes()), "verifier_sha256": verifier_sha,
                "wheel": reference["wheel_filename"], "wheel_sha256": reference["wheel_sha256"],
                "native": report["identity"]["native"], "python": report["identity"]["python"],
                "dependencies": report["identity"]["dependencies"],
                "gil_before": report["identity"]["gil_enabled"], "gil_after": report["identity"]["gil_after_page"],
                **{key: value for key, value in block.items() if key != "expected_output"},
            })
    return found


def build_problems(html, identity, target):
    integrity = runpy.run_path(str(ROOT / "_tools/build_integrity.py"))
    build_file = html / "_build-info.json"
    if not build_file.is_file():
        return ["Current HTML build manifest missing."]
    build = read_json(build_file)
    problems = []
    if not build["complete"] or build["source_inputs"] != integrity["source_inputs"](ROOT):
        problems.append("HTML build does not match current documentation inputs.")
    if build["outputs"] != integrity["html_outputs"](html):
        problems.append("HTML output hashes differ from the completed build.")
    if build["website_version"] != target["version"]:
        problems.append("HTML build records a different release version.")
    if any(build["installed_package"].get(key) != identity[key]
           for key in ("product_version", "native", "stubs", "payload")):
        problems.append("Rendered API extraction differs from the verified installed wheel.")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--html-dir", type=Path, required=True)
    parser.add_argument("--rendered-examples", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--slice", choices=("all", "core"), default="all")
    parser.add_argument("--allow-candidate", action="store_true")
    parser.add_argument("--defer-profile", action="append", default=[],
                        help="Local reporting only. Report the named missing executions as pending.")
    args = parser.parse_args()
    inventory = read_json(ROOT / "_data/public-api.json")
    table = read_json(ROOT / "_data/coverage.json")
    release = read_json(ROOT / "_data/release.json")
    target = read_json(ROOT / "target.json")
    identity = read_json(args.identity)
    profiles = read_json(ROOT / "_data/profiles.json")["profiles"]
    declared = read_json(ROOT / "_data/examples.json")["examples"]
    reader_targets = read_json(ROOT / "_data/reader-targets.json")
    rendered = read_json(args.rendered_examples)
    if args.defer_profile and (not args.allow_candidate or not set(args.defer_profile) <= profiles.keys()):
        parser.error("Deferrals require local reporting and declared profiles.")

    problems = build_problems(args.html_dir, identity, target)
    if rendered["status"] != "pass":
        problems.append("The rendered example verification did not pass.")
    actual_html = {p.relative_to(args.html_dir).as_posix() for p in args.html_dir.rglob("*.html")}
    if args.slice == "all" and set(rendered["pages"]) != actual_html:
        problems.append("Rendered example proof does not cover all HTML pages.")
    for name, record in rendered["pages"].items():
        page = args.html_dir / name
        if not page.is_file() or sha(page.read_bytes()) != record.get("html_sha256"):
            problems.append(f"Rendered example proof is stale: {name}")
    canonical = {entry["path"] for entry in inventory["entries"]}
    paths = [entry["path"] for entry in table["entries"]]
    if canonical != set(paths) or len(paths) != len(canonical) or table["aliases"] != inventory["aliases"]:
        problems.append("Coverage paths and aliases must match the canonical public inventory.")
    if set(identity["public_api_paths"]) != canonical or len(identity["public_api_paths"]) != len(canonical):
        problems.append("Installed-wheel identity records a different public inventory.")
    references = [identity, *identity.get("profile_identities", {}).values()]
    if any(not release_identity_matches(reference, release) or reference["stubs"] != inventory["stubs"]
           for reference in references):
        problems.append("Wheel identities differ from the pinned release.")
    if target["version"] != inventory["version"] or release["version"] != target["version"]:
        problems.append("Target, public inventory and release versions differ.")
    if not args.allow_candidate and (target["status"] != "released" or not target["publication_allowed"]):
        problems.append("The configured site release is not enabled for publication.")

    examples = {example["id"]: example for example in declared}
    if len(examples) != len(declared):
        problems.append("Example IDs must be globally unique.")
    for example in declared:
        if (not set(example["covers"]) <= canonical or not example["profiles"]
                or not set(example["profiles"]) <= profiles.keys() or not example.get("reviewed")):
            problems.append(f"Invalid case registration: {example['id']}")
    if not set(reader_targets) <= canonical:
        problems.append("Reader targets must refer to canonical public entries.")
    reverse = MAPPINGS["examples_by_entry"](declared)
    visible_locations = {
        (Path(case["page"]).with_suffix(".html").as_posix(), case["id"]): case
        for case in declared if case["format"] == "python"
    }
    selected = [entry for entry in table["entries"] if args.slice == "all"
                or entry["owner"] in ("rstimes.Delta", "rstimes.Configs", "rstimes")
                or entry["owner"].startswith("rstimes.errors.")]
    selected_ids = {identifier for entry in selected for identifier in entry["examples"]}
    if args.slice == "all":
        selected_ids.update(examples)
    blocks, invalid = authored_cases(examples, rendered["pages"])
    problems.extend(invalid)
    verifier_sha = sha((ROOT / "_tools/verify_examples.py").read_bytes())
    runs = matching_reports(args.reports, examples, blocks, identity, profiles, verifier_sha)
    checks, pending = {}, set()
    for name in sorted(selected_ids & examples.keys()):
        for profile in examples[name]["profiles"]:
            options = runs.get((name, profile), [])
            if options and all(proof["verified"] for proof in options):
                checks[(name, profile)] = options[-1]
            elif not options and profile in args.defer_profile:
                pending.add((name, profile))
            else:
                problems.append(f"Current passing execution missing or contradicted: {name}/{profile}")

    anchors, records = {}, []
    for entry in selected:
        path = entry["path"]
        invalid, evidence, pending_cases = [], [], []
        if not entry["description_reviewed"] or not entry["examples"]:
            invalid.append("Description or example mapping incomplete.")
        page_name = entry["page"] + ".html"
        rendered_page = args.html_dir / page_name
        if rendered_page not in anchors:
            dom = APISections()
            if rendered_page.is_file():
                dom.feed(rendered_page.read_text(encoding="utf-8"))
            anchors[rendered_page] = dom
        dom = anchors[rendered_page]
        if entry["anchor"] not in dom.ids:
            invalid.append("Rendered public anchor missing.")
        for field, expected in MAPPINGS["derived_fields"](entry, reverse[path]).items():
            actual = entry[field]
            if actual != expected:
                invalid.append(f"Stale {field}: missing {sorted(set(expected) - set(actual))}, "
                               f"extra {sorted(set(actual) - set(expected))}, or noncanonical list.")
        locations = linked_locations(page_name, dom.links.get(entry["anchor"], []))
        linked_cases = [visible_locations[location] for location in locations if location in visible_locations]
        if path in reader_targets:
            preferred = reader_targets[path]
            expected = examples.get(preferred, {})
            if (preferred not in entry["examples"] or expected.get("format") != "python"
                    or path not in expected.get("covers", [])):
                invalid.append(f"Reader target is not a visible example registered for this entry: {preferred}.")
            actual = [case["id"] for case in linked_cases]
            if preferred not in actual or any(path not in case["covers"] for case in linked_cases):
                invalid.append(f"Wrong rendered reader link: expected {preferred}, saw {actual or locations}.")
        for name in entry["examples"]:
            example = examples.get(name)
            if not example or path not in example["covers"]:
                invalid.append(f"Invalid mapping: {name}")
                continue
            for profile in example["profiles"]:
                proof = checks.get((name, profile))
                details = dict(example_page=example["page"], scenarios=example["scenarios"],
                               expectation_basis=example["expectation_basis"])
                if proof:
                    evidence.append({**proof, **details})
                elif (name, profile) in pending:
                    pending_cases.append(dict(example=name, profile=profile, **details))
                else:
                    invalid.append(f"Unverified example: {name}/{profile}")
        for issue in entry.get("known_issue_ids", []):
            reproductions = [examples.get(name, {}) for name in entry["examples"]]
            if not any(case.get("verification_role") == "known-defect-reproduction"
                       and issue in case.get("known_issue_ids", []) for case in reproductions):
                invalid.append(f"Missing labelled product reproduction: {issue}")
            issue_page = args.html_dir / (entry.get("known_issue_page", "") + ".html")
            if not issue_page.is_file() or issue not in issue_page.read_text(encoding="utf-8"):
                invalid.append(f"Missing public product disclosure: {issue}")
        if invalid:
            problems.append({"path": path, "problems": invalid})
        records.append({
            "path": path, "kind": entry["kind"], "origin": entry["origin"],
            "page": entry["page"], "anchor": entry["anchor"],
            "rendered_example_links": [
                {"page": case["page"], "id": case["id"]} for case in linked_cases
            ],
            "semantic_dimensions": entry["semantic_dimensions"],
            "scenarios": entry["scenarios"], "evidence": evidence, "pending": pending_cases,
            "known_issue_ids": entry.get("known_issue_ids", []),
            "status": "fail" if invalid else "pending" if pending_cases else "pass",
        })
    counts = Counter(record["status"] for record in records)
    authorize = args.slice == "all" and not args.allow_candidate and not problems and not pending
    result = {
        "at_utc": datetime.now(timezone.utc).isoformat(), "slice": args.slice,
        "version": target["version"], "source_commit": release["source_commit"],
        "candidate_only": args.allow_candidate, "aliases": inventory["aliases"],
        "verification_scope": "Public documentation, rendered anchors and current installed-wheel executions.",
        "product_functional_conformance_certified": False,
        "publication_authorized_by_this_result": authorize, "entries": len(records),
        "html_build_sha256": sha((args.html_dir / "_build-info.json").read_bytes())
        if (args.html_dir / "_build-info.json").is_file() else None,
        "passed": counts["pass"], "pending_entries": counts["pending"], "passed_case_profiles": len(checks),
        "pending_case_profiles": [{"example": name, "profile": profile} for name, profile in sorted(pending)],
        "problems": problems, "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(entries=len(records), passed=counts["pass"], pending=counts["pending"],
                          case_profiles=len(checks), problems=len(problems), publication_authorized=authorize)))
    if problems:
        print(json.dumps(problems[:15]))
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
