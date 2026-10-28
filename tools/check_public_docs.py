"""Apply the established AST/doctest checks to the six current public stubs."""
import ast
import doctest
import json
from pathlib import Path
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import rstimes

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(rstimes.__file__).resolve().parent
HERE = ROOT / "evidence"
HERE.mkdir(exist_ok=True)
runner = doctest.DocTestRunner()
rows = []
missing = []
for path in sorted(SOURCE.glob('*.pyi')):
    tree = ast.parse(path.read_text())
    definitions = [node for node in ast.walk(tree) if isinstance(node, (ast.ClassDef, ast.FunctionDef))]
    namespace = dict(vars(rstimes), Pddt=rstimes.Pddt, Pydt=rstimes.Pydt, date=date,
                     datetime=datetime, time=time, timedelta=timedelta, timezone=timezone,
                     ZoneInfo=ZoneInfo)
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)) and not getattr(node, 'level', 0):
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    for node in definitions:
        if not ast.get_docstring(node):
            missing.append((path.name, node.name, 'docstring'))
        if isinstance(node, ast.FunctionDef):
            if node.returns is None:
                missing.append((path.name, node.name, 'return annotation'))
            arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
            for argument in arguments:
                if argument.arg not in ('self', 'cls') and argument.annotation is None:
                    missing.append((path.name, node.name, argument.arg))
        runner.run(doctest.DocTestParser().get_doctest(ast.get_docstring(node) or '',
                   namespace, path.name + ':' + node.name, str(path), 0))
    rows.append(dict(file=path.name, definitions=len(definitions)))
summary = runner.summarize()
result = dict(files=rows, definitions=sum(row['definitions'] for row in rows),
              missing=missing, examples=summary.attempted, example_failures=summary.failed,
              native=rstimes._native.__file__)
(HERE / 'public-docs-audit.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
raise SystemExit(bool(missing or summary.failed))
