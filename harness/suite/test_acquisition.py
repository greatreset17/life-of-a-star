#!/usr/bin/env python3
"""Suite test 35 — acquisition integrity. Corruption and removal are
exercised on a COPY of the manifest in the scratch area; no verification
path writes to real state.

 - corrupted checksum -> acquire.py verify exits non-zero naming the source
 - removed entry -> sources.require raises SourceUnavailable naming it
 - intact manifest -> verify exits zero
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
PY = ROOT / ".venv" / "bin" / "python"

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


manifest = json.loads((ROOT / "pipeline" / "manifest.json").read_text())

with tempfile.TemporaryDirectory() as td:
    # intact
    p_ok = Path(td) / "ok.json"
    p_ok.write_text(json.dumps(manifest))
    r = subprocess.run([str(PY), "pipeline/acquire.py", "verify", str(p_ok)],
                       cwd=ROOT, capture_output=True, text=True)
    check("t35-intact-verifies", r.returncode == 0, r.stdout[-300:])

    # corrupted checksum
    bad = json.loads(json.dumps(manifest))
    bad["sources"]["cie_cmf"]["sha256"] = "0" * 64
    p_bad = Path(td) / "bad.json"
    p_bad.write_text(json.dumps(bad))
    r = subprocess.run([str(PY), "pipeline/acquire.py", "verify", str(p_bad)],
                       cwd=ROOT, capture_output=True, text=True)
    check("t35-corrupt-checksum-fails", r.returncode != 0 and "cie_cmf" in r.stdout,
          f"rc={r.returncode}")

# removed entry -> pipeline names the missing source (sources.require path)
import importlib  # noqa: E402

from pipeline import sources  # noqa: E402

orig = sources.MANIFEST
try:
    with tempfile.TemporaryDirectory() as td2:
        cut = json.loads(json.dumps(manifest))
        del cut["sources"]["mist_track_1p0"]
        p_cut = Path(td2) / "cut.json"
        p_cut.write_text(json.dumps(cut))
        sources.MANIFEST = p_cut
        try:
            sources.require("mist_track_1p0", extracted=True)
            check("t35-removed-entry-named", False, "require did not raise")
        except sources.SourceUnavailable as e:
            check("t35-removed-entry-named",
                  "mist_track_1p0" in str(e) and "no manifest entry" in str(e), str(e))
finally:
    sources.MANIFEST = orig
    importlib.reload(sources)

print(f"\nacquisition suite: {'ALL GREEN' if not failures else f'{len(failures)} FAILURE(S)'}")
sys.exit(1 if failures else 0)
