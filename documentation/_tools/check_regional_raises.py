"""Check the documented named-time-zone range at the installed and rendered entries."""

import argparse
import ast
import inspect
import json
from pathlib import Path
import re


MOVES = frozenset({
    "normalize", "to_monday", "to_tuesday", "to_wednesday", "to_thursday",
    "to_friday", "to_saturday", "to_sunday", "to_yesterday", "to_tomorrow",
})
QUERIES = frozenset({
    "year", "month", "day", "hour", "minute", "second", "weekday", "quarter", "day_of_month",
    "day_of_quarter", "day_of_year", "days_in_month", "days_in_quarter", "days_in_year",
    "days_bf_month", "days_bf_quarter", "days_bf_year", "is_leap_year", "is_long_year", "isoyear",
    "isoweek", "isoweekday", "isocalendar", "toordinal", "time", "ctime", "tzname", "is_dst",
    "utcoffset_seconds", "timedf",
})
REGIONAL_METHODS = MOVES | QUERIES
CONTROLS = frozenset({"date", "values_naive"})
EAGER = {"Pldt": "rstimes.pldt.Pldt", "Series.pldt": "polars.Series.pldt"}
API_PAGES = {"api/reference/rstimes/pldt/index.html": "Pldt", "api/polars-series.html": "Series.pldt"}

ZONE = re.compile(
    r"\b(?:(?:named|regional|iana)\s+(?:time\s*zones?|zones?)|(?:native\s+)?time\s*zone\s+backend)\b",
    re.I,
)
LIMIT = re.compile(r"\b(?:ranges?|bounds?|limits?|supported\s+(?:dates?|years?))\b", re.I)
OUTSIDE = re.compile(r"\b(?:outside|beyond|out of|exceeds?)\b", re.I)
OUTPUT_LIMIT = re.compile(
    r"\b(?:u?int\d+|storage|unit(?:'s)?|output integer)\s+(?:capacity|range|bounds?|limits?)\b",
    re.I,
)
CLAUSE_BREAK = re.compile(
    r"(?<=[.!?])\s+|;\s*|,?\s+or\s+(?=(?:the|an?)\s+(?:result|date)\b|outside\b)",
)


def regional_reason(text):
    """Recognize the actual cause within one error clause, with flexible wording."""
    text = " ".join(text.replace("-", " ").split())
    return any(
        ZONE.search(clause) and LIMIT.search(clause) and OUTSIDE.search(clause)
        and not OUTPUT_LIMIT.search(clause)
        for clause in CLAUSE_BREAK.split(text)
    )


def doc_raises(doc):
    """Read a NumPy-style Raises section without searching examples or notes."""
    lines = inspect.cleandoc(doc).splitlines()
    entries = {}
    if "Raises" not in lines:
        return entries
    exception = None
    for line in lines[lines.index("Raises") + 2:]:
        if not line:
            continue
        if re.fullmatch(r"[A-Za-z_][\w.]*Error", line):
            exception = line
            entries[exception] = []
        elif line.startswith(" ") and exception:
            entries[exception].append(line.strip())
        else:
            break
    return {error: " ".join(parts) for error, parts in entries.items()}


def eager_problems(name, raises, text):
    overflow = raises.get("OverflowError", "")
    problems = []
    if not regional_reason(overflow):
        problems.append("Explain the named time zone date range under OverflowError")
    if name in MOVES and not ("capacity" in overflow and "unit" in overflow):
        problems.append("Keep the result unit capacity reason under OverflowError")
    if name == "isocalendar":
        negative_year = re.search(r"negative ISO years?|ISO years? (?:is|are|can be) negative", text, re.I)
        if "UInt32" not in overflow or not negative_year or "isoyear()" not in text:
            problems.append("Explain the unsigned ISO field and signed isoyear() alternative")
        if not any("isoyear()" in clause and ZONE.search(clause) and LIMIT.search(clause)
                   for clause in re.split(r"(?<=[.!?])\s+|;\s*", " ".join(text.split()))):
            problems.append("Explain that the named time zone limit also applies to isoyear()")
    return problems


