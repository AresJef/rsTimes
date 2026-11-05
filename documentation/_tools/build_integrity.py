"""Bind a static HTML build to current sources and installed-package extraction."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_inputs(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if not path.is_file() or any(p in ('_build', '_generated', '__pycache__') for p in relative.parts):
            continue
        if relative.parts[:2] == ('api', 'reference') or path.suffix in ('.pyc', '.doctree', '.pickle'):
            continue
        result[relative.as_posix()] = sha(path)
    requirements = root.parent / 'requirements-docs.txt'
    if requirements.exists():
        result['build-config/requirements-docs.txt'] = sha(requirements)
    return result


def html_outputs(root):
    root = Path(root)
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and p.relative_to(root).as_posix() != '_build-info.json'}


def build_started(app):
    output = Path(app.outdir)
    if Path(app.doctreedir).is_relative_to(output):
        raise RuntimeError('Use sphinx-build -d with a doctree directory outside the public HTML output.')
    app.rstimes_source_inputs = source_inputs(app.srcdir)
    (output / '_build-info.json').unlink(missing_ok=True)


def build_finished(app, exception):
    if exception is not None or app.statuscode or app._warncount:
        return
    current = source_inputs(app.srcdir)
    if current != app.rstimes_source_inputs:
        raise RuntimeError('Documentation inputs changed during the HTML build; rebuild before verification.')
    # Sphinx's incremental-build cache belongs outside the published artifact.
    # The doctree directory is already separate; remove only its own root marker.
    (Path(app.outdir) / '.buildinfo').unlink(missing_ok=True)
    # The theme's Jinja macro is needed while rendering, never by a browser.
    # Remove only this known build output; check all remaining HTML strictly.
    (Path(app.outdir) / '_static/webpack-macros.html').unlink(missing_ok=True)
    outputs = html_outputs(app.outdir)
    if any(part.startswith('.') for name in outputs for part in Path(name).parts):
        raise RuntimeError('Private build/cache files must not be inside the public HTML output.')
    provenance = json.loads((Path(app.srcdir) / '_stubs/rstimes/_provenance.json').read_text())
    data = dict(schema=1, complete=True, built_at_utc=datetime.now(timezone.utc).isoformat(),
                website_version=app.config.release, source_inputs=current, outputs=outputs,
                installed_package=provenance)
    (Path(app.outdir) / '_build-info.json').write_text(json.dumps(data, indent=2) + '\n')
