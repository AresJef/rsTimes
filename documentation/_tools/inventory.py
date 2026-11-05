"""Inventory installed public paths without importing the source checkout.

Run with the isolated example interpreter. This is documentation tooling only.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path
import sys

import rstimes
from rstimes import errors
import pandas as pd
import polars as pl
from polars.series.plotting import SeriesPlot

PROTOCOLS = {
    "__new__", "__init__", "__add__", "__radd__", "__iadd__", "__sub__",
    "__rsub__", "__isub__", "__mul__", "__rmul__", "__truediv__",
    "__rtruediv__", "__floordiv__", "__rfloordiv__", "__mod__", "__rmod__",
    "__pow__", "__rpow__", "__divmod__", "__rdivmod__", "__matmul__",
    "__neg__", "__pos__", "__abs__", "__invert__", "__and__", "__rand__",
    "__or__", "__ror__", "__xor__", "__rxor__", "__eq__", "__ne__",
    "__lt__", "__le__", "__gt__", "__ge__", "__hash__", "__bool__",
    "__len__", "__iter__", "__next__", "__reversed__", "__contains__",
    "__getitem__", "__setitem__", "__delitem__", "__str__", "__repr__",
    "__format__", "__bytes__", "__int__", "__float__", "__index__",
    "__copy__", "__deepcopy__", "__getstate__", "__setstate__", "__reduce__",
    "__reduce_ex__", "__array__", "__array_ufunc__", "__array_function__",
    "__arrow_c_array__", "__arrow_c_stream__", "__dlpack__",
    "__dlpack_device__", "__dataframe__", "__replace__", "__round__",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signature(node: ast.FunctionDef) -> str:
    # Do not copy stub bodies or docstrings into the signature.
    returns = " -> " + ast.unparse(node.returns) if node.returns else ""
    return f"{node.name}({ast.unparse(node.args)}){returns}"


def inventory() -> dict:
    package = Path(rstimes.__file__).resolve().parent
    specs = [
        ("rstimes.Delta", rstimes.Delta, "delta.pyi", "Delta"),
        ("rstimes.Configs", rstimes.Configs, "parser.pyi", "Configs"),
        ("rstimes.Pydt", rstimes.Pydt, "pydt.pyi", "Pydt"),
        ("rstimes.Pddt", rstimes.Pddt, "pddt.pyi", "Pddt"),
        ("rstimes.Pddt.pddt", type(rstimes.Pddt([]).pddt), "pddt.pyi", "_PddtNamespace"),
        ("rstimes.Pldt", rstimes.Pldt, "pldt.pyi", "Pldt"),
        ("polars.Series.pldt", type(pl.Series([], dtype=pl.Datetime("us")).pldt), "pldt.pyi", "_SeriesNamespace"),
        ("polars.Expr.pldt", type(pl.col("date").pldt), "pldt.pyi", "_ExprNamespace"),
        ("rstimes.Pldt.dt", type(pl.Series([], dtype=pl.Datetime("us")).dt), None, None),
        ("rstimes.Pldt.ext", type(pl.Series([], dtype=pl.Datetime("us")).ext), None, None),
        ("rstimes.Pldt.plot", SeriesPlot, None, None),
    ]
    specs.extend((f"rstimes.errors.{name}", getattr(errors, name), "errors.pyi", name) for name in errors.__all__)
    rows, exclusions = [], []
    trees = {p.name: ast.parse(p.read_text()) for p in package.glob("*.pyi")}
    for prefix, typ, stub, clsname in specs:
        cls = next((n for n in trees[stub].body if isinstance(n, ast.ClassDef) and n.name == clsname), None) if stub else None
        declared: dict[str, list[ast.FunctionDef]] = {}
        if cls:
            for node in cls.body:
                if isinstance(node, ast.FunctionDef):
                    declared.setdefault(node.name, []).append(node)
        if clsname in ("_SeriesNamespace", "_ExprNamespace", "_PddtNamespace"):
            declared.pop("__init__", None)  # Accessor construction is not the public call path.
        if prefix.endswith((".dt", ".ext", ".plot")):
            names = {n for n in dir(typ) if not n.startswith("_")}
            names |= {n for n in PROTOCOLS if n != '__init__' and any(n in base.__dict__ for base in typ.__mro__ if base is not object)}
        else:
            names = {n for n in dir(typ) if not n.startswith("_") or n in PROTOCOLS} | set(declared)
        if clsname and clsname.startswith("_"):
            names -= {n for n in names if n.startswith("_")}
        for name in sorted(names):
            if name.startswith("_") and name not in PROTOCOLS:
                exclusions.append({"path": f"{prefix}.{name}", "reason": "private implementation detail"})
                continue
            nodes = declared.get(name, [])
            provider = next((c for c in typ.__mro__ if name in vars(c)), None)
            try:
                descriptor = inspect.getattr_static(typ, name)
                runtime_present = True
                doc = inspect.getdoc(descriptor) or ""
                try:
                    runtime_signature = str(inspect.signature(getattr(typ, name)))
                except (TypeError, ValueError, AttributeError):
                    runtime_signature = None
            except AttributeError:
                descriptor, doc, runtime_signature = None, "", None
                runtime_present = False
            # Registered upstream accessors are non-data descriptors. Class
            # lookup returns an accessor class, whose constructor signature is
            # not the user-facing property access syntax.
            descriptor_type = type(descriptor)
            namespace_accessor = (
                (descriptor_type.__module__ == "polars.api" and descriptor_type.__name__ == "NameSpace")
                or (descriptor_type.__module__ == "pandas.core.accessor" and descriptor_type.__name__ in ("Accessor", "CachedAccessor"))
            )
            if namespace_accessor:
                runtime_signature = None
            rows.append({
                "path": f"{prefix}.{name}", "owner": prefix, "name": name,
                "kind": "protocol" if name.startswith("__") else "namespace_accessor" if namespace_accessor else "property" if isinstance(descriptor, property) or inspect.isdatadescriptor(descriptor) else "method",
                "declared_in_stub": bool(nodes), "stub": stub,
                "stub_lines": [n.lineno for n in nodes],
                "signatures": [signature(n) for n in nodes],
                "runtime_signature": runtime_signature,
                "runtime_present": runtime_present,
                "disabled": runtime_present and descriptor is None,
                "provider": f"{provider.__module__}.{provider.__qualname__}" if provider else None,
                "origin": "library" if provider and provider.__module__.startswith("rstimes") else "inherited",
                "source_description": ast.get_docstring(nodes[-1]) if nodes else doc,
                "page": None, "anchor": None, "examples": [], "scenarios": [],
                "status": "unmapped",
            })
        rows.append({"path": prefix, "owner": prefix, "name": clsname or typ.__name__, "kind": "namespace" if ".pldt" in prefix or prefix.endswith((".pddt", ".dt", ".ext", ".plot")) else "class", "signatures": [], "stub": stub, "stub_lines": [cls.lineno] if cls else [], "runtime_present": True, "origin": "library" if cls else "inherited", "source_description": ast.get_docstring(cls) if cls else inspect.getdoc(typ), "page": None, "anchor": None, "examples": [], "scenarios": [], "status": "unmapped"})
    for module, stub, exports in [(rstimes, "__init__.pyi", rstimes.__all__), (rstimes.parser, "parser.pyi", rstimes.parser.__all__)]:
        for name in exports:
            obj = getattr(module, name)
            if inspect.isclass(obj):
                continue
            prefix = "rstimes." + name
            if any(r["path"] == prefix for r in rows):
                continue
            selected_stub = stub
            nodes = [n for n in trees[selected_stub].body if isinstance(n, ast.FunctionDef) and n.name == name]
            # Root re-exports have their declaration in parser.pyi.
            if not nodes:
                nodes = [n for n in trees["parser.pyi"].body if isinstance(n, ast.FunctionDef) and n.name == name]
                selected_stub = "parser.pyi"
            rows.append({"path": prefix, "owner": "rstimes", "name": name, "kind": "function", "stub": selected_stub, "stub_lines": [n.lineno for n in nodes], "signatures": [signature(n) for n in nodes], "runtime_present": True, "origin": "library", "source_description": ast.get_docstring(nodes[-1]) if nodes else inspect.getdoc(obj), "page": None, "anchor": None, "examples": [], "scenarios": [], "status": "unmapped"})
    aliases = {f"rstimes.{module}.{name}": f"rstimes.{name}" for module, names in [("delta", ["Delta"]), ("parser", rstimes.parser.__all__), ("pydt", ["Pydt"]), ("pddt", ["Pddt"]), ("pldt", ["Pldt"])] for name in names}
    # A namespace accessor and the namespace it returns are one public call
    # path. Retain both descriptions without counting that path twice.
    unique = {}
    namespace_accessors = []
    for row in rows:
        previous = unique.get(row['path'])
        if previous is None:
            unique[row['path']] = row
            continue
        if row['kind'] != 'namespace' or previous['kind'] != 'property':
            raise ValueError(f"Unexpected duplicate public path: {row['path']}")
        previous['accessor_kind'] = previous['kind']
        previous['kind'] = 'namespace'
        previous['namespace_definition'] = {k: row[k] for k in ('owner', 'name', 'stub', 'stub_lines', 'source_description')}
        namespace_accessors.append(row['path'])
    declaration_count = len(rows)
    rows = list(unique.values())
    for row in rows:
        if row['owner'] == 'rstimes.Pydt' and row['name'] in ('min', 'max', 'resolution'):
            row['kind'] = 'attribute'
    return {
        "schema": 3, "product_version": importlib.metadata.version("rstimes"),
        "target_status": "provisional_latest_adopted_implementation_awaiting_release",
        "python": sys.version, "package": str(package),
        "dependencies": {n: importlib.metadata.version(n) for n in ("numpy", "pandas", "polars", "python-dateutil")},
        "native": {p.name: sha(p) for p in package.iterdir() if p.suffix in ('.so', '.pyd')},
        "stubs": {p.name: sha(p) for p in package.glob("*.pyi")},
        "exports": rstimes.__all__, "error_exports": errors.__all__,
        "aliases": aliases, "rows": sorted(rows, key=lambda x: x["path"]),
        "exclusions": exclusions,
        "scope_note": "Inherited datetime/pandas/Polars public members and usable Datetime and genericExtension/Plot namespaces included. Dtype-specific non-Datetime namespaces are recorded at their accessors; their unrelated dtype API is not an rsTimes datetime API. Private implementation helpers excluded. Overloads are signatures of one entry, not extra entries.",
        "counts": dict(Counter(r["owner"] for r in rows)),
        "raw_descriptor_and_namespace_rows": declaration_count,
        "merged_namespace_accessor_paths": namespace_accessors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps({"entries": len(data["rows"]), "owners": data["counts"], "missing_runtime": [r["path"] for r in data["rows"] if not r["runtime_present"]]}, indent=2))
