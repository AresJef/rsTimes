"""Check project-relative HTML links, anchors and the public artifact boundary."""
from __future__ import annotations

import argparse
import csv
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import runpy
from urllib.parse import unquote, urljoin, urlsplit

DOC = Path(__file__).resolve().parents[1]
BASE = 'https://aresjef.github.io/rsTimes/'
PREFIX = '/rsTimes/'


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links = set(), []
        self.canonical = []
        self.destination = None
        self.noindex = False
        self.fragments_text = []
        self.read_fragments = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get('id'):
            self.ids.add(attributes['id'])
        if tag == 'link' and attributes.get('rel') == 'canonical':
            self.canonical.append(attributes['href'])
        if tag == 'meta' and attributes.get('name') == 'robots':
            self.noindex = 'noindex' in attributes.get('content', '')
        if tag == 'a' and attributes.get('id') == 'documentation-destination':
            self.destination = attributes['href']
        if tag == 'script' and attributes.get('id') == 'documentation-fragments':
            self.read_fragments = True
        for name in ('href', 'src'):
            if attributes.get(name):
                self.links.append(attributes[name])

    def handle_data(self, data):
        if self.read_fragments:
            self.fragments_text.append(data)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.read_fragments = False


def site_path(path):
    target = unquote(path.removeprefix(PREFIX))
    return target + 'index.html' if not target or target.endswith('/') else target


def verify_receiver_exports(site, version, documents, hashes, problems):
    exact = site / version
    receiver_path = 'verification/receivers.json'
    if not (exact / receiver_path).is_file():
        problems.append('Missing the public example receiver index')
        return
    detailed = json.loads((exact / receiver_path).read_bytes())['cases']
    json_rows = json.loads((exact / 'verification/coverage.json').read_bytes())['records']
    csv_path = exact / 'verification/coverage.csv'
    # A verified entry can reference many receipts in its existing evidence cell.
    field_limit = csv.field_size_limit(csv_path.stat().st_size)
    try:
        with csv_path.open(newline='', encoding='utf-8') as file:
            csv_rows = list(csv.DictReader(file))
    finally:
        csv.field_size_limit(field_limit)
    if [row['entry'] for row in csv_rows] != [row['path'] for row in json_rows]:
        problems.append('The public CSV and JSON have different entry rows')
        return
    for csv_row, row in zip(csv_rows, json_rows):
        if (csv_row['receiver_index'] != row['receiver_index'] or row['receiver_index'] != receiver_path
                or csv_row['reader_status'] != row['reader_status']):
            problems.append(f'{row["path"]}: receiver pointers or reader status differ')
        for field in ('rendered_example_links', 'reader_witnesses', 'other_visible_witnesses', 'backend_witnesses'):
            if json.loads(csv_row[field]) != row[field]:
                problems.append(f'{row["path"]}: CSV/JSON disagree on {field}')
        for link in row['rendered_example_links']:
            if link['href'] != detailed[link['id']]['example_link']:
                problems.append(f'{row["path"]}: rendered example is missing its public deep link')
    for case, detail in detailed.items():
        report = version + '/' + detail['report']
        if hashes.get(report) != detail['report_sha256']:
            problems.append(f'{case}: published receiver receipt or checksum differs')
        if link := detail['example_link']:
            page, fragment = link.split('#', 1)
            document = documents.get(version + '/' + page)
            if document is None or fragment not in document.ids:
                problems.append(f'{case}: missing the public example anchor')
    counts = json.loads((exact / 'verification/execution-counts.json').read_bytes())
    for extra in counts['unregistered_successes']:
        if version + '/' + extra['report'] not in hashes:
            problems.append(f'{extra["case"]}: successful worker record is not accessible')


