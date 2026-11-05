"""Export current CI evidence without local paths, transcripts or environment files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports', type=Path, required=True)
    parser.add_argument('--identity', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stubs', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh evidence-export directory')
    args.output.mkdir(parents=True)
    reports = sorted(args.reports.rglob('*.md.json'))
    if not reports:
        parser.error('No actual page reports were produced')
    for path in reports:
        report = json.loads(path.read_text())
        if report['status'] != 'pass' or report['identity'].get('import_location_verified') is not True:
            parser.error('Only actual passing installed-wheel reports can be exported')
        report['original_report_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        report['identity']['package_path'] = 'verified-interpreter/site-packages/rstimes'
        report.pop('transcript', None)
        destination = args.output / 'reports' / path.relative_to(args.reports)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + '\n')
    shutil.copyfile(args.identity, args.output / 'identity.json')
    if args.stubs:
        if any(p.is_symlink() for p in args.stubs.rglob('*')):
            parser.error('Generated stubs must not contain links')
        shutil.copytree(args.stubs, args.output / 'stubs', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    print(json.dumps({'exported_reports': len(reports), 'included_stubs': args.stubs is not None}))


if __name__ == '__main__':
    main()
