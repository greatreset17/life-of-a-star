#!/usr/bin/env python3
"""Acquisition against the manifest. Fetches whatever is absent, verifies every
checksum, exits non-zero on any mismatch or any unpinned entry. No source, no
run: this script never synthesises, never substitutes, never proceeds past a
failure it can name.

  acquire.py            fetch + verify everything in the manifest
  acquire.py verify     verify only (no network)
"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from sources import MANIFEST, _sha256  # noqa: E402


def main(argv):
    verify_only = "verify" in argv
    # an explicit manifest path may be supplied (external substitution — the
    # harness exercises corruption behaviour on a COPY, never on the real one)
    paths = [a for a in argv if a.endswith(".json")]
    manifest_path = Path(paths[0]) if paths else MANIFEST
    entries = json.loads(manifest_path.read_text())["sources"]
    failures = []
    for name, e in entries.items():
        dest = ROOT / e["dest"]
        if e.get("per_file_manifest"):
            # a manifest-of-manifests: verify each listed file's checksum
            if not dest.exists():
                failures.append(f"{name}: nodes manifest absent ({e['dest']})")
                continue
            nodes = json.loads(dest.read_text())
            bad = 0
            for key, ne in nodes.items():
                p = ROOT / ne["file"]
                if not p.exists() or _sha256(p) != ne["sha256"]:
                    failures.append(f"{name}/{key}: absent or checksum mismatch")
                    bad += 1
                    if bad > 5:
                        failures.append(f"{name}: …further node failures suppressed")
                        break
            if bad == 0:
                print(f"ok    {name} ({len(nodes)} node files)")
            continue
        if not dest.exists():
            if verify_only:
                failures.append(f"{name}: file absent ({e['dest']})")
                continue
            print(f"fetch {name} <- {e['url']}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                req = urllib.request.Request(e["url"], headers={"User-Agent": "life-of-a-star acquisition"})
                with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
                    while chunk := r.read(1 << 20):
                        f.write(chunk)
            except Exception as ex:
                failures.append(f"{name}: retrieval failed ({ex})")
                continue
        declared = e.get("sha256", "")
        if declared in ("", "PENDING-PIN"):
            failures.append(f"{name}: checksum not pinned")
            continue
        actual = _sha256(dest)
        if actual != declared:
            failures.append(f"{name}: checksum mismatch (manifest {declared[:12]}…, actual {actual[:12]}…)")
            continue
        if "extracted_member" in e:
            m = ROOT / e["extracted_member"]
            if not m.exists():
                failures.append(f"{name}: extracted member absent ({e['extracted_member']})")
            elif _sha256(m) != e.get("extracted_sha256"):
                failures.append(f"{name}: extracted member checksum mismatch")
            else:
                print(f"ok    {name} (+ extracted member)")
                continue
        else:
            print(f"ok    {name}")
    if failures:
        print("\nACQUISITION FAILED — the pipeline must not run:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nacquisition: ALL VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
