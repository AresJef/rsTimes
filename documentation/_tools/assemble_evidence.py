"""Combine only the complete set of same-run, same-commit producer artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

DOC = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--run-attempt', required=True)
    args = parser.parse_args()
    profiles = set(json.loads((DOC / '_data/profiles.json').read_text())['profiles'])
    expected = profiles | {'inventory312', 'inventory314', 'inventory315'}
    found = {}
    for context_file in sorted(args.input.rglob('context.json')):
        context = json.loads(context_file.read_text())
        profile = context['profile']
        if profile not in expected or profile in found:
            parser.error('Unexpected or duplicate producer: ' + profile)
        for key in ('repository', 'commit', 'run_id', 'run_attempt'):
            if str(context[key]) != str(getattr(args, key)):
                parser.error('Evidence from a different workflow context: ' + key)
        found[profile] = context_file.parent
    if set(found) != expected:
        parser.error('Missing producer artifacts: ' + ', '.join(sorted(expected - found.keys())))
    if args.output.exists() or any(p.is_symlink() for p in args.input.rglob('*')):
        parser.error('Output must be fresh and producer artifacts must not contain links')
    args.output.mkdir(parents=True)
    identity = json.loads((found['full'] / 'identity.json').read_text())
    audit = json.loads((found['full'] / 'stub-audit.json').read_text())
    if audit['missing'] or audit['example_failures'] or not audit['examples']:
        parser.error('Installed public-stub examples did not pass')
    identity['profile_identities'] = {}
    for profile, directory in found.items():
        current = json.loads((directory / 'identity.json').read_text())
        if current['product_version'] != identity['product_version'] or current['stubs'] != identity['stubs'] or current['public_api_paths'] != identity['public_api_paths']:
            parser.error('Producers disagree about the public package or inventory')
        inventory = directory / 'inventory.json'
        if inventory.exists() and json.loads(inventory.read_text())['status'] != 'pass':
            parser.error('Actual runtime/stub inventory failed: ' + profile)
        if profile not in profiles:
            if not inventory.exists():
                parser.error('Missing supported-Python inventory projection')
            continue
        identity['profile_identities'][profile] = current
        reports = directory / 'reports'
        if not reports.is_dir():
            parser.error('Missing actual page reports for ' + profile)
        for report_file in reports.rglob('*.md.json'):
            if json.loads(report_file.read_text())['profile'] != profile:
                parser.error('Report profile differs from its producer')
        shutil.copytree(reports, args.output / 'reports' / profile)
    shutil.copytree(found['full'] / 'stubs', DOC / '_stubs', dirs_exist_ok=True)
    (args.output / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    (args.output / 'context.json').write_text(json.dumps(dict(repository=args.repository, commit=args.commit,
        run_id=args.run_id, run_attempt=args.run_attempt, producers=sorted(found)), indent=2) + '\n')
    print(json.dumps({'producers': len(found), 'page_profiles': len(profiles), 'actual_native_identities_kept_separate': True}))


if __name__ == '__main__':
    main()
