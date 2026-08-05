#!/usr/bin/env python3
"""Build the per-EEP chromaticity table — the sole colour source for Stage 1.

For every EEP: interpolate the owning grid's spectra at the track's
(Teff, log g), convolve through the one colour chain, gamut-map (fork 1),
and emit:  eep, teff, logg, grid, dlogg_edge, xy, rgb_lin (mapped direction),
excursion.  Stage 1 reads this file and nothing else for colour.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import colour  # noqa: E402
from pipeline.constants import TABLE_FLOAT_DECIMALS  # noqa: E402
from pipeline.track import Track  # noqa: E402


def build():
    sel = json.loads((ROOT / "data" / "raw" / "spectra_selection.json").read_text())
    tr = Track.load()
    rows = []
    for p in sel["per_eep"]:
        wl, flux = colour.interp_spectrum(ROOT, p["grid"], p["cell"], p["teff"], p["logg"])
        xyz = colour.spectrum_to_xyz(wl, flux)
        xy = colour.xyz_to_xy(xyz)
        rgb, excursion = colour.gamut_map(xyz)
        # fork 35 — the eye is lit by what it can see: the V(lambda)-weighted
        # fraction of the SED (Y is already the CIE ybar integral; the ratio
        # against the SED's own bolometric integral is the piece's adaptation
        # weight). An ember radiating in the far infrared no longer holds
        # the eye. Ratio of integrals over the same grid: units cancel.
        f_vis = float(xyz[1] / max(np.trapezoid(flux, wl), 1e-300))
        rows.append({
            "eep": p["eep"],
            "teff": round(p["teff"], 2),
            "logg": round(p["logg"], 4),
            "grid": p["grid"],
            "dlogg_edge": p["dlogg_edge"],
            "xy": [round(v, TABLE_FLOAT_DECIMALS) for v in xy],
            "rgb_lin": [round(float(v), TABLE_FLOAT_DECIMALS) for v in rgb],
            "excursion": round(float(excursion), TABLE_FLOAT_DECIMALS),
            "f_vis": float(f"{f_vis:.6e}"),
        })
        if p["eep"] % 200 == 0:
            print(f"  eep {p['eep']}/{tr.n}  T={p['teff']:.0f} xy=({xy[0]:.4f},{xy[1]:.4f}) exc={excursion:.4f}", flush=True)
    out = ROOT / "data" / "derived"
    out.mkdir(parents=True, exist_ok=True)
    (out / "colour.json").write_text(json.dumps(
        {"source": "build_colour_table.py; chain: spectrum -> CIE1931-2deg -> XYZ -> linear sRGB -> Oklab gamut map (fork 1)",
         "rows": rows}, indent=0))
    print(f"colour table: {len(rows)} rows written")


if __name__ == "__main__":
    build()
