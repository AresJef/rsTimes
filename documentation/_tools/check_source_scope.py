"""Reject product changes in this documentation checkout and its CI wiring."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

DOC = Path(__file__).resolve().parents[1]
ROOT = DOC.parent


def git(*args):
    return subprocess.check_output(['git', '--no-optional-locks', *args], cwd=ROOT, text=True)


def changed(*args):
    return {path for path in git(*args, '-z').split('\0') if path}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--working-tree', action='store_true')
    args = parser.parse_args()
    binding = json.loads((DOC / '_data/source-checkout.json').read_text())
    base = binding['docs_base_commit']
    if subprocess.run(['git', 'cat-file', '-e', base + '^{commit}'], cwd=ROOT, capture_output=True).returncode:
        subprocess.run(['git', 'fetch', '--no-tags', '--depth=1', 'origin', base], cwd=ROOT, check=True)
    paths = changed('diff', '--name-only', '--no-renames', base, 'HEAD')
    if args.working_tree:
        paths.update(changed('diff', '--name-only', '--no-renames', 'HEAD'))
        paths.update(changed('ls-files', '--others', '--exclude-standard'))
    allowed = {'requirements-docs.txt', '.github/workflows/documentation.yml'}
    problems = [p for p in sorted(paths) if not p.startswith('documentation/') and p not in allowed]
    result = {'docs_base_commit': base, 'documentation_commit': git('rev-parse', 'HEAD').strip(),
              'changed_paths': sorted(paths),
              'problems': problems, 'status': 'fail' if problems else 'pass'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'changed_paths': len(paths), 'problems': problems}))
    return int(bool(problems))


if __name__ == '__main__':
    raise SystemExit(main())
