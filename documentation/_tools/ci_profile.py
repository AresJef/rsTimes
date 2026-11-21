"""Install one pinned public wheel, run its docs slice, and export only evidence."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import urlopen

DOC = Path(__file__).resolve().parents[1]
ROOT = DOC.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--release-source', type=Path)
    parser.add_argument('--candidate-distributions', type=Path)
    args = parser.parse_args()
    inventory_only = args.profile.startswith('inventory')
    profiles = json.loads((DOC / '_data/profiles.json').read_text())['profiles']
    if args.profile not in profiles and args.profile not in ('inventory312', 'inventory314', 'inventory315'):
        parser.error('Unknown documentation profile')
    official = args.release_source.resolve() if args.release_source else None
    candidate = args.candidate_distributions.resolve() if args.candidate_distributions else None
    target = json.loads((DOC / 'target.json').read_text())
    if bool(candidate) != (target['status'] == 'candidate'):
        parser.error('Only a candidate target accepts the verified CI distributions directory')
    if (args.profile == 'full' or args.profile.startswith('nogil')) and official is None:
        parser.error('This profile requires the independent released source checkout')
    if os.environ.get('PYTHON_GIL') or os.environ.get('PYTHONPATH'):
        parser.error('Do not force GIL state or inject an import path')
    work = args.work.resolve()
    output = args.output.resolve()
    work.mkdir(parents=True, exist_ok=False)
    environment = work / 'environment'
    subprocess.run([sys.executable, '-m', 'venv', str(environment)], check=True)
    python = environment / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')

    def run(*arguments):
        subprocess.run([str(python), *map(str, arguments)], cwd=ROOT, check=True)

    if args.profile.startswith('nogil'):
        qualified = list((official / '.local/internal-polars-wheels').glob('*.whl'))
        if len(qualified) != 1:
            parser.error('Expected exactly one qualified compatible internal dependency wheel')
        run('-m', 'pip', 'install', '--no-deps', qualified[0])
    requirements = 'inventory' if inventory_only else args.profile
    run('-m', 'pip', 'install', '--disable-pip-version-check', '-r', DOC / 'requirements' / (requirements + '.txt'))
    release = json.loads((DOC / '_data/release.json').read_text())
    version = release['version']
    wheels = work / 'wheel'
    distribution_source = ('--no-index', '--find-links', candidate) if candidate else ()
    run('-m', 'pip', 'download', '--only-binary=:all:', '--no-deps', '--dest', wheels,
        *distribution_source, 'rsTimes==' + version)
    run('-I', DOC / '_tools/bind_release.py', '--wheel-dir', wheels, '--check-wheel-only')
    wheel = next(wheels.glob('*.whl'))
    run('-m', 'pip', 'install', '--no-deps', wheel)
    identity = work / 'identity.json'
    run('-I', DOC / '_tools/bind_release.py', '--wheel-dir', wheels, '--output', identity)
    projections = {'core': 'core', 'polars-only': 'polars-only',
                   'full': 'full', 'windows-full': 'full', 'pandas2': 'pandas2',
                   'pandas-current': 'current', 'polars-current': 'current',
                   'optional-exports': 'full', 'optional-exports-current': 'current',
                   'nogil314': 'nogil314', 'nogil315': 'nogil315',
                   'inventory312': '312', 'inventory314': '314', 'inventory315': '315'}
    inventory_report = work / 'inventory.json'
    if args.profile in projections:
        run('-I', DOC / '_tools/verify_inventory.py', '--projection', projections[args.profile], '--output', inventory_report)
    if inventory_only:
        output.mkdir(parents=True, exist_ok=False)
        (output / 'identity.json').write_bytes(identity.read_bytes())
    else:
        run('-I', DOC / '_tools/run_profile.py', '--profile', args.profile, '--evidence-dir', work / 'reports')
        command = ['-I', DOC / '_tools/export_evidence.py', '--reports', work / 'reports',
                   '--identity', identity, '--output', output]
        if args.profile == 'full':
            run('-I', DOC / '_tools/extract_stubs.py', '--output', work / 'stubs')
            source_check = DOC / '_tools/check_published_source.py'
            source_argument = '--commit-repository' if candidate else '--tag-repository'
            run('-I', source_check, source_argument, official, '--output', work / 'source-tag.json')
            (source_file, source_record), = [
                (name, record) for name, record in release['files'].items()
                if record['packagetype'] == 'sdist'
            ]
            archive = work / source_file
            if candidate:
                shutil.copyfile(candidate / source_file, archive)
            else:
                with urlopen(source_record['url'], timeout=60) as response:
                    archive.write_bytes(response.read(source_record['size'] + 1))
            run('-I', source_check, '--sdist', archive, '--output', work / 'source-sdist.json')
            run('-I', official / 'tools/check_public_docs.py', '--evidence-dir', work / 'stub-audit')
            command += ['--stubs', work / 'stubs']
        run(*command)
        if args.profile in ('full', 'windows-full'):
            run('-I', DOC / '_tools/check_receiver_observer.py', output / 'receiver-observer.json')
    if inventory_report.exists():
        (output / 'inventory.json').write_bytes(inventory_report.read_bytes())
    if args.profile == 'full':
        for filename in ('source-tag.json', 'source-sdist.json'):
            (output / filename).write_bytes((work / filename).read_bytes())
        audit = json.loads((work / 'stub-audit/public-docs-audit.json').read_text())
        audit.pop('native', None)
        (output / 'stub-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    context = dict(profile=args.profile, repository=os.environ['GITHUB_REPOSITORY'],
                   commit=os.environ['GITHUB_SHA'], run_id=os.environ['GITHUB_RUN_ID'],
                   run_attempt=os.environ['GITHUB_RUN_ATTEMPT'], inventory_only=inventory_only)
    (output / 'context.json').write_text(json.dumps(context, indent=2) + '\n')


if __name__ == '__main__':
    main()
