#!/usr/bin/env python3
"""Fetch the selected spectrum nodes from SVO, cut to the declared band
(SPECTRA_BAND_ANGSTROM), gzip, checksum into the nodes manifest.
Retries transient failures; exits non-zero if ANY node is missing at the end
(no-fallback: a partial grid stops the pipeline by name).

  fetch_spectra.py [--workers N]
"""
import gzip
import hashlib
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.constants import SPECTRA_BAND_ANGSTROM  # noqa: E402

SEL = ROOT / "data" / "raw" / "spectra_selection.json"
OUT = ROOT / "data" / "raw" / "spectra"
NODES_MANIFEST = OUT / "nodes_manifest.json"
BASE = "http://svo2.cab.inta-csic.es/theory/newov2/ssap.php"


def fetch_one(n):
    grid, teff, logg = n["grid"], n["teff"], n["logg"]
    dest = OUT / grid / f"t{teff:07.1f}_g{logg:+.2f}.txt.gz"
    if dest.exists():
        return n, dest, "cached"
    url = f"{BASE}?model={n['url'].split('model=')[1].split('&')[0]}&fid={n['fid']}&format=ascii"
    lo, hi = SPECTRA_BAND_ANGSTROM
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "life-of-a-star acquisition"})
            with urllib.request.urlopen(req, timeout=300) as r:
                raw = r.read().decode()
            lines = []
            for ln in raw.splitlines():
                if ln.startswith("#") or not ln.strip():
                    continue
                w = float(ln.split(None, 1)[0])
                if lo <= w <= hi:
                    lines.append(ln.strip())
            if len(lines) < 100:
                raise ValueError(f"only {len(lines)} in-band samples")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(dest, "wt") as f:
                f.write(f"# grid={grid} teff={teff} logg={logg} fid={n['fid']}\n")
                f.write(f"# source={url}\n# band_angstrom={lo},{hi}\n")
                f.write("\n".join(lines) + "\n")
            return n, dest, "fetched"
        except Exception as e:  # noqa: BLE001 — retried, then reported by name
            last = e
            time.sleep(5 * (attempt + 1))
    return n, None, f"FAILED: {last}"


def main(argv):
    workers = int(argv[argv.index("--workers") + 1]) if "--workers" in argv else 4
    sel = json.loads(SEL.read_text())
    nodes = sel["needed"]
    manifest = json.loads(NODES_MANIFEST.read_text()) if NODES_MANIFEST.exists() else {}
    failures = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fetch_one, n) for n in nodes]
        for fut in as_completed(futs):
            n, dest, status = fut.result()
            done += 1
            key = f"{n['grid']}/t{n['teff']:07.1f}_g{n['logg']:+.2f}"
            if dest is None:
                failures.append((key, status))
                print(f"[{done}/{len(nodes)}] {key}  {status}", flush=True)
                continue
            if status == "fetched" or key not in manifest:
                manifest[key] = {
                    "fid": n["fid"], "grid": n["grid"], "teff": n["teff"], "logg": n["logg"],
                    "file": str(dest.relative_to(ROOT)),
                    "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
                    "bytes": dest.stat().st_size, "retrieved": str(date.today()),
                }
            if done % 25 == 0 or status == "fetched":
                print(f"[{done}/{len(nodes)}] {key}  {status}", flush=True)
            if done % 25 == 0:
                NODES_MANIFEST.write_text(json.dumps(manifest, indent=0, sort_keys=True))
    NODES_MANIFEST.write_text(json.dumps(manifest, indent=0, sort_keys=True))
    if failures:
        print(f"\nFETCH INCOMPLETE — {len(failures)} node(s) missing; the pipeline must not run:")
        for k, s in failures:
            print(f"  {k}: {s}")
        return 1
    print(f"\nall {len(nodes)} nodes verified present")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
