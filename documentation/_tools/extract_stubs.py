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
public_functions = {"parse", "parse_str", "parse_to_epoch", "parse_to_integer", "parse_to_float",
                    "to_unix_ms", "from_unix_ms"}


def for_website(node, module):
    """Use the shipped description with links to standalone website examples."""
    doc = ast.get_docstring(node)
    if not doc:
        return
    lines = doc.splitlines()
    starts = [i for i in range(len(lines) - 1)
              if lines[i].strip() and re.fullmatch(r"-{3,}", lines[i + 1])]
    for position, start in reversed(list(enumerate(starts))):
        if lines[start] not in {"Example", "Examples"}:
            continue
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        del lines[start:end]
    content = "\n".join(lines).strip()
    if re.search(r"(?m)^\s*(?:>>> |\.\. (?:code|code-block|sourcecode|literalinclude)::|\x60\x60\x60(?:python|pycon))", content):
        raise ValueError(f"Unrouted executable example in {module}.{getattr(node, 'name', 'module')}")
    rendered = []
    for line in content.splitlines():
        if re.match(r"^[\w ,]+ : ", line):
            # Napoleon parses prose unions in type fields.
            rendered.append(line.replace("bool | numpy.bool_", "bool or numpy.bool_"))
        else:
            rendered.append(re.sub(r"(?<![`\w])numpy\.bool_(?![`\w])", "``numpy.bool_``", line))
    content = "\n".join(rendered)
    content = re.sub(r"(?m)^Boolean options accept", "Notes\n-----\nBoolean options accept", content)
    node.body[0].value.value = content


for name in ("__init__", "delta", "parser", "pydt", "pddt", "pldt", "errors"):
    tree = ast.parse((package / (name + ".pyi")).read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
            for_website(node, name)
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
