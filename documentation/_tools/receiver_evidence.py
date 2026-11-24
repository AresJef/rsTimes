"""Observe example receivers on a registered wheel and publish the case index."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import runpy
import subprocess
import sys
from tempfile import TemporaryDirectory


DOC = Path(__file__).resolve().parents[1]
TOOLS = DOC / "_tools"
PROFILES = ("full", "polars-only", "core", "pandas2", "pandas-current", "polars-current",
            "nogil315", "nogil314", "optional-exports", "optional-exports-current",
            "public-install", "windows-full")
EXECUTIONS = {"select", "collect", "select-raises", "collect-raises"}
WARNING = "dependency-warning-filter"
RECIPE = "recipe-event-renewals"


def read(path):
    return json.loads(path.read_bytes())


def digest(content):
    return sha256(content).hexdigest()


def registrations():
    return {item["id"]: item for item in read(DOC / "_data/examples.json")["examples"]}


def profile_for(case):
    if case["id"] == WARNING and "core" in case["profiles"]:
        return "core"
    return next(profile for profile in PROFILES if profile in case["profiles"])


def check_recipe(events):
    parsed = {event["effect"] for event in events
              if event["entry"] == "polars.Expr.pldt.parse" and event["effect"] in EXECUTIONS}
    added = {event["effect"] for event in events
             if event["entry"] == "polars.Expr.pldt.add" and event["effect"] in EXECUTIONS}
    if parsed != {"collect"} or not {"select", "collect"} <= added:
        raise ValueError(f"{RECIPE}: expected parse only at collect, got {sorted(parsed)}; add {sorted(added)}")


def capture(profile, reports, output):
    coverage = runpy.run_path(str(TOOLS / "check_coverage.py"))
    scan, contract = coverage["SCAN"], coverage["CONTRACT"]
    inventory = [entry["path"] for entry in read(DOC / "_data/public-api.json")["entries"]]
    pages = defaultdict(list)
    for case in registrations().values():
        if profile_for(case) == profile:
            pages[case["page"]].append(case)

    def execute(page, payload, work):
        command = [sys.executable, "-I", "-B", str(TOOLS / "observe_receivers.py")]
        out = subprocess.run(command, input=json.dumps(dict(payload, filename=page, inventory=inventory)),
                             text=True, cwd=work, capture_output=True, timeout=120)
        if out.returncode or out.stderr:
            raise ValueError(f"Receiver observation failed for {page}/{profile}: {out.stderr}")
        return json.loads(out.stdout)

    def observe_page(item):
        page, cases = item
        relative = page.replace("/", "--") + ".json"
        report_bytes = (reports / relative).read_bytes()
        report = json.loads(report_bytes)
        source = DOC / page
        if (report["page"] != page or report["profile"] != profile or report["status"] != "pass"
                or report["page_sha256"] != digest(source.read_bytes())):
            raise ValueError(f"Receiver observation has no matching page receipt: {page}/{profile}")
        groups = {group["id"]: group for group in report["groups"]}
        snippets = {block.name: block for block in scan(source.read_text(encoding="utf-8"), source.suffix)}
        observed = {}
        with TemporaryDirectory(prefix="rstimes-doc-observer-") as work:
            contract_cases = [case for case in cases if case["format"] == "contract"]
            if contract_cases:
                check_source = DOC / "_checks" / Path(page).with_suffix(".txt")
                bodies = dict(contract.findall(check_source.read_text(encoding="utf-8")))
                verdicts = execute(page, {"contracts": bodies}, work)
                for case in contract_cases:
                    name = case["id"]
                    verdict, group = verdicts[name], groups[name]
                    if (verdict["failures"] or verdict["attempted"] != group["assertions"]
                            or group["sha256"] != digest(bodies[name].encode())):
                        raise ValueError(f"Observed contract differs from the passing receipt: {name}/{profile}")
                    observed[name] = verdict["uses"]
            for case in cases:
                if case["format"] != "python":
                    continue
                name = case["id"]
                snippet, group = snippets[name], groups[name]
                verdict = execute(page, {"code": snippet.code, "raises": case.get("raises")}, work)
                if (verdict["output"] != snippet.output or verdict["exception"] != case.get("raises")
                        or group["actual"]["output"] != snippet.output
                        or group["sha256"] != digest(snippet.code.encode())):
                    raise ValueError(f"Observed example differs from the passing receipt: {name}/{profile}")
                observed[name] = verdict["uses"]
        if RECIPE in observed:
            check_recipe(observed[RECIPE])
        return {name: {"profile": profile, "report": f"{profile}/{relative}",
                       "report_sha256": digest(report_bytes), "case_sha256": groups[name]["sha256"],
                       "observations": events}
                for name, events in observed.items() if groups[name]["status"] == "pass"}

    with ThreadPoolExecutor(max_workers=4) as pool:
        observed = {name: detail for result in pool.map(observe_page, sorted(pages.items()))
                    for name, detail in result.items()}
    if observed.keys() != {case["id"] for cases in pages.values() for case in cases}:
        raise ValueError(f"Receiver observation missed a registered case: {profile}")
    output.write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
    print(f"{profile}: observed {len(observed)} registered cases")


def observed_uses(events):
    """Keep actual observations and discard possible operator dispatches."""
    return [event for event in events if event["effect"] != "operator-candidate"]


def bind_cases(source, exact, reports, identity, cases):
    observations = read(source)
    if observations.keys() != cases.keys():
        raise ValueError("Receiver evidence must cover each registered case exactly once")
    check_recipe(observations[RECIPE]["observations"])
    index = {}
    for name, trace in observations.items():
        case = cases[name]
        profile = profile_for(case)
        relative = f'{profile}/{case["page"].replace("/", "--")}.json'
        public, source_sha, published_sha, _ = reports[relative]
        report = read(exact / public)
        group = next(item for item in report["groups"] if item["id"] == name)
        if (trace["profile"] != profile or trace["report"] != relative or trace["report_sha256"] != source_sha
                or group["status"] != "pass" or trace["case_sha256"] != group["sha256"]):
            raise ValueError(f"Receiver evidence is stale or attached to the wrong receipt: {name}")
        runtime = identity["profile_identities"][profile]
        link = Path(case["page"]).with_suffix(".html").as_posix() + "#" + name if case["format"] == "python" else None
        index[name] = {
            "example_link": link, "profile": profile, "format": case["format"],
            "report": public, "report_sha256": published_sha, "case_sha256": trace["case_sha256"],
            "wheel": runtime["wheel_filename"], "wheel_sha256": runtime["wheel_sha256"],
            "observations": observed_uses(trace["observations"]),
        }
    return index


def is_witness(row, event, visible):
    path = row["path"]
    if event["entry"] != path:
        return False
    if path.startswith("polars.Expr.pldt."):
        return event["effect"] in EXECUTIONS
    if visible and path.startswith("polars.Series.pldt") and event["receiver"] != "polars.series.series.Series":
        return False
    if event["effect"] == "read":
        return row["kind"] in {"property", "namespace", "namespace_accessor"}
    return event["effect"] in {"called", "raises", "constructor", "operator"}


def add_reader_evidence(rows, index):
    visible_by_entry = defaultdict(set)
    for case, trace in index.items():
        if trace["format"] != "python":
            continue
        for event in trace["observations"]:
            visible_by_entry[event["entry"]].add(case)
    for row in rows:
        linked = [item["id"] for item in row["rendered_example_links"]]
        actual = {
            name for name in visible_by_entry[row["path"]]
            if any(is_witness(row, event, True) for event in index[name]["observations"])
        }
        current = [name for name in linked if name in actual]
        backend = [name for name in row["examples"] if index[name]["format"] != "python"
                   and any(is_witness(row, event, False) for event in index[name]["observations"])]
        if current:
            status = "verified-reader-link"
        elif actual:
            status = "visible-example-needs-link"
        elif linked:
            status = "reader-receiver-pending"
        elif backend:
            status = "backend-witness-only"
        else:
            status = "backend-attribution-pending"
        row.update(receiver_index="verification/receivers.json", reader_status=status,
                   reader_witnesses=current, other_visible_witnesses=sorted(actual - set(current)),
                   backend_witnesses=backend)
        if row["path"] == "rstimes.errors.DependencyWarning" and WARNING not in current:
            raise ValueError("The DependencyWarning API row lacks its observed filter example")
    return dict(Counter(row["reader_status"] for row in rows))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    capture(args.profile, args.reports, args.output)
