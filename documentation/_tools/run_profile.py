"""Run every complete page declared for one documentation dependency profile."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / '_data/examples.json').read_text())
    profiles = {p for example in manifest['examples'] for p in example['profiles']}
    if args.profile not in profiles:
        parser.error('Unknown profile: ' + args.profile)
    pages = sorted({e['page'] for e in manifest['examples'] if args.profile in e['profiles']})
    return subprocess.run([
        sys.executable, '-I', str(ROOT / '_tools/verify_examples.py'),
        *[str(ROOT / page) for page in pages], '--profile', args.profile,
        '--evidence-dir', str(args.evidence_dir.resolve()),
    ], check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
