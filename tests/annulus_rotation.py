#!/usr/bin/env python3
"""Multi-angle real-WebGL annulus registration and pointer-hit regression."""
import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default='data/sample-saga.json')
    parser.add_argument('--size', default='1200x800')
    args = parser.parse_args()
    expression = (ROOT / 'tests/annulus_rotation_browser.js').read_text()
    run = subprocess.run([sys.executable, '-s', 'tests/headless.py',
                          'data=' + args.data + '&plot=1&probe=1&pump=1&warm=15',
                          '--size', args.size, '--eval', expression],
                         cwd=ROOT, capture_output=True, text=True, timeout=180)
    print(run.stdout)
    if run.stderr:
        print(run.stderr, file=sys.stderr)
    result = None
    for line in run.stdout.splitlines():
        if line.startswith('EVAL:'):
            try:
                result = json.loads(line.partition(':')[2].strip())
            except json.JSONDecodeError:
                continue
            if isinstance(result, str):
                result = json.loads(result)
    if run.returncode or not result or not result.get('ok'):
        return 1
    print('ANNULUS-ROTATION OK · %d checks · %d camera/spin poses' %
          (result['checks'], len(result['poses'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
