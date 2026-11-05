"""Package checked HTML and public verification receipts for exact-version Pages."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil

DOC = Path(__file__).resolve().parents[1]
SITE_PREFIX = '/rsTimes/'


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html', type=Path, required=True)
    parser.add_argument('--coverage', type=Path, required=True)
    parser.add_argument('--reports', type=Path, required=True)
    parser.add_argument('--identity', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--run-url', required=True)
    args = parser.parse_args()
    gate = json.loads(args.coverage.read_text())
    if gate.get('publication_authorized_by_this_result') is not True:
        parser.error('A complete passing publication gate is required')
    target = json.loads((DOC / 'target.json').read_text())
    version = target['version']
    if version != json.loads(args.identity.read_text())['product_version']:
        parser.error('Package and website version differ')
    if args.output.exists() or any(p.is_symlink() for p in args.html.rglob('*')):
        parser.error('Use a fresh destination and a site without filesystem links')
    exact = args.output / version
    shutil.copytree(args.html, exact)
    public_reports = {}
    for report_file in sorted(args.reports.rglob('*.md.json')):
        report = json.loads(report_file.read_text())
        if report.get('status') != 'pass' or report.get('failures'):
            parser.error('Only passing current reports belong in the site')
        report.pop('transcript', None)
        report['identity']['package_path'] = 'verified-interpreter/site-packages/rstimes'
        relative = Path('verification/reports') / args.reports.name / report_file.relative_to(args.reports)
        write_json(exact / relative, report)
        public_reports[report_file.resolve()] = relative.as_posix()
    rows = []
    manifest = json.loads((DOC / '_data/coverage.json').read_text())
    mapped = {row['path']: row for row in manifest['entries']}
    for record in gate['records']:
        row = dict(record)
        row['evidence'] = [dict(item, report=public_reports[Path(item['report']).resolve()]) for item in record['evidence']]
        row['examples'] = mapped[row['path']]['examples']
        row['profiles'] = mapped[row['path']]['profiles']
        rows.append(row)
    write_json(exact / 'verification/coverage.json', dict(entries=len(rows), records=rows,
               scope=gate['verification_scope'], known_product_defects=gate['known_product_defects']))
    with (exact / 'verification/coverage.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['entry', 'page', 'scenarios', 'examples', 'profiles', 'evidence', 'status'])
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(entry=row['path'], page=row['page'] + '.html#' + row['anchor'],
                scenarios=json.dumps(row['scenarios']), examples=json.dumps(row['examples']),
                profiles=json.dumps(row['profiles']), evidence=json.dumps(row['evidence']), status=row['status']))
    identity = json.loads(args.identity.read_text())
    build = dict(schema=1, product_version=version, source_commit=target['source_commit'],
                 documentation_commit=args.commit, workflow_url=args.run_url,
                 prepared_at_utc=datetime.now(timezone.utc).isoformat(),
                 package=identity, public_entries=len(rows), verified_profiles=sorted(identity['profile_identities']),
                 known_product_defects=gate['known_product_defects'], product_functional_conformance_certified=False,
                 build_tools={name: importlib.metadata.version(name) for name in ('sphinx', 'myst-parser', 'pydata-sphinx-theme', 'sphinx-autoapi')})
    write_json(args.output / '_meta/build.json', build)
    write_json(exact / '_meta/build.json', build)
    write_json(args.output / 'versions.json', [dict(version=version, name=version + ' (beta)', url=SITE_PREFIX + version + '/')])
    for directory in (args.output, args.output / 'latest'):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'index.html').write_text(f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/svg+xml" href="{SITE_PREFIX}{version}/_static/favicon.svg">
<meta http-equiv="refresh" content="0; url={SITE_PREFIX}{version}/"><title>rsTimes {version} documentation</title>
<link rel="canonical" href="https://aresjef.github.io{SITE_PREFIX}{version}/"></head>
<body><main><h1>rsTimes {version} documentation</h1><p>Beta release.</p>
<p><a href="{SITE_PREFIX}{version}/">Open the English documentation</a></p></main></body></html>\n''')
    (args.output / '404.html').write_text(f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/svg+xml" href="{SITE_PREFIX}{version}/_static/favicon.svg">
<title>Page not found — rsTimes</title><style>body{{font:1rem/1.65 system-ui;margin:4rem auto;padding:0 1.25rem;max-width:44rem}}a:focus-visible{{outline:3px solid #176b94;outline-offset:3px}}</style></head>
<body><main><h1>Page not found</h1><p>The address may have changed. The current documentation covers rsTimes {version} (beta).</p>
<p><a href="{SITE_PREFIX}{version}/">Documentation home</a> · <a href="{SITE_PREFIX}{version}/api/index.html">API reference</a> · <a href="{SITE_PREFIX}{version}/search.html">Search</a></p></main></body></html>\n''')
    (args.output / '.nojekyll').write_text('')
    files = {p.relative_to(args.output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(args.output.rglob('*')) if p.is_file()}
    write_json(args.output / '_meta/files.json', dict(files=files))
    print(json.dumps({'version': version, 'public_entries': len(rows), 'files': len(files) + 1, 'output': str(args.output)}))


if __name__ == '__main__':
    main()
