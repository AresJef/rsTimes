"""Check the ISO fields and named time-zone errors at installed and rendered entries."""

import argparse
import ast
import inspect
import json
from pathlib import Path
import re
import runpy


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
NAMESPACES = EAGER | {"Pddt": "rstimes.pddt.Pddt", "Expr.pldt": "polars.Expr.pldt"}
API_PAGES = {
    "api/reference/rstimes/pddt/index.html": "Pddt",
    "api/reference/rstimes/pldt/index.html": "Pldt",
    "api/polars-series.html": "Series.pldt",
    "api/polars-expressions.html": "Expr.pldt",
}
ISO_GUIDES = {
    "Pddt": "guides/pddt-boundaries.html#pddt-iso-week-year",
    "Pldt": "guides/pldt-queries.html#pldt-extract-iso-week-struct",
    "Series.pldt": "guides/pldt-output.html#pldt-series-isocalendar",
    "Expr.pldt": "guides/expressions-queries.html#expr-iso-field-structure",
}
ISO_EXAMPLE_RECEIVERS = {
    "Pddt": ("rstimes.Pddt.isocalendar", "rstimes.pddt.Pddt"),
    "Pldt": ("rstimes.Pldt.isocalendar", "rstimes.pldt.Pldt"),
    "Series.pldt": ("polars.Series.pldt.isocalendar", "polars.series.series.Series"),
    "Expr.pldt": ("polars.Expr.pldt.isocalendar", "polars.expr.expr.Expr"),
}
SHARED_LABELS = {
    "Pldt": "On a Pldt",
    "Series.pldt": "On a native Polars Series",
    "Expr.pldt": "In a Polars query",
}
ISO_FIELD = re.compile(
    r"\b(year|week|day)(?:\s+(?:and|,)\s+(week|day))?"
    r"\s+(?:columns?|fields?)\s+(?:(?:now|still)\s+)?(?:uses?|are|is|of type)\s+"
    r"(?:nullable\s+)?(Int64|UInt32)\b",
)
OLD_ISO = re.compile(
    r"UInt32 table capacity|(?:negative ISO years?|ISO years? outside).{0,50}(?:raises?|rejects?)"
    r"|use isoyear\(\) to read (?:a )?signed|three (?:nullable )?UInt32",
    re.I,
)

ZONE = re.compile(
    r"\b(?:(?:named|regional|iana)\s+(?:time\s*zones?|zones?)|(?:native\s+)?time\s*zone\s+backend)\b",
    re.I,
)
LIMIT = re.compile(r"\b(?:ranges?|bounds?|limits?|supported\s+(?:dates?|years?))\b", re.I)
OUTSIDE = re.compile(r"\b(?:outside|beyond|out of|exceeds?|too early or too late)\b", re.I)
OUTPUT_LIMIT = re.compile(
    r"\b(?:u?int\d+|storage|unit(?:'s)?|output integer)\s+(?:capacity|range|bounds?|limits?)\b",
    re.I,
)
CLAUSE_BREAK = re.compile(
    r"(?<=[.!?])\s+|;\s*|,?\s+or\s+(?=(?:the|an?)\s+(?:result|date)\b|outside\b)",
)
QUERY_ACTION = r"(?:select(?:\(\))? or collect(?:\(\))?|collect(?:\(\))? or select(?:\(\))?)"
EXPR_EXECUTION = re.compile(
    rf"\b(?:during|in)\s+{QUERY_ACTION}(?!\w)"
    rf"|\b{QUERY_ACTION}\s+(?:(?:will|can|may)\s+)?(?:raises?|fails?|evaluates?|process(?:es)?)\b",
    re.I,
)
EARLY_FAILURE = re.compile(
    r"\bbefore\s+(?:(?:the|actual)\s+)*(?:select|collect|execution|evaluation)\b"
    r"|\b(?:during|at)\s+(?:expression\s+)?(?:creation|construction|planning|schema inference)\b",
    re.I,
)
EXCEPTION_NAME = re.compile(r"\b[A-Za-z_][\w]*Error\b")


