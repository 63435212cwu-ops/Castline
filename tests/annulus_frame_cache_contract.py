#!/usr/bin/env python3
"""Real-WebGL frame-cache equivalence and frozen DOM work contract."""
import argparse
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default='data/sample-saga.json')
    parser.add_argument('--size', default='1000x720')
    args = parser.parse_args()
    expression = (ROOT / "tests/annulus_frame_cache_browser.js").read_text()
    cmd = [sys.executable, "-s", "tests/headless.py",
           "data=" + args.data + "&plot=1&probe=1&pump=1&warm=20", "--size", args.size,
           "--eval", expression]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                         timeout=180, env=dict(os.environ, CL_TIMEOUT="120"))
    print(run.stdout)
    if run.stderr:
        print(run.stderr, file=sys.stderr)
    result = None
    for line in run.stdout.splitlines():
        if line.startswith("EVAL:"):
            result = json.loads(line.partition(":")[2].strip())
            if isinstance(result, str):
                result = json.loads(result)
    if run.returncode or not result or not result.get("ok"):
        return 1
    print("ANNULUS-FRAME-CACHE-BROWSER OK · %d contracts · frozen %.3fms · moving %.3fms" %
          (result["checks"], result["frozenMs"], result["movingMs"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
