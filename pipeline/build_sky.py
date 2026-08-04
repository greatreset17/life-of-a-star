#!/usr/bin/env python3
"""Build the sky tables: star catalogue with chain-derived colours, orbit
positions at the output epochs (f32 binary), the Sun's own galactic orbit
sampled on the spine, and the Milky Way band map (same 3-band chain).

Outputs:
  app/data/sky.json           meta + per-star colour/brightness/scotopic
  app/data/sky_positions.bin  f32 [n_epoch][n_star][3] galactocentric pc
  app/data/sun_orbit.bin      f32 [n_spine][3]
  app/data/band.json          healpix-5 cells: direction, rgb, luminance
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import colour, sky  # noqa: E402
from pipeline.cooling import CoolingSpine  # noqa: E402
from pipeline.track import Track  # noqa: E402

PRESENT_AGE_YR = 4.57e9


def epoch_grid(age_min, age_max):
    """Signed Myr offsets from the present: dense near zero (constellation
    dissolution), coarse over Gyr (galactic orbits)."""
    near = [0.0, 0.05, 0.15, 0.4, 1.0, 3.0, 10.0, 30.0, 100.0]
    far_fw = list(np.arange(300.0, (age_max - PRESENT_AGE_YR) / 1e6 + 300.0, 300.0))
    far_bw = list(-np.arange(300.0, (PRESENT_AGE_YR - age_min) / 1e6 + 300.0, 300.0))
    eps = sorted(set([-v for v in near] + near + far_fw + far_bw))
    return np.array(eps)


def build():
    tr = Track.load()
    cs = CoolingSpine.build(tr)
    rows, excluded = sky.load_catalog(ROOT)
    pos0, vel0, n_rv = sky.to_galactocentric(rows)
    print(f"catalogue: {len(rows)} stars ({sum(1 for r in rows if r['src'] == 'hip')} Hipparcos), "
          f"excluded {excluded}, RV for {n_rv}")

    # colours through the one chain
    rgbs, scot = [], []
    for r in rows:
        rgb, exc, sp = sky.star_chromaticity(r["sed"])
        rgbs.append([round(float(v), 5) for v in rgb])
        scot.append(round(float(sp), 5))

    t_out = epoch_grid(cs.age_yr[0], cs.age_yr[-1])
    print(f"integrating {len(rows)} orbits over {len(t_out)} epochs "
          f"({t_out[0]:.0f}..{t_out[-1]:.0f} Myr)")
    pos_epochs = sky.integrate_orbits(pos0, vel0, t_out)

    # the Sun's own orbit, sampled at every spine node
    sun0 = np.array([[-sky.R0_PC, 0.0, sky.Z_SUN_PC]])
    sunv = np.array([[sky.V_SUN[0], sky.V_SUN[1], sky.V_SUN[2]]])
    t_spine_myr = (cs.age_yr - PRESENT_AGE_YR) / 1e6
    # sample the sun densely on its own grid then interp to spine nodes
    t_sun = np.unique(np.concatenate([t_out, np.linspace(t_spine_myr[0], t_spine_myr[-1], 4096)]))
    sun_pos = sky.integrate_orbits(sun0, sunv, t_sun)[:, 0, :]
    sun_spine = np.stack([np.interp(t_spine_myr, t_sun, sun_pos[:, k]) for k in range(3)], axis=1)

    # solar galactic period for the suite: recross of azimuth
    phi = np.unwrap(np.arctan2(sun_pos[:, 1], sun_pos[:, 0]))
    total_turns = abs(phi[-1] - phi[0]) / (2 * np.pi)
    period = (t_sun[-1] - t_sun[0]) / total_turns
    print(f"solar orbit: {total_turns:.1f} circuits, period {period:.1f} Myr")

    # energy / L_z drift over the forward span (suite test 28)
    e0, lz0 = sky.energy_lz(pos0, vel0)

    (ROOT / "app" / "data" / "sky_positions.bin").write_bytes(
        pos_epochs.astype("<f4").tobytes())
    (ROOT / "app" / "data" / "sun_orbit.bin").write_bytes(
        sun_spine.astype("<f4").tobytes())
    # the Sun ON THE SAME EPOCH GRID as the stars: heliocentric directions
    # must subtract a Sun interpolated with the same (lo, f) as the star
    # positions — a spine-node Sun is up to 1/6 of an orbit (kpc) off the
    # true path between MS nodes and collapses every direction (measured)
    sun_epochs = np.stack([np.interp(t_out, t_sun, sun_pos[:, k]) for k in range(3)], axis=1)
    (ROOT / "app" / "data" / "sun_epochs.bin").write_bytes(
        sun_epochs.astype("<f4").tobytes())

    meta = {
        "n_star": len(rows), "n_epoch": len(t_out),
        "epochs_myr": [round(float(v), 4) for v in t_out],
        "present_age_yr": PRESENT_AGE_YR,
        "excluded": excluded, "n_rv": n_rv,
        "solar_period_myr": round(float(period), 1),
        "solar_circuits": round(float(total_turns), 2),
        "gmag": [round(r["gmag"], 3) for r in rows],
        "rgb_lin": rgbs,
        "scotopic_factor": scot,
        "src": [r["src"] for r in rows],
    }
    (ROOT / "app" / "data" / "sky.json").write_text(json.dumps(meta, indent=0))

    # Milky Way band: healpix-5 aggregate through the same chain
    cells = []
    import csv as _csv
    with open(ROOT / "data/raw/gaia/band_hpx5.csv") as f:
        for r in _csv.DictReader(f):
            sed = {"G": float(r["gflux"]), "BP": float(r["bpflux"]), "RP": float(r["rpflux"])}
            rgb, _, sp = sky.star_chromaticity(sed)
            cells.append({"hpx": int(r["hpx"]), "n": int(r["n"]),
                          "gflux": float(r["gflux"]),
                          "rgb": [round(float(v), 4) for v in rgb],
                          "scot": round(float(sp), 4)})
    (ROOT / "app" / "data" / "band.json").write_text(json.dumps(
        {"nside": 32, "cells": cells}, indent=0))
    print(f"band map: {len(cells)} cells")
    # identity copies
    (ROOT / "data" / "derived" / "sky_meta.json").write_text(json.dumps(
        {"n_star": len(rows), "excluded": excluded, "solar_period_myr": meta["solar_period_myr"],
         "e_lz_sample": [float(e0[0]), float(lz0[0])]}, indent=0))


if __name__ == "__main__":
    build()
