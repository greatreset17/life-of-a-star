#!/usr/bin/env python3
"""Harness orchestrator.

  run.py selftest     physics-mirror known-answer tests
  run.py static       static checks over shipping source
  run.py suite        full test suite for the passes built so far
  run.py all          everything above

Exit code is the verdict. The suite is the judge.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "bin" / "python"


def run(name, cmd):
    print(f"\n=== {name} ===")
    r = subprocess.run(cmd, cwd=ROOT)
    return r.returncode


def main(argv):
    what = argv[0] if argv else "all"
    codes = []
    if what in ("selftest", "all"):
        codes.append(run("mirror selftest", [str(PY), "harness/mirror.py", "selftest"]))
    if what in ("static", "all"):
        codes.append(run("static checks", [str(PY), "harness/static_checks.py", "all"]))
    if what in ("suite", "all"):
        suite = ROOT / "harness" / "suite"
        if suite.exists():
            for t in sorted(suite.glob("test_*.py")):
                codes.append(run(t.stem, [str(PY), str(t)]))
        else:
            print("\n(no suite tests yet)")
    bad = sum(1 for c in codes if c != 0)
    print(f"\nharness: {'ALL GREEN' if not bad else f'{bad} SECTION(S) FAILED'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
