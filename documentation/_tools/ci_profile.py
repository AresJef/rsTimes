"""Install one pinned public wheel, run its docs slice, and export only evidence."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

DOC = Path(__file__).resolve().parents[1]
ROOT = DOC.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inventory_only = args.profile.startswith('inventory')
    profiles = json.loads((DOC / '_data/profiles.json').read_text())['profiles']
    if args.profile not in profiles and args.profile not in ('inventory312', 'inventory314', 'inventory315'):
        parser.error('Unknown documentation profile')
    if os.environ.get('PYTHON_GIL') or os.environ.get('PYTHONPATH'):
        parser.error('Do not force GIL state or inject an import path')
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    environment = work / 'environment'
    subprocess.run([sys.executable, '-m', 'venv', str(environment)], check=True)
    python = environment / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')

    def run(*arguments):
        subprocess.run([str(python), *map(str, arguments)], cwd=ROOT, check=True)

    if args.profile.startswith('nogil'):
        qualified = list((ROOT / '.local/internal-polars-wheels').glob('*.whl'))
        if len(qualified) != 1:
            parser.error('Expected exactly one qualified compatible internal dependency wheel')
        run('-m', 'pip', 'install', '--no-deps', qualified[0])
    requirements = 'inventory' if inventory_only else args.profile
    run('-m', 'pip', 'install', '--disable-pip-version-check', '-r', DOC / 'requirements' / (requirements + '.txt'))
    version = json.loads((DOC / '_data/release.json').read_text())['version']
    wheels = work / 'wheel'
    run('-m', 'pip', 'download', '--only-binary=:all:', '--no-deps', '--dest', wheels, 'rsTimes==' + version)
    run('-I', DOC / '_tools/bind_release.py', '--wheel-dir', wheels, '--check-wheel-only')
    wheel = next(wheels.glob('*.whl'))
    run('-m', 'pip', 'install', '--no-deps', wheel)
    identity = work / 'identity.json'
    run('-I', DOC / '_tools/bind_release.py', '--wheel-dir', wheels, '--output', identity)
    projections = {'full': 'full', 'windows-full': 'full', 'pandas2': 'pandas2',
                   'pandas-current': 'current', 'polars-current': 'current',
                   'optional-exports': 'full', 'optional-exports-current': 'current',
                   'nogil314': 'nogil314', 'nogil315': 'nogil315',
                   'inventory312': '312', 'inventory314': 'full', 'inventory315': 'full'}
    inventory_report = work / 'inventory.json'
    if args.profile in projections:
        run('-I', DOC / '_tools/verify_inventory.py', '--projection', projections[args.profile], '--output', inventory_report)
    if inventory_only:
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / 'identity.json').write_bytes(identity.read_bytes())
    else:
        run('-I', DOC / '_tools/run_profile.py', '--profile', args.profile, '--evidence-dir', work / 'reports')
        command = ['-I', DOC / '_tools/export_evidence.py', '--reports', work / 'reports',
                   '--identity', identity, '--output', args.output]
        if args.profile == 'full':
            run('-I', DOC / '_tools/extract_stubs.py', '--output', work / 'stubs')
            run('-I', ROOT / 'tools/check_public_docs.py', '--evidence-dir', work / 'stub-audit')
            command += ['--stubs', work / 'stubs']
        run(*command)
    if inventory_report.exists():
        (args.output / 'inventory.json').write_bytes(inventory_report.read_bytes())
    if args.profile == 'full':
        audit = json.loads((work / 'stub-audit/public-docs-audit.json').read_text())
        audit.pop('native', None)
        (args.output / 'stub-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    context = dict(profile=args.profile, repository=os.environ['GITHUB_REPOSITORY'],
                   commit=os.environ['GITHUB_SHA'], run_id=os.environ['GITHUB_RUN_ID'],
                   run_attempt=os.environ['GITHUB_RUN_ATTEMPT'], inventory_only=inventory_only)
    (args.output / 'context.json').write_text(json.dumps(context, indent=2) + '\n')


if __name__ == '__main__':
    main()
