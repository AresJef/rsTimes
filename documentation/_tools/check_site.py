"""Check project-relative HTML links, anchors and the public artifact boundary."""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links = set(), []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get('id'):
            self.ids.add(attributes['id'])
        for name in ('href', 'src'):
            if attributes.get(name):
                self.links.append(attributes[name])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    base = 'https://aresjef.github.io/rsTimes/'
    documents, problems, external = {}, [], set()
    files = sorted(p for p in args.site.rglob('*') if p.is_file())
    suffixes = {'.html', '.css', '.js', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.eot', '.json', '.inv', '.txt', '.csv', '.xml', '.map'}
    for path in files:
        relative = path.relative_to(args.site)
        if path.is_symlink() or any(part.startswith('.') for part in relative.parts) and relative.as_posix() != '.nojekyll':
            problems.append('Private or linked artifact path: ' + relative.as_posix())
        if relative.as_posix() != '.nojekyll' and path.suffix not in suffixes:
            problems.append('Unexpected public artifact type: ' + relative.as_posix())
        if path.suffix in ('.html', '.json', '.csv', '.txt', '.js', '.css'):
            content = path.read_bytes()
            if any(marker in content for marker in (b'/Users/jef/', b'/home/runner/', b'D:\\a\\', b'file:///')):
                problems.append('Workstation/runner path leaked into artifact: ' + relative.as_posix())
        if path.suffix == '.html':
            document = Document()
            document.feed(path.read_text())
            documents[relative.as_posix()] = document
    checked = 0
    for source, document in documents.items():
        for link in document.links:
            parsed = urlsplit(urljoin(base + source, link))
            if parsed.scheme not in ('http', 'https'):
                continue
            if parsed.netloc != 'aresjef.github.io' or not parsed.path.startswith('/rsTimes/'):
                external.add(parsed._replace(fragment='').geturl())
                continue
            target = unquote(parsed.path.removeprefix('/rsTimes/'))
            if not target or target.endswith('/'):
                target += 'index.html'
            destination = args.site / target
            checked += 1
            if not destination.is_file():
                problems.append(f'{source}: missing target {link}')
            elif parsed.fragment and target in documents and unquote(parsed.fragment) not in documents[target].ids:
                problems.append(f'{source}: missing anchor {link}')
    result = dict(status='fail' if problems else 'pass', files=len(files), html_pages=len(documents),
                  internal_links_checked=checked, external_links=sorted(external), problems=problems)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'external_links'}))
    return int(bool(problems))


if __name__ == '__main__':
    raise SystemExit(main())