def verify_migration(site, documents, hashes, preview, problems):
    plan = json.loads((DOC / '_data/legacy-pages.json').read_text())
    build = json.loads((site / '_meta/build.json').read_text())
    mode = build['publication_stage']
    version = plan['version']
    legacy = plan['old_version']
    target = json.loads((DOC / 'target.json').read_text())
    active = target['version']
    previous_version = target.get('previous_version')
    default = target.get('default_version', active)
    if build['product_version'] != active or mode not in ('preserve', 'redirect'):
        problems.append('Unexpected released identity or archive stage')
    if build['acceptance'] != ('preview' if preview else 'ci'):
        problems.append('A preview cannot serve as a verified production artifact')
    if not preview and build['pending_case_profiles']:
        problems.append('Incomplete example coverage')
    expected_versions = [active, previous_version] if previous_version else [active]
    expected_versions.sort(key=lambda item: item != default)
    if mode == 'preserve':
        expected_versions.append(legacy)
    version_rows = json.loads((site / 'versions.json').read_text())
    versions = [row['version'] for row in version_rows]
    if (versions != expected_versions
            or any(row['url'] != PREFIX + row['version'] + '/' for row in version_rows)):
        problems.append('Version selector differs from the current stage')
    choices = documents.get('versions.html')
    if not choices or set(choices.links) != {PREFIX + item + '/' for item in expected_versions}:
        problems.append('Version choices do not link to the exact versions')
    if previous_version:
        previous = json.loads((DOC / '_data/previous-site.json').read_text())
        retained = {name: digest for name, digest in hashes.items() if name.startswith(previous_version + '/')}
        if previous['old_version'] != previous_version or retained != previous['old_files']:
            problems.append('The previous exact-version site differs from the verified archive')
        if (build.get('default_documentation_version') != default
                or build.get('exact_versions') != {
                    item: PREFIX + item + '/_meta/build.json' for item in (active, previous_version)
                }):
            problems.append('Versioned build evidence pointers do not match the site default')
    receipts = {name: plan['old_files'][name] for name in plan['retained_evidence']}
    archive_info = json.loads((site / '_meta/legacy-evidence.json').read_text())
    if (archive_info['version'] != legacy or archive_info['files'] != receipts
            or archive_info['archive_sha256'] != plan['archive']['sha256']):
        problems.append('Historical evidence lost its original identity')
    expected_old = ({name: value for name, value in plan['old_files'].items() if name.startswith(legacy + '/')}
                    if mode == 'preserve' else receipts)
    old_paths = {name for name in hashes if name.startswith(legacy + '/')}
    if mode == 'redirect':
        old_paths -= plan['pages'].keys()
    if old_paths != expected_old.keys() or any(hashes.get(name) != value for name, value in expected_old.items()):
        problems.append('Preserved historical files differ from the verified old snapshot')
    for name in ('index.html', 'latest/index.html'):
        if documents[name].destination != PREFIX + default + '/':
            problems.append('Incorrect current entry point: ' + name)
    if documents['404.html'].destination or 'Page not found' not in (site / '404.html').read_text():
        problems.append('Missing dedicated 404 page')
    for name, doc in documents.items():
        exact = next((item for item in (active, previous_version) if item and name.startswith(item + '/')), None)
        if exact and any(not url.startswith(BASE + exact + '/') for url in doc.canonical):
            problems.append('Canonical URL leaves its exact version: ' + name)
    if mode != 'redirect':
        return dict(stage=mode, old_body_pages=len(plan['pages']), historical_receipts=len(receipts))

    manifest = json.loads((site / version / 'verification/legacy-redirects.json').read_text())
    if manifest != dict(from_version=legacy, to_version=version, pages=plan['pages']):
        problems.append('Public redirect table differs from the planned mapping')
    count = 0
    for name, route in plan['pages'].items():
        source = documents.get(name)
        expected_canonical = BASE.removesuffix(PREFIX) + route['target'].split('#', 1)[0]
        if (not source or not source.noindex or source.destination != route['target']
                or source.canonical != [expected_canonical]
                or PREFIX + '_routing/moved.js' not in source.links
                or json.loads(''.join(source.fragments_text)) != route['fragments']):
            problems.append('Incorrect legacy redirect page: ' + name)
        for target in [route['target'], *route['fragments'].values()]:
            parsed = urlsplit(target)
            location = site_path(parsed.path)
            landing = documents.get(location)
            if (parsed.scheme or parsed.netloc or not parsed.path.startswith(PREFIX + version + '/')
                    or not landing or landing.destination
                    or (parsed.fragment and unquote(parsed.fragment) not in landing.ids)):
                problems.append(f'{name}: invalid or cyclic migration target {target}')
        count += len(route['fragments'])
    return dict(stage=mode, old_body_pages=0, migrated_pages=len(plan['pages']),
                mapped_fragments=count, historical_receipts=len(receipts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    documents, hashes, problems, external = {}, {}, [], set()
    files = sorted(p for p in args.site.rglob('*') if p.is_file())
    suffixes = {'.html', '.css', '.js', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.eot', '.json', '.inv', '.txt', '.csv', '.xml', '.map'}
    for path in files:
        relative = path.relative_to(args.site)
        content = path.read_bytes()
        if relative.as_posix() != '_meta/files.json':
            hashes[relative.as_posix()] = hashlib.sha256(content).hexdigest()
        if path.is_symlink() or any(part.startswith('.') for part in relative.parts) and relative.as_posix() != '.nojekyll':
            problems.append('Private or linked artifact path: ' + relative.as_posix())
        if relative.as_posix() != '.nojekyll' and path.suffix not in suffixes:
            problems.append('Unexpected public artifact type: ' + relative.as_posix())
        if path.suffix in ('.html', '.json', '.csv', '.txt', '.js', '.css'):
            if any(marker in content for marker in (b'/Users/jef/', b'/home/runner/', b'D:\\a\\', b'file:///')):
                problems.append('Workstation/runner path leaked into artifact: ' + relative.as_posix())
        if path.suffix == '.html':
            document = Document()
            document.feed(path.read_text())
            documents[relative.as_posix()] = document
    checked = 0
    for source, document in documents.items():
        for link in document.links:
            parsed = urlsplit(urljoin(BASE + source, link))
            if parsed.scheme not in ('http', 'https'):
                continue
            if parsed.netloc != 'aresjef.github.io' or not parsed.path.startswith('/rsTimes/'):
                external.add(parsed._replace(fragment='').geturl())
                continue
            target = site_path(parsed.path)
            destination = args.site / target
            checked += 1
            if not destination.is_file():
                problems.append(f'{source}: missing target {link}')
            elif parsed.fragment and target in documents and unquote(parsed.fragment) not in documents[target].ids:
                problems.append(f'{source}: missing anchor {link}')
    recorded = json.loads((args.site / '_meta/files.json').read_text())['files']
    if recorded != hashes:
        problems.append('Packaged site files differ from their checksums')
    migration = verify_migration(args.site, documents, hashes, args.preview, problems)
    target = json.loads((DOC / 'target.json').read_text())
    upgrade = args.site / target['version'] / 'compatibility/migration.html'
    check_upgrade = runpy.run_path(str(DOC / '_tools/check_upgrade.py'))['check_upgrade']
    try:
        check_upgrade(upgrade.read_text(encoding='utf-8'), target['version'])
    except ValueError as error:
        problems.append(str(error))
    verify_receiver_exports(args.site, target['version'], documents, hashes, problems)
    result = dict(status='fail' if problems else 'pass', files=len(files), html_pages=len(documents),
                  internal_links_checked=checked, external_links=sorted(external), problems=problems,
                  migration=migration, preview=args.preview)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'external_links'}))
    return int(bool(problems))


if __name__ == '__main__':
    raise SystemExit(main())
