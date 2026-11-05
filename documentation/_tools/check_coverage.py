"""Check explicit entry/example/report links; partial slices never authorize publication."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import runpy

ROOT = Path(__file__).resolve().parents[1]


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        self.ids.update(value for name, value in attrs if name == 'id')


def sha(content):
    return hashlib.sha256(content).hexdigest()


def report_matches_profile(report, identity, profiles, verifier_sha):
    """Bind package bytes, actual dependency presence/versions and interpreter state."""
    actual = report['identity']
    if actual.get('import_location_verified') is not True:
        return False
    reference = identity.get('profile_identities', {}).get(report['profile'], identity)
    if actual.get('version') != reference['product_version']:
        return False
    if any(actual.get(k) != reference[k] for k in ('native', 'stubs', 'payload')):
        return False
    spec = profiles.get(report['profile'])
    if not spec or actual.get('python_minor') != spec['python_minor'] or actual.get('gil_enabled') is not spec['gil_enabled']:
        return False
    dependencies = {name: value for name, value in spec['dependencies'].items() if value is not None}
    return actual.get('dependencies') == dependencies and report.get('verifier_sha256') == verifier_sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports', type=Path, required=True)
    parser.add_argument('--identity', type=Path, required=True)
    parser.add_argument('--html-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--slice', choices=('all', 'core'), default='all')
    parser.add_argument('--allow-candidate', action='store_true')
    args = parser.parse_args()
    inventory = json.loads((ROOT / '_data/coverage.json').read_text())
    manifest = json.loads((ROOT / '_data/examples.json').read_text())
    target = json.loads((ROOT / 'target.json').read_text())
    identity = json.loads(args.identity.read_text())
    profile_specs = json.loads((ROOT / '_data/profiles.json').read_text())['profiles']
    verifier_sha = sha((ROOT / '_tools/verify_examples.py').read_bytes())
    duplicates = [path for path, count in Counter(e['path'] for e in inventory['entries']).items() if count > 1]
    if duplicates:
        parser.error('Duplicate canonical public paths in coverage table: ' + ', '.join(duplicates))
    if len(identity['public_api_paths']) != len(set(identity['public_api_paths'])):
        parser.error('The frozen public inventory contains duplicate canonical paths.')
    problems, records = [], []
    integrity = runpy.run_path(str(ROOT / '_tools/build_integrity.py'))
    build_problem = None
    build_file = args.html_dir / '_build-info.json'
    if not build_file.exists():
        build_problem = 'Current HTML build manifest missing; rebuild with the documentation integrity hooks.'
    else:
        build = json.loads(build_file.read_text())
        if not build.get('complete') or build['source_inputs'] != integrity['source_inputs'](ROOT):
            build_problem = 'HTML build does not match current documentation inputs.'
        elif build['outputs'] != integrity['html_outputs'](args.html_dir):
            build_problem = 'HTML output hashes differ from the completed build.'
        elif any(build['installed_package'].get(k) != identity[k] for k in ('product_version', 'native', 'stubs', 'payload')):
            build_problem = 'Rendered API extraction differs from the verified installed package.'
    if build_problem:
        problems.append(build_problem)
    if not args.allow_candidate and (target['status'] != 'released' or not target['publication_allowed']):
        problems.append('The final public release has not been bound; publication is prohibited.')
    if not args.allow_candidate and target['version'] != identity['product_version']:
        problems.append('The website version and tested package version differ.')
    if set(e['path'] for e in inventory['entries']) != set(identity['public_api_paths']):
        problems.append('The coverage table differs from the frozen runtime/stub public inventory.')
    examples = {e['id']: e for e in manifest['examples']}
    if len(examples) != len(manifest['examples']):
        problems.append('Example IDs must be globally unique.')
    missing_profiles = {p for e in manifest['examples'] for p in e['profiles']} - profile_specs.keys()
    if missing_profiles:
        problems.append('Undeclared execution profiles: ' + ', '.join(sorted(missing_profiles)))
    reports = []
    for path in args.reports.rglob('*.md.json'):
        report = json.loads(path.read_text())
        source = ROOT / report['page']
        if not source.exists() or report['page_sha256'] != sha(source.read_bytes()):
            continue  # Historical changed-page evidence is retained but not reused.
        if not report_matches_profile(report, identity, profile_specs, verifier_sha):
            continue
        reports.append((path, report))
    anchors = {}
    selected = [e for e in inventory['entries'] if args.slice == 'all' or e['owner'] in ('rstimes.Delta', 'rstimes.Configs', 'rstimes') or e['owner'].startswith('rstimes.errors.')]
    for entry in selected:
        entry_problems = []
        if build_problem:
            entry_problems.append(build_problem)
        if not entry['description_reviewed'] or entry['status'] not in ('candidate_examples_passed', 'verified', 'reviewed_pending_full_gate'):
            entry_problems.append('description/scenario review incomplete')
        if not entry['examples']:
            entry_problems.append('no example mapping')
        page = args.html_dir / (entry['page'] + '.html')
        if page not in anchors:
            dom = Anchors()
            if page.exists():
                dom.feed(page.read_text())
            anchors[page] = dom.ids
        if entry['anchor'] not in anchors[page]:
            entry_problems.append('rendered public anchor missing')
        evidence = []
        for issue in entry.get('known_issue_ids', []):
            reproductions = [examples.get(identifier, {}) for identifier in entry['examples']]
            if not any(e.get('verification_role') == 'known-defect-reproduction' and issue in e.get('known_issue_ids', []) for e in reproductions):
                entry_problems.append(f'labelled known-defect reproduction missing: {issue}')
            issue_page = args.html_dir / (entry.get('known_issue_page', '') + '.html')
            if not issue_page.exists() or issue not in issue_page.read_text():
                entry_problems.append(f'rendered known-defect disclosure missing: {issue}')
        for example_id in entry['examples']:
            example = examples.get(example_id)
            if example is None or entry['path'] not in example['covers']:
                entry_problems.append(f'invalid mapping: {example_id}')
                continue
            text = (ROOT / example['page']).read_text()
            pattern = r'^```\{doctest\}\s+' + re.escape(example_id) + r'\n(.*?)^```\s*$'
            block = re.search(pattern, text, re.M | re.S)
            if block is None:
                entry_problems.append(f'actual page block missing: {example_id}')
                continue
            code_hash = sha(block[1].encode())
            for profile in example['profiles']:
                applicable = [(p, r) for p, r in reports if r['page'] == example['page'] and r['profile'] == profile and any(g['id'] == example_id and g['sha256'] == code_hash for g in r['groups'])]
                if not applicable or any(r['status'] != 'pass' or r['failures'] for _, r in applicable):
                    entry_problems.append(f'current passing report missing or contradicted: {example_id}/{profile}')
                else:
                    evidence.append({'example': example_id, 'profile': profile, 'report': str(applicable[-1][0]), 'page_sha256': applicable[-1][1]['page_sha256'], 'code_sha256': code_hash})
        if entry_problems:
            problems.append({'path': entry['path'], 'problems': entry_problems})
        records.append({'path': entry['path'], 'page': entry['page'], 'anchor': entry['anchor'], 'scenarios': entry.get('scenarios', []), 'evidence': evidence, 'known_issue_ids': entry.get('known_issue_ids', []), 'product_conformance': entry.get('product_conformance', 'not-certified-by-documentation-check'), 'status': 'fail' if entry_problems else 'candidate_pass' if args.allow_candidate else 'pass'})
    known = sorted({issue for record in records for issue in record['known_issue_ids']})
    result = {'at_utc': datetime.now(timezone.utc).isoformat(), 'slice': args.slice, 'candidate_only': args.allow_candidate, 'verification_scope': 'Documentation descriptions, actual examples, identities and rendered links; labelled rsTimes defect reproductions are not product functional passes.', 'product_functional_conformance_certified': False, 'known_product_defects': known, 'publication_authorized_by_this_result': args.slice == 'all' and not args.allow_candidate and not problems, 'entries': len(selected), 'passed': sum(r['status'] != 'fail' for r in records), 'problems': problems, 'records': records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}))
    return int(bool(problems))


if __name__ == '__main__':
    raise SystemExit(main())
