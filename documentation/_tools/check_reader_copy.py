"""Check reader-visible API copy after Sphinx has rendered it."""

import argparse
import json
from pathlib import Path
import re
import runpy

from bs4 import BeautifulSoup


TYPES = runpy.run_path(str(Path(__file__).with_name("public_types.py")))
REGIONAL = runpy.run_path(str(Path(__file__).with_name("check_regional_raises.py")))
PRIVATE_TYPES = set(TYPES["LABELS"]) | TYPES["INLINE"] | set(TYPES["EXTERNAL"])
PRIVATE_TYPE = re.compile(r"\b(?:" + "|".join(map(re.escape, sorted(PRIVATE_TYPES))) + r")\b")
KNOWN_BAD_COPY = re.compile(
    r"\b(?:curr|prev)\s+calendar\b|\bA Int64\b|\botherwise0\b|\bcore17\b|\bversion[12]\b",
    re.IGNORECASE,
)
MODULE_OPENING = re.compile(
    r"^(?:type hints for|type information for|public type information for|public home of)\b",
    re.IGNORECASE,
)
BACKTICKS = chr(96) * 2
CHOICES = {
    "to_first_of": {"unit": "Y Q M W"},
    "to_last_of": {"unit": "Y Q M W"},
    "to_start_of": {"unit": "Y Q M W D h m s ms us"},
    "to_end_of": {"unit": "Y Q M W D h m s ms us"},
    "is_first_of": {"unit": "Y Q M W"},
    "is_last_of": {"unit": "Y Q M W"},
    "is_start_of": {"unit": "Y Q M W D h m s ms us"},
    "is_end_of": {"unit": "Y Q M W D h m s ms us"},
    "round": {"freq": "D h m min s ms us ns"},
    "ceil": {"freq": "D h m min s ms us ns"},
    "floor": {"freq": "D h m min s ms us ns"},
    "diff": {"unit": "Y Q M W D h m min s ms us", "inclusive": "one both neither"},
}
READER_GUIDES = [
    "guides/pldt-factories.html", "guides/pldt-boundaries.html",
    "guides/expressions-boundaries.html", "guides/expressions-calendar.html",
    "guides/pydt-boundaries.html", "guides/pldt-calendar.html",
    "guides/pddt.html", "guides/pldt.html",
    "guides/pddt-ranges.html", "guides/pldt-ranges.html",
    "guides/pldt-queries.html", "guides/pldt-output.html", "guides/expressions-queries.html",
    "compatibility/free-threaded.html", "compatibility/known-issues.html",
    "getting-started/index.html", "development/contributing.html",
]
TIMEDF_FIELDS = {
    "tm_year", "tm_mon", "tm_mday", "tm_hour", "tm_min", "tm_sec", "tm_wday", "tm_yday", "tm_isdst",
}
PLDT_QUERY_PAGES = {
    "api/reference/rstimes/pldt/index.html": "rstimes.pldt.Pldt",
    "api/polars-series.html": "polars.Series.pldt",
    "api/polars-expressions.html": "polars.Expr.pldt",
}
CONFIG_INDEX_SETTERS = ("set_tzoffset", "set_month", "set_weekday", "set_hms", "set_ampm")
NARROW_DICT = re.compile(r"\bdict\s*\[\s*str\s*,\s*(?:typing\.)?SupportsIndex\s*\]")


def visible(node):
    return node.get_text(" ", strip=True)


def parameters(description):
    for field in description.select(":scope > dl.field-list > dt"):
        if visible(field).removesuffix(":").strip() != "Parameters":
            continue
        body = field.find_next_sibling("dd")
        for item in (*body.find_all("p", recursive=False), *body.select(":scope > ul > li")):
            name = item.find("strong")
            if name:
                yield visible(name), item


def owner(node):
    for panel in node.find_parents("dl"):
        head = panel.select_one(":scope > dt.sig[id]")
        if head:
            return head["id"]
    return ""


def method_description(main, entry):
    head = main.find(id=entry)
    return head.find_next_sibling("dd") if head else None


