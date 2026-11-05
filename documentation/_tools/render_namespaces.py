"""Render installed namespace declarations at their actual public paths."""
import json
from pathlib import Path
from sphinx.ext.napoleon import Config
from sphinx.ext.napoleon.docstring import NumpyDocstring


def render(snapshot: Path, destination: Path) -> None:
    data = json.loads(snapshot.read_text())
    config = Config(napoleon_preprocess_types=True, napoleon_type_aliases={
        'date': 'datetime.date', 'datetime': 'datetime.datetime',
        'time': 'datetime.time', 'timedelta': 'datetime.timedelta',
    })
    for namespace in data['namespaces']:
        root = namespace['path']
        series = root == 'polars.Series.pldt'
        title = 'Polars Series date namespace' if series else 'Polars expression date namespace'
        lines = [title, '=' * len(title), '',
                 f'.. py:class:: {root}', '',
                 '   Access this namespace on a real Polars Series.' if series else '   Access this namespace on a native Polars Expr. Results execute in select or collect.', '',
                 '   Import rstimes to register the accessor. It is not a separately constructed user object.', '',
                 '   Known product limitations, including custom ZoneInfo targets, are disclosed in',
                 '   :doc:`/compatibility/known-issues`.', '',
                 'See the :doc:`../guides/pldt` guide for native storage and the',
                 ':doc:`../guides/expressions` guide for executed eager and lazy queries.', '']
        seen = set()
        for member in namespace['members']:
            name = member['name']
            assert name not in seen, (root, name)
            seen.add(name)
            if member['property']:
                lines += [f'.. py:property:: {root}.{name}', '']
            else:
                lines += [f".. py:method:: {root}.{member['signature']}", '']
            rendered = str(NumpyDocstring(member['docstring'], config)).splitlines()
            lines += ['   ' + line if line else '' for line in rendered] + ['']
        filename = 'polars-series.rst' if series else 'polars-expressions.rst'
        (destination / filename).write_text('\n'.join(lines) + '\n')
