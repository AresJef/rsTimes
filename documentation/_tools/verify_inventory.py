"""Compare an actual installed public surface with its independent frozen list."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import runpy

DOC = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projection', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    expected = json.loads((DOC / '_data/public-api.json').read_text())
    actual = runpy.run_path(str(DOC / '_tools/inventory.py'))['inventory']()
    expected_paths = {r['path'] for r in expected['entries']
                      if args.projection in r['dependency_profiles_available']}
    if not expected_paths:
        parser.error('Unknown frozen public-surface projection')
    actual_paths = {r['path'] for r in actual['rows']}
    missing = sorted(expected_paths - actual_paths)
    unexpected = sorted(actual_paths - expected_paths)
    invalid = sorted(r['path'] for r in actual['rows'] if not r['runtime_present'])
    identity_match = actual['product_version'] == expected['version'] and actual['stubs'] == expected['stubs']
    result = dict(projection=args.projection, product_version=actual['product_version'],
                  python=actual['python'], dependencies=actual['dependencies'],
                  expected_entries=len(expected_paths), actual_entries=len(actual_paths),
                  missing=missing, unexpected=unexpected, runtime_absent=invalid,
                  public_stub_identity_matches=identity_match,
                  status='pass' if identity_match and not (missing or unexpected or invalid) else 'fail')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return int(result['status'] != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
