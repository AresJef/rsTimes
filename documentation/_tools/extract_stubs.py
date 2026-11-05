"""Extract the public API declarations from an installed wheel for AutoAPI."""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.metadata
import json
import re
from pathlib import Path
import rstimes

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True, help='Generated stub root; the rstimes package directory is created inside it.')
args = parser.parse_args()
args.output = args.output / 'rstimes'
args.output.mkdir(parents=True, exist_ok=True)
package = Path(rstimes.__file__).resolve().parent
public_classes = {"Delta", "Configs", "Pydt", "Pddt", "Pldt", "RstimesError", "ParseError", "ConfigError"}
public_functions = {"parse", "parse_str", "parse_to_epoch", "to_unix_ms", "from_unix_ms"}
for name in ("__init__", "delta", "parser", "pydt", "pddt", "pldt", "errors"):
    tree = ast.parse((package / (name + ".pyi")).read_text())
    if name == 'pldt':
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Pldt')
        initializer = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
        doc = initializer.body[0].value
        doc.value = doc.value.replace('Initialize the registered native namespace.', "Initialize this Pldt's native Datetime Series data.")
        doc.value = doc.value.replace('The existing receiver/state/namespace is initialized; no result column is returned.', 'The receiver is initialized. Python construction returns the completed Pldt; this initializer itself returns None.')
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            # A trailing underscore is a reStructuredText link marker. Treat this
            # actual NumPy type name as code, without changing product stubs.
            node.value = re.sub(r"(?<![`\w])numpy\.bool_(?![`\w])", "``numpy.bool_``", node.value)
            node.value = re.sub(r"(?m)^([ \t]*)Boolean options accept", r"\1Notes\n\1-----\n\1Boolean options accept", node.value)
            node.value = node.value.replace(
                "yearfirst and dayfirst are read-only after construction. Choose them when\ncreating Configs, or override them for one parse call with its arguments.",
                "Direct assignment to yearfirst and dayfirst is unsupported. Choose the flags\nwhen creating Configs, or override them for one parse call. Calling __init__\nagain replaces the flags and resets all token tables.",
            )
            if name == 'pddt':
                node.value = node.value.replace(
                    "Return this index's date-field namespace; native value replace is inherited.",
                    "Return this index's namespace for strict date-field replacement.",
                )
            if name == 'pldt':
                node.value = node.value.replace('Supported IANA name, ZoneInfo or representable standard fixed offset.', 'IANA name, ordinary ZoneInfo or representable standard fixed offset.')
    if name == 'pldt':
        namespaces = []
        for cls in (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in ('_SeriesNamespace', '_ExprNamespace')):
            root = 'polars.Series.pldt' if cls.name == '_SeriesNamespace' else 'polars.Expr.pldt'
            members = []
            for node in cls.body:
                if not isinstance(node, ast.FunctionDef) or node.name.startswith('_'):
                    continue
                method = copy.deepcopy(node)
                method.decorator_list = []
                method.args.args = [a for a in method.args.args if a.arg != 'self']
                signature = ast.unparse(method).splitlines()[0][4:-1]
                members.append({'name': node.name, 'signature': signature, 'property': any(isinstance(d, ast.Name) and d.id == 'property' for d in node.decorator_list), 'docstring': ast.get_docstring(node) or ''})
            namespaces.append({'path': root, 'members': members})
        assert {n['path'] for n in namespaces} == {'polars.Series.pldt', 'polars.Expr.pldt'}
        snapshot = {'stub_sha256': hashlib.sha256((package / 'pldt.pyi').read_bytes()).hexdigest(), 'namespaces': namespaces}
        (args.output / 'namespaces.json').write_text(json.dumps(snapshot, indent=2) + '\n')
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Pldt')
        cls.body[0].value.value = ast.get_docstring(cls) + '\n\n.. warning::\n\n    Known defect RV03: business ZoneInfo target overrides can be replaced by their key. See :doc:`/compatibility/known-issues` for the observed wrong instant and a verified workaround.'
    if name in ('pddt', 'pldt'):
        class_name = 'Pddt' if name == 'pddt' else 'Pldt'
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'copy')
        parameters = ast.get_docstring(method).split('\nReturns\n-------\n', 1)[0]
        method.body[0].value.value = parameters + f'''\nReturns
-------
{class_name} or object
    The default protocol returns a fresh same-class shell. Concrete custom
    copy hooks can choose a different result, as shown in the copy guide.

Notes
-----
Default shallow copies share safe date buffers and business references.
Default deep copies isolate date buffers and preserve aliases/cycles with
one memo. These operations do not rerun business initialization.

.. warning::

    Known defect RV04: named copy has incomplete None, missing and dynamic
    reduction fallback. The affected configurations can raise or bypass a
    legitimate reduction. See :doc:`/compatibility/known-issues` for observed
    behavior and standard copy-function workarounds. This is an unresolved
    defect, not a claim of complete custom reduction conformance.
'''
    tree.body = [n for n in tree.body if not isinstance(n, ast.ClassDef) or n.name in public_classes]
    tree.body = [n for n in tree.body if not isinstance(n, ast.FunctionDef) or n.name in public_functions]
    (args.output / (name + ".pyi")).write_text(ast.unparse(tree) + "\n")
provenance = {
    'product_version': importlib.metadata.version('rstimes'),
    'native': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in package.iterdir() if p.suffix in ('.so', '.pyd')},
    'stubs': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in package.glob('*.pyi')},
    'payload': {p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in package.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'},
}
(args.output / '_provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
print(f"Extracted seven public stub modules from {package}")
