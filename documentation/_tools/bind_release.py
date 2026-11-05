"""Bind installed-package verification to pinned public wheel ZIP bytes."""
from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import runpy
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def wheel_identity(path, release, inventory):
    expected = release['files'].get(path.name)
    if expected is None or expected['packagetype'] != 'bdist_wheel':
        raise ValueError('Wheel is absent from the pinned public release: ' + path.name)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected['sha256']:
        raise ValueError('Public wheel SHA mismatch: ' + path.name)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP member in public wheel')
        metadata_files = [n for n in names if n.endswith('.dist-info/METADATA')]
        if len(metadata_files) != 1:
            raise ValueError('Expected exactly one distribution metadata file')
        metadata = BytesParser().parsebytes(archive.read(metadata_files[0]))
        if metadata['Name'].lower() != 'rstimes' or metadata['Version'] != release['version']:
            raise ValueError('Wheel metadata differs from the pinned target release')
        payload = {n.removeprefix('rstimes/'): hashlib.sha256(archive.read(n)).hexdigest()
                   for n in names if n.startswith('rstimes/') and not n.endswith('/')}
    stubs = {n: value for n, value in payload.items() if n.endswith('.pyi')}
    if stubs != inventory['stubs'] or inventory['version'] != release['version']:
        raise ValueError('Public stub identity differs from the independent API inventory')
    return {
        'product_version': release['version'], 'wheel_filename': path.name,
        'wheel_sha256': digest, 'source_commit': release['source_commit'],
        'native': {n: value for n, value in payload.items() if n.endswith(('.so', '.pyd'))},
        'stubs': stubs, 'payload': payload,
        'expected_identity_basis': 'Pinned public-release SHA and raw ZIP members; installed bytes are compared separately.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--wheel', type=Path)
    source.add_argument('--wheel-dir', type=Path)
    parser.add_argument('--profile-wheel', action='append', nargs=2, default=[], metavar=('PROFILE', 'WHEEL'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check-wheel-only', action='store_true', help='Check pinned public bytes before installation; do not claim an installed-package check.')
    args = parser.parse_args()
    wheel = args.wheel
    if args.wheel_dir:
        wheels = list(args.wheel_dir.glob('*.whl'))
        if len(wheels) != 1:
            parser.error('--wheel-dir must contain exactly one product wheel; use --wheel for an explicit file')
        wheel = wheels[0]
    release = json.loads((ROOT / '_data/release.json').read_text())
    inventory = json.loads((ROOT / '_data/public-api.json').read_text())
    expected = wheel_identity(wheel, release, inventory)
    if not args.check_wheel_only:
        if args.output is None:
            parser.error('--output is required for an installed-package binding')
        actual = runpy.run_path(str(ROOT / '_tools/verify_examples.py'))['identity']()
        if actual['version'] != expected['product_version'] or any(actual[k] != expected[k] for k in ('native', 'stubs', 'payload')):
            parser.error('Installed package bytes differ from the pinned public wheel')
    expected['public_api_paths'] = [row['path'] for row in inventory['entries']]
    expected['profile_identities'] = {}
    profiles = json.loads((ROOT / '_data/profiles.json').read_text())['profiles']
    for profile, filename in args.profile_wheel:
        if profile not in profiles or profile in expected['profile_identities']:
            parser.error('Unknown or repeated profile-wheel binding: ' + profile)
        expected['profile_identities'][profile] = wheel_identity(Path(filename), release, inventory)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(expected, indent=2) + '\n')
    print(json.dumps({'version': expected['product_version'], 'wheel': wheel.name,
                      'package_members': len(expected['payload']), 'public_paths': len(expected['public_api_paths']),
                      'additional_abi_profiles': list(expected['profile_identities']),
                      'installed_package_verified': not args.check_wheel_only}))


if __name__ == '__main__':
    main()
