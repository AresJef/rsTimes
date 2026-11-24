"""Readable type labels for generated reference pages, derived from the wheel stubs."""

import ast
import re

LABELS = {
    "_ActualDateInput": "DateFieldInput",
    "_Ambiguous": "RepeatedTimePolicy",
    "_BoolCollection": "PandasBooleanColumn",
    "_BooleanMask": "PolarsBooleanColumn",
    "_CalendarInput": "CalendarCoordinate",
    "_Column": "PandasColumn",
    "_CombineDate": "CombineDateInput",
    "_CombineTime": "CombineTimeInput",
    "_DT": "DatetimeResult",
    "_DateCollection": "DateCollection",
    "_DateInput": "DateInput",
    "_DateT": "DateResult",
    "_DateValue": "DateValue",
    "_DatetimeInput": "DatetimeInput",
    "_DatetimeT": "DatetimeResult",
    "_DeltaInput": "DeltaInput",
    "_DeltaT": "DeltaResult",
    "_DiffInput": "DateDifferenceInput",
    "_DiffValue": "DateDifferenceValue",
    "_EpochInput": "EpochInput",
    "_Error": "ExceptionType",
    "_ExprAmbiguous": "ExprRepeatedTimePolicy",
    "_ExprCalendarInput": "ExprCalendarCoordinate",
    "_ExprIntegerInput": "ExprIntegerInput",
    "_ExprOptionalField": "ExprOptionalInteger",
    "_ExprQuerySelection": "ExprQueryTarget",
    "_ExprSelection": "ExprCalendarSelection",
    "_FixedAmount": "DurationAmount",
    "_FixedFrequency": "FixedFrequency",
    "_IntegerArgument": "IntegerArgument",
    "_IntegerInput": "IntegerInput",
    "_IsoInput": "ISODateInput",
    "_MapValue": "IndexValue",
    "_Metadata": "BusinessState",
    "_Missing": "MissingDate",
    "_Nonexistent": "SkippedTimePolicy",
    "_NumericInput": "NumericInput",
    "_NumpyDateInput": "NumPyDateInput",
    "_NumpyInput": "NumPyDateInput",
    "_OptionalField": "OptionalInteger",
    "_PddtNamespace": "PandasDateNamespace",
    "_PddtT": "PddtResult",
    "_PldtT": "PldtResult",
    "_QuerySelection": "QueryTarget",
    "_ReplaceFields": "ReplaceFields",
    "_Selection": "CalendarSelection",
    "_SeriesNamespace": "PolarsSeriesDateNamespace",
    "_State": "DeltaState",
    "_StoredSelection": "NamedCalendarSelection",
    "_TimedeltaT": "TimedeltaResult",
    "_Zone": "TimezoneInput",
}
INLINE = {
    "_Boolean", "_Default", "_Unit",
}
MODULE_NAMES = {"_dt": "datetime", "np": "numpy", "pd": "pandas", "pl": "polars"}
EXTERNAL = {
    "_PolarsSeries": "polars.Series",
    "_NAType": "type(pandas.NA)",
    "_NaTType": "type(pandas.NaT)",
}
WORD = re.compile(r"\b_[A-Z][A-Za-z_0-9]*\b")
CLASS_TYPES = {
    "_PddtNamespace": "The .pddt namespace of the corresponding Pddt class.",
    "_SeriesNamespace": "The .pldt namespace of the corresponding Polars Series class.",
}