def check(html):
    pages = set((html / "api").rglob("*.html"))
    pages.update(html / path for path in REGIONAL["API_PAGES"])
    problems, fields, notes_seen, page_records = [], [], [], {}
    query_fields, dict_fields = {}, {}
    regional_raises = []
    root = html / "api/reference/rstimes"

    def fail(path, entry, field, reason):
        problems.append(dict(page=path.relative_to(html).as_posix(), entry=entry, field=field, reason=reason))

    for path in sorted([*pages, *(html / name for name in READER_GUIDES)]):
        if not path.is_file():
            fail(path, "", "", "Missing public page")
            continue
        markup = BeautifulSoup(path.read_bytes(), "html.parser")
        main = markup.find("main")
        if main is None:
            fail(path, "", "", "Missing main content")
            continue
        signatures = main.select("dt.sig")
        for tag in [*signatures, *main.select("dl.field-list")]:
            body = visible(tag)
            if private := PRIVATE_TYPE.search(body):
                fail(path, tag.get("id", "") or owner(tag), "type", f"Private type {private[0]}")
            if BACKTICKS in body:
                fail(path, tag.get("id", "") or owner(tag), "parameter or return", "Unrendered backticks")
        for ref in main.select('a[href^="#type-"]'):
            if main.find(id=ref["href"][1:]) is None:
                fail(path, owner(ref), "type", "Missing same-page definition for " + visible(ref))
        for tag in main.find_all(["p", "li"]):
            if tag.find_parent(["pre", "code"]) is not None:
                continue
            if error := KNOWN_BAD_COPY.search(visible(tag)):
                fail(path, owner(tag), "", "Stale reader wording " + error[0])
        if path.parent.parent == root and path.parent.name in {"delta", "parser", "pydt", "pddt"}:
            section = main.find("section")
            opening = section.find("p", recursive=False) if section else None
            if opening is None or MODULE_OPENING.search(visible(opening)):
                fail(path, path.parent.name, "module", "Missing reader-oriented module introduction")
        if path == root / "pydt/index.html":
            for method, expected in CHOICES.items():
                entry = f"rstimes.pydt.Pydt.{method}"
                head = main.find(id=entry)
                description = head.find_next_sibling("dd") if head else None
                actual = dict(parameters(description)) if description else {}
                for field, choices in expected.items():
                    tag = actual.get(field)
                    terms = re.findall(r"\w+", visible(tag)) if tag else []
                    if tag is None or not set(choices.split()) <= set(terms) or BACKTICKS in visible(tag):
                        fail(path, entry, field, "Missing or broken literal choices")
                    else:
                        fields.append([entry, field, choices.split()])
            entry = "rstimes.pydt.Pydt.fromisoformat"
            head = main.find(id=entry)
            description = head.find_next_sibling("dd") if head else None
            literal = dict(parameters(description)).get("dtstr") if description else None
            if literal is None or literal.find("dl") or "stored text" not in visible(literal):
                fail(path, entry, "dtstr", "Expected one plain parameter description")
        if path == root / "parser/index.html":
            for name in CONFIG_INDEX_SETTERS:
                entry = "rstimes.parser.Configs." + name
                description = method_description(main, entry)
                field = dict(parameters(description)).get("mapping") if description else None
                text = visible(field) if field else ""
                if NARROW_DICT.search(text) or not all(word in text for word in ("string keys", "integer values")):
                    fail(path, entry, "mapping", "Describe string keys and integer values without narrowing the generic dict")
                else:
                    dict_fields[entry] = text
            for name in ("parse", "parse_str", "parse_to_epoch"):
                entry = "rstimes.parser." + name
                head = main.find(id=entry)
                description = head.find_next_sibling("dd") if head else None
                headings = [] if not description else [
                    tag for tag in description.find_all("p", class_="rubric", recursive=False)
                    if visible(tag) == "Notes"
                ]
                if (len(headings) != 1 or visible(description).count("Boolean options accept") != 1
                        or not any("Boolean options accept" in visible(p) for p in headings[0].find_next_siblings("p"))):
                    fail(path, entry, "Notes", "Expected one Boolean options paragraph under Notes")
                else:
                    notes_seen.append(entry)
        if namespace := PLDT_QUERY_PAGES.get(path.relative_to(html).as_posix()):
            entry = namespace + ".timedf"
            description = method_description(main, entry)
            text = visible(description) if description else ""
            if (not TIMEDF_FIELDS <= set(re.findall(r"\btm_[a-z]+\b", text))
                    or "whole second" not in text or "including fractional seconds and fold" in text):
                fail(path, entry, "time fields", "Expected nine named fields with tm_sec as a whole second")
            else:
                query_fields[entry] = text
            entry = namespace + ".isocalendar"
            description = method_description(main, entry)
            text = visible(description) if description else ""
            error = "ComputeError" if namespace == "polars.Expr.pldt" else "OverflowError"
            if not all(word in text for word in (error, "UInt32", "isoyear()")):
                fail(path, entry, "Raises", f"Explain {error} for the UInt32 ISO year and how to use isoyear()")
            else:
                query_fields[entry] = text
        for row in REGIONAL["check_api_page"](main, path.relative_to(html).as_posix()):
            regional_raises.append(row)
            for reason in row["problems"]:
                fail(path, row["entry"], "Raises", reason)
                problems[-1].update(receiver=row["receiver"], carrier=row["carrier"], line=row["line"])
        page_records[path.relative_to(html).as_posix()] = {
            "signatures": len(signatures),
            "type_links": len(main.select('a[href^="#type-"]')),
        }
    return dict(status="fail" if problems else "pass", pages=page_records,
                api_pages=len(pages), literal_fields=fields, parser_notes=notes_seen,
                timedf_and_iso_fields=query_fields, config_index_fields=dict_fields,
                regional_year_raises=regional_raises, problems=problems)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = check(args.html)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: receipt[key] for key in ("status", "api_pages", "problems")}, ensure_ascii=False))
    return bool(receipt["problems"])


if __name__ == "__main__":
    raise SystemExit(main())