def regional_clauses(text):
    """Find clauses that describe the named time-zone date range."""
    text = " ".join(text.replace("-", " ").split())
    return [clause for clause in CLAUSE_BREAK.split(text)
            if ZONE.search(clause) and LIMIT.search(clause) and OUTSIDE.search(clause)
            and not OUTPUT_LIMIT.search(clause)]


def regional_reason(text):
    return bool(regional_clauses(text))


def expr_regional_reason(text):
    clauses = regional_clauses(text)
    return (any(EXPR_EXECUTION.search(clause) for clause in clauses)
            and not any(EARLY_FAILURE.search(clause) or set(EXCEPTION_NAME.findall(clause)) - {"ComputeError"}
                        for clause in clauses))


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


def eager_problems(name, raises):
    overflow = raises.get("OverflowError", "")
    problems = []
    if not regional_reason(overflow):
        problems.append("Explain the named time zone date range under OverflowError")
    if name in MOVES and not ("capacity" in overflow and "unit" in overflow):
        problems.append("Keep the result unit capacity reason under OverflowError")
    return problems


def runtime_problems(name, raises):
    if name not in MOVES | {"isocalendar", "isoyear"}:
        return []
    eager = raises.get("OverflowError", "")
    expression = raises.get("polars.exceptions.ComputeError", "")
    problems = []
    if not regional_reason(eager) or not all(receiver in eager for receiver in ("Pldt", "Series.pldt")):
        problems.append("Explain OverflowError for the named time zone date range on eager Pldt and Series.pldt")
    if not expr_regional_reason(expression):
        problems.append("Explain the Expr named time zone date range under ComputeError during select or collect")
    return problems


def iso_fields(text):
    fields = {}
    for first, second, dtype in ISO_FIELD.findall(" ".join(text.split())):
        for name in filter(None, (first, second)):
            fields.setdefault(name, set()).add(dtype)
    return fields


def iso_problems(name, receiver, returns, raises, text, carrier):
    shared = carrier == "runtime help" and receiver != "Pddt"
    problems = []
    if name == "isoyear":
        signed = "negative" in text or (receiver == "Pddt" and "signed" in text)
        if "Int64" not in returns or not signed or OLD_ISO.search(text):
            problems.append("Describe the signed single-year result without an obsolete table limit")
    else:
        wanted = {"year": {"Int64"}, "week": {"UInt32"}, "day": {"UInt32"}}
        if iso_fields(returns) != wanted or "negative" not in returns:
            problems.append("Returns must assign Int64 to year and UInt32 to week and day")
        if OLD_ISO.search(" ".join(text.split())) or any("UInt32" in error for error in raises.values()):
            problems.append("Remove the obsolete unsigned ISO year failure and workaround")
        if receiver == "Pddt":
            if not all(word in returns for word in ("index", "name", "nullable", "three cells missing")):
                problems.append("Describe the preserved pandas index and three missing cells")
        elif not all(word in returns for word in ("Struct", "column name", "null")):
            problems.append("Describe the named Struct and outer null")
        guide = ISO_GUIDES[receiver]
        example = text
        if shared:
            _, label, example = text.partition(SHARED_LABELS[receiver])
            if label:
                example = re.split(r"\n(?:On a Pldt|On a native Polars Series|In a Polars query)\b", example)[0]
        if guide not in example:
            problems.append(f"Link this receiver to its same-version example {guide}")

    if receiver == "Expr.pldt" and not shared:
        reason = raises.get("polars.exceptions.ComputeError", "")
        if "OverflowError" in raises or not expr_regional_reason(reason):
            problems.append("Explain the named time zone date range under ComputeError during select or collect")
    return problems


def doc_section(text, name):
    lines = inspect.cleandoc(text).splitlines()
    if name not in lines:
        return ""
    body = []
    start = lines.index(name) + 2
    for index in range(start, len(lines)):
        if index + 1 < len(lines) and re.fullmatch(r"-{3,}", lines[index + 1]):
            break
        body.append(lines[index])
    return "\n".join(body).strip("\n")


