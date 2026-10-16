#!/usr/bin/env python3
"""Run W1/W5 real-WebGL lifecycle contracts through the existing CDP harness."""
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    expression = (ROOT / "tests/atlas_lifecycle_contract_browser.js").read_text()
    cmd = [sys.executable, "-s", "tests/headless.py",
           "data=data/sample-saga.json&probe=1&pump=1&warm=20", "--size", "800x600",
           "--eval", expression]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                         timeout=180, env=dict(os.environ, CL_TIMEOUT="120"))
    print(run.stdout)
    if run.stderr:
        print(run.stderr, file=sys.stderr)
    payload = None
    for line in run.stdout.splitlines():
        if line.startswith("EVAL:"):
            payload = json.loads(line.partition(":")[2].strip())
            if isinstance(payload, str):
                payload = json.loads(payload)
    if run.returncode or not payload or not payload.get("ok"):
        return 1
    print("ATLAS-LIFECYCLE-BROWSER OK · %d contracts" % payload["checks"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