def runtime_problems(name, raises):
    if name not in MOVES and name != "isocalendar":
        return []
    eager = raises.get("OverflowError", "")
    expression = raises.get("polars.exceptions.ComputeError", "")
    if (not all(receiver in eager for receiver in ("Pldt", "Series.pldt"))
            or not regional_reason(expression)
            or not all(word in expression for word in ("select", "collect"))):
        return ["Identify the eager OverflowError and the Expr range error during select or collect"]
    return []


def html_raises(description):
    """Read the text of each actual exception in one rendered API entry."""
    errors = {}
    for field in description.select(":scope > dl.field-list > dt"):
        if field.get_text(" ", strip=True).rstrip(":").strip() != "Raises":
            continue
        body = field.find_next_sibling("dd")
        if body is None:
            break
        for item in body.select(":scope > p, :scope > ul > li > p"):
            name = item.find("strong")
            if name:
                tag = name.get_text(" ", strip=True)
                errors[tag] = item.get_text(" ", strip=True).removeprefix(tag).lstrip(" –—-")
    return errors


def check_api_page(main, relative):
    receiver = API_PAGES.get(relative)
    if not receiver:
        return []
    rows = []
    for name in sorted(REGIONAL_METHODS | CONTROLS):
        entry = EAGER[receiver] + "." + name
        anchor = main.find(id=entry)
        description = anchor.find_next_sibling("dd") if anchor else None
        raises = html_raises(description) if description else {}
        text = description.get_text(" ", strip=True) if description else ""
        rows.append({"entry": entry, "receiver": receiver, "carrier": "HTML", "page": relative,
                     "line": anchor.sourceline if anchor else None, "raises": raises,
                     "problems": eager_problems(name, raises, text)})
    return rows


def check_install(stub):
    import polars as pl
    from rstimes import Pldt
    import rstimes.pldt

    series = pl.Series("event", [0], dtype=pl.Datetime("ms", "UTC"))
    owners = {"Pldt": Pldt, "Series.pldt": type(series.pldt), "Expr.pldt": type(pl.col("event").pldt)}
    if stub is None:
        stub = Path(rstimes.pldt.__file__).with_suffix(".pyi")
    classes = {node.name: node for node in ast.parse(stub.read_bytes()).body if isinstance(node, ast.ClassDef)}
    rows = []
    for receiver, owner in owners.items():
        namespace = EAGER.get(receiver, "polars.Expr.pldt")
        names = MOVES | {"isocalendar"} if receiver == "Expr.pldt" else REGIONAL_METHODS | CONTROLS
        for name in sorted(names):
            entry = namespace + "." + name
            public = inspect.getattr_static(owner, name)
            text = inspect.getdoc(public) or ""
            provider = public.fget if isinstance(public, property) else public
            raises = doc_raises(text)
            rows.append({"entry": entry, "receiver": receiver, "carrier": "runtime help",
                         "file": provider.__code__.co_filename, "line": provider.__code__.co_firstlineno,
                         "raises": raises, "problems": eager_problems(name, raises, text) + runtime_problems(name, raises)})
            if receiver == "Expr.pldt":
                continue
            body = classes["Pldt" if receiver == "Pldt" else "_SeriesNamespace"].body
            method, = [node for node in body if isinstance(node, ast.FunctionDef) and node.name == name]
            text = ast.get_docstring(method) or ""
            raises = doc_raises(text)
            rows.append({"entry": entry, "receiver": receiver, "carrier": "installed stub",
                         "file": str(stub), "line": method.lineno, "raises": raises,
                         "problems": eager_problems(name, raises, text)})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stub", type=Path, help="Use an isolated stub copy as the declaration input.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = check_install(args.stub)
    problems = [row for row in rows if row["problems"]]
    receipt = {"status": "fail" if problems else "pass", "rows": rows, "problems": problems}
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "checked": len(rows), "problems": problems}))
    return bool(problems)


if __name__ == "__main__":
    raise SystemExit(main())