def iso_expression_observer(observer, inventory, entry, actor):
    from polars import Expr, Struct

    class IsoExpressionObserver(observer["Observer"]):
        def __init__(self, names):
            super().__init__(names)
            self.iso_outputs = {}
            self.materializations = []

        def wrapped(self, function, receiver, name, path, receiver_type, line):
            observed = super().wrapped(function, receiver, name, path, receiver_type, line)
            is_alias = name == "alias" and id(receiver) in self.iso_outputs
            if (path, receiver_type) != (entry, actor) and not is_alias:
                return observed

            def track_output(*args, **kwargs):
                result = observed(*args, **kwargs)
                if type(result) is Expr:
                    self.iso_outputs[id(result)] = result
                return result

            return track_output

        def projection_origins(self, source, expr, roots):
            # An alias or direct re-selection preserves a value column. Operations
            # such as len() can retain its root name while dropping its computation.
            if id(expr) in self.iso_outputs:
                return self.flow(expr)
            is_direct_column = type(expr) is str or (
                type(expr) is Expr and expr.meta.undo_aliases().meta.is_column()
            )
            if len(roots) == 1 and is_direct_column:
                return source.get(roots[0], set())
            return set()

        def materialized_column(self, frame, column, origin, action):
            super().materialized_column(frame, column, origin, action)
            if origin[:2] == (entry, actor):
                series = frame.get_column(column)
                dtype = series.dtype
                self.materializations.append({
                    "entry": entry, "receiver": actor, "column": column, "effect": action,
                    "dtype": str(dtype),
                    "fields": [[field.name, str(field.dtype)] for field in dtype.fields] if isinstance(dtype, Struct) else [],
                    "values": series.to_list(), "outer_nulls": series.is_null().to_list(),
                })

    return IsoExpressionObserver(inventory)


def installed_iso_example(receiver, doc, file, observer):
    """Execute the installed example and observe the receiver and materialization."""
    inventory = [entry for entry, _ in ISO_EXAMPLE_RECEIVERS.values()]
    entry, actor = ISO_EXAMPLE_RECEIVERS[receiver]
    label = str(file) + "::" + entry
    example = doc_section(doc, "Examples")
    watches_values = receiver == "Expr.pldt"
    trace = (iso_expression_observer(observer, inventory, entry, actor)
             if watches_values else observer["Observer"](inventory))
    result = observer["contracts"]({entry: example}, trace, label)[entry]
    actual = {event["effect"] for event in result["uses"]
              if (event["entry"], event["receiver"]) == (entry, actor)}
    problems = []
    if not result["attempted"] or result["failures"]:
        problems.append("Run the installed isocalendar example and match its documented output")
    if "called" not in actual:
        problems.append(f"The installed example must call {entry} on {actor}")
    if watches_values:
        result["materializations"] = trace.materializations
        if not any(item["fields"] == [["year", "Int64"], ["week", "UInt32"], ["day", "UInt32"]]
                   and item["values"] == [{"year": 2020, "week": 53, "day": 5}, None]
                   and item["outer_nulls"] == [False, True] for item in trace.materializations):
            problems.append("The installed Expr example must materialize its ISO year, week and day and the outer null in select or collect")
    return result, problems


def html_section(description, name):
    for field in description.select(":scope > dl.field-list > dt"):
        if field.get_text(" ", strip=True).rstrip(":").strip() == name:
            return field.find_next_sibling("dd")
    return None


