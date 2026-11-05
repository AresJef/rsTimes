"""Reject product changes in this documentation checkout and its CI wiring."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

DOC = Path(__file__).resolve().parents[1]
ROOT = DOC.parent


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--working-tree', action='store_true')
    args = parser.parse_args()
    binding = json.loads((DOC / '_data/source-checkout.json').read_text())
    base = binding['docs_base_commit']
    if subprocess.run(['git', 'cat-file', '-e', base + '^{commit}'], cwd=ROOT, capture_output=True).returncode:
        subprocess.run(['git', 'fetch', '--no-tags', '--depth=1', 'origin', base], cwd=ROOT, check=True)
    paths = set(git('diff', '--name-only', base, 'HEAD').splitlines())
    if args.working_tree:
        paths.update(git('diff', '--name-only', 'HEAD').splitlines())
        paths.update(git('ls-files', '--others', '--exclude-standard').splitlines())
    allowed = {'requirements-docs.txt', '.github/workflows/documentation.yml'}
    problems = [p for p in sorted(paths) if not p.startswith('documentation/') and p not in allowed]
    for name, digest in binding['source_files'].items():
        path = ROOT / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            problems.append('Published source input changed: ' + name)
    for name, digest in binding.get('maintenance_inputs', {}).items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            problems.append('Existing main-maintenance input changed: ' + name)
    result = {'docs_base_commit': base, 'published_source_commit': binding['source_commit'],
              'checked_source_inputs': len(binding['source_files']), 'changed_paths': sorted(paths),
              'checked_existing_maintenance_inputs': len(binding.get('maintenance_inputs', {})),
              'problems': problems, 'status': 'fail' if problems else 'pass'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'changed_paths': len(paths), 'problems': problems}))
    return int(bool(problems))


if __name__ == '__main__':
    raise SystemExit(main())