def declarations(tree):
    """Read type definitions without importing optional adapters or editing their stubs."""
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            found[node.targets[0].id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found[node.target.id] = node.value
        elif isinstance(node, ast.ClassDef) and node.name in LABELS:
            found[node.name] = node
    return found


def present(tree):
    """Change only the shadow annotations and documented type fields used for HTML."""
    aliases = declarations(tree)
    definitions = {}
    active = set()

    def resolve(name):
        if name in INLINE and name in aliases:
            return show(aliases[name])
        if name in EXTERNAL:
            return EXTERNAL[name]
        label = LABELS.get(name)
        if label is None or name not in aliases:
            return name
        if label not in definitions and label not in active:
            active.add(label)
            value = aliases[name]
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "TypeVar":
                bound, = (kw.value for kw in value.keywords if kw.arg == "bound")
                target = bound.value if isinstance(bound, ast.Constant) else show(bound)
                description = (
                    f"The concrete {target} input type. Repeated uses of this label in "
                    "the same signature refer to that same type."
                )
            elif name in CLASS_TYPES:
                description = CLASS_TYPES[name]
            elif isinstance(value, ast.ClassDef):
                fields = [
                    f"{field.target.id}: {show(field.annotation)}"
                    for field in value.body if isinstance(field, ast.AnnAssign)
                ]
                description = "Optional keys " + ", ".join(fields) + "."
            else:
                description = show(value)
            active.remove(label)
            definitions[label] = description
        return label

    class TypeNames(ast.NodeTransformer):
        def visit_Name(self, node):
            value = MODULE_NAMES.get(node.id, node.id)
            replacement = resolve(value)
            if replacement == node.id:
                return node
            return ast.parse(replacement, mode="eval").body

    def show(node):
        # Reparse the expression so definitions in the installed tree are never modified.
        clone = ast.parse(ast.unparse(node), mode="eval").body
        return ast.unparse(TypeNames().visit(clone))

    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.annotation is not None:
            node.annotation = ast.parse(show(node.annotation), mode="eval").body
        elif isinstance(node, ast.FunctionDef) and node.returns is not None:
            node.returns = ast.parse(show(node.returns), mode="eval").body
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
            doc = ast.get_docstring(node)
            if doc:
                # Only known internal type spellings occur in these docstrings;
                # executable examples have already been split out by the extractor.
                clean = WORD.sub(lambda match: resolve(match[0]), doc)
                node.body[0].value.value = clean
    return definitions


def link_types(app, doctree):
    """Link visible labels to definitions in the same generated API page."""
    import json
    from pathlib import Path

    from docutils import nodes
    from sphinx import addnodes

    docname = app.env.docname
    if docname.startswith("api/reference/rstimes/"):
        module = docname.split("/")[3]
    elif docname in {"api/polars-series", "api/polars-expressions"}:
        module = "pldt"
    else:
        return
    registry = json.loads((Path(app.srcdir) / "_stubs/rstimes/public-types.json").read_text())
    definitions = registry.get(module, {})
    if not definitions:
        return
    names = re.compile(r"\b(?:" + "|".join(map(re.escape, definitions)) + r")\b")
    used = set()

    def anchor(label):
        return "type-" + re.sub(r"(?<!^)(?=[A-Z])", "-", label).lower()

    def reference(label):
        used.add(label)
        return nodes.reference(label, label, refuri="#" + anchor(label), internal=True)

    for xref in list(doctree.findall(addnodes.pending_xref)):
        label = xref.get("reftarget", "").rsplit(".", 1)[-1]
        if label in definitions:
            xref.replace_self(reference(label))
    for parent in (*doctree.findall(addnodes.desc_signature), *doctree.findall(nodes.field_body)):
        for leaf in list(parent.findall(nodes.Text)):
            if leaf.parent is None or isinstance(leaf.parent, (nodes.reference, addnodes.pending_xref)):
                continue
            start, pieces = 0, []
            for match in names.finditer(str(leaf)):
                pieces.extend((nodes.Text(str(leaf)[start:match.start()]), reference(match[0])))
                start = match.end()
            if pieces:
                pieces.append(nodes.Text(str(leaf)[start:]))
                leaf.parent.replace(leaf, pieces)
    if not used:
        return

    # Include type definitions referred to by other displayed labels on this page.
    definitions_on_page = used.copy()
    pending = sorted(used)
    while pending:
        for dependency in names.findall(definitions[pending.pop()]):
            if dependency not in definitions_on_page:
                pending.append(dependency)
                definitions_on_page.add(dependency)
    section = nodes.section(ids=["signature-type-guide"])
    section += nodes.title("Types in these signatures", "Types in these signatures")
    section += nodes.paragraph(text="These labels are for reading the signatures on this page. In Python code, use the types from their original packages and the public rsTimes API.")
    items = nodes.definition_list()
    for label in sorted(definitions_on_page):
        term = nodes.term(label, label, ids=[anchor(label)])
        text = nodes.paragraph()
        prior = 0
        for match in names.finditer(definitions[label]):
            text += nodes.Text(definitions[label][prior:match.start()])
            text += reference(match[0])
            prior = match.end()
        text += nodes.Text(definitions[label][prior:])
        items += nodes.definition_list_item("", term, nodes.definition("", text))
    section += items
    body = next(iter(doctree.findall(nodes.section)), doctree)
    body += section