def html_raises(description):
    """Read the text of each actual exception in one rendered API entry."""
    errors = {}
    body = html_section(description, "Raises")
    if body is not None:
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
    names = REGIONAL_METHODS | CONTROLS if receiver in EAGER else {"isocalendar", "isoyear"}
    for name in sorted(names):
        entry = NAMESPACES[receiver] + "." + name
        anchor = main.find(id=entry)
        description = anchor.find_next_sibling("dd") if anchor else None
        raises = html_raises(description) if description else {}
        returns = html_section(description, "Returns") if description else None
        returned = returns.get_text(" ", strip=True) if returns else ""
        text = description.get_text(" ", strip=True) if description else ""
        if description:
            text += " " + " ".join(link["href"] for link in description.select("a[href]"))
        problems = eager_problems(name, raises) if receiver in EAGER else []
        if name in ("isocalendar", "isoyear"):
            problems.extend(iso_problems(name, receiver, returned, raises, text, "HTML"))
        if name == "isocalendar" and description:
            primary = [
                link["href"]
                for paragraph in description.find_all("p", recursive=False)
                if paragraph.get_text(" ", strip=True).startswith("Example in ")
                for link in paragraph.select("a[href]")
            ]
            if len(primary) != 1 or not primary[0].endswith(ISO_GUIDES[receiver]):
                problems.append("The primary example must lead to this receiver's guide anchor")
        rows.append({"entry": entry, "receiver": receiver, "carrier": "HTML", "page": relative,
                     "line": anchor.sourceline if anchor else None, "returns": returned,
                     "raises": raises, "problems": problems})
    return rows


def check_install(stub, pddt_stub):
    import polars as pl
    from rstimes import Pddt, Pldt
    import rstimes.pldt

    series = pl.Series("event", [0], dtype=pl.Datetime("ms", "UTC"))
    owners = {
        "Pldt": Pldt, "Series.pldt": type(series.pldt),
        "Expr.pldt": type(pl.col("event").pldt), "Pddt": Pddt,
    }
    if stub is None:
        stub = Path(rstimes.pldt.__file__).with_suffix(".pyi")
    if pddt_stub is None:
        pddt_stub = Path(inspect.getfile(Pddt)).with_suffix(".pyi")
    classes = {
        node.name: (node, file)
        for file in (stub, pddt_stub)
        for node in ast.parse(file.read_bytes()).body if isinstance(node, ast.ClassDef)
    }
    observer = runpy.run_path(str(Path(__file__).with_name("observe_receivers.py")))
    rows = []
    for receiver, owner in owners.items():
        namespace = NAMESPACES[receiver]
        names = REGIONAL_METHODS | CONTROLS if receiver in EAGER else {"isocalendar", "isoyear"}
        if receiver == "Expr.pldt":
            names |= MOVES
        declaration = {"Series.pldt": "_SeriesNamespace", "Expr.pldt": "_ExprNamespace"}.get(receiver, receiver)
        cls, file = classes[declaration]
        for name in sorted(names):
            entry = namespace + "." + name
            public = inspect.getattr_static(owner, name)
            text = inspect.getdoc(public) or ""
            provider = public.fget if isinstance(public, property) else public
            carriers = [("runtime help", provider.__code__.co_filename, provider.__code__.co_firstlineno, text)]
            if receiver != "Expr.pldt" or name not in MOVES:
                method, = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name]
                carriers.append(("installed stub", str(file), method.lineno, ast.get_docstring(method) or ""))
            for carrier, location, line, copy in carriers:
                raises = doc_raises(copy)
                returns = " ".join(doc_section(copy, "Returns").split())
                shared = carrier == "runtime help" and receiver != "Pddt"
                problems = eager_problems(name, raises) if shared or receiver in EAGER else []
                if shared:
                    problems.extend(runtime_problems(name, raises))
                if name in ("isocalendar", "isoyear"):
                    problems.extend(iso_problems(name, receiver, returns, raises, copy, carrier))
                row = {"entry": entry, "receiver": receiver, "carrier": carrier, "file": location,
                       "line": line, "returns": returns, "raises": raises, "problems": problems}
                if carrier == "installed stub" and name == "isocalendar":
                    row["example"], example_problems = installed_iso_example(receiver, copy, file, observer)
                    problems.extend(example_problems)
                rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stub", type=Path, help="Use an isolated stub copy as the declaration input.")
    parser.add_argument("--pddt-stub", type=Path, help="Use an isolated pandas declaration input.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = check_install(args.stub, args.pddt_stub)
    problems = [row for row in rows if row["problems"]]
    receipt = {"status": "fail" if problems else "pass", "rows": rows, "problems": problems}
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "checked": len(rows), "problems": problems}))
    return bool(problems)


if __name__ == "__main__":
    raise SystemExit(main())
