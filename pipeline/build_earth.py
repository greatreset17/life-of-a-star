#!/usr/bin/env python3
"""Build the Earth-orbit table for Stage 1: both runs (drag on/off), the
engulfment events, and the mass-loss prescription comparison. All numbers
come out of pipeline/earth.py's integration of the track's own mass history.

Output app/data/earth.json:
  s_grid          slider positions for the curve samples (via age -> EEP -> s)
  a_drag_au       Earth semi-major axis, full physics
  a_nodrag_au     Earth semi-major axis, mass loss only (fork 21 meaning)
  r_star_au       photospheric radius on the same grid
  engulf_drag     { t_yr, s, a_au }   solved event, drag on
  engulf_nodrag   { t_yr, s, a_au }   solved event, drag off
  mdot_track      per-EEP track mass-loss rate (Msun/yr)
  mdot_sc05       per-EEP Schroeder & Cuntz 2005 comparison rate
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.arclength import ArcLength  # noqa: E402
from pipeline.constants import AU_M, R_SUN_M, TABLE_FLOAT_DECIMALS  # noqa: E402
from pipeline.earth import EarthOrbit, sc05_rate  # noqa: E402
from pipeline.track import Track  # noqa: E402

R = TABLE_FLOAT_DECIMALS


def rr(a):
    return [round(float(v), R) for v in np.asarray(a, float)]


def build():
    tr = Track.load()
    al = ArcLength.from_track(tr)
    eo = EarthOrbit(tr)
    ages = tr.col("star_age")

    def s_of_age(t_yr):
        eep = 1.0 + np.interp(t_yr, ages, np.arange(tr.n))
        return al.s_of_eep(np.atleast_1d(eep))

    res_d = eo.integrate(drag=True)
    res_n = eo.integrate(drag=False)

    # a common slider grid: the no-drag run's output grid (it runs longest),
    # extended to the end of the track — the star's curve continues after
    # both Earths are gone; the orbit curves read null there (absence drawn
    # as absence)
    t_last = res_n["t_yr"][-1]
    t_ext = ages[ages > t_last]
    t_grid = np.concatenate([res_n["t_yr"], t_ext])
    s_grid = s_of_age(t_grid)
    a_drag = np.interp(t_grid, res_d["t_yr"], res_d["a_yr"],
                       right=float("nan"))
    # beyond its engulfment the drag orbit no longer exists: NaN, drawn as
    # absence (a blank is information)
    a_drag[t_grid > (res_d["t_engulf_yr"] or t_grid[-1])] = float("nan")
    a_nodrag = np.interp(t_grid, res_n["t_yr"], res_n["a_yr"], right=float("nan"))
    a_nodrag[t_grid > (res_n["t_engulf_yr"] or t_grid[-1])] = float("nan")
    r_star_au = 10 ** np.interp(t_grid, ages, tr.col("log_R")) * R_SUN_M / AU_M

    def event(res):
        if not res["engulfed"]:
            return None
        t = res["t_engulf_yr"]
        return {"t_yr": round(t, 1), "s": round(float(s_of_age(t)[0]), 6),
                "a_au": round(float(np.interp(t, res["t_yr"], res["a_yr"])), 6)}

    out = {
        "meta": {
            "note": "fork 21: on MIST v1.2 the no-drag Earth is also engulfed (AGB, geometry); drag moves death to the RGB tip. S&CS 2008: 7.59 Gyr from present, RGB loss 0.332 Msun — divergence displayed.",
            "ledger_residual_frac": res_d["ledger"]["residual_frac"],
            "attributed_m": res_d["ledger"]["attributed"],
        },
        "s_grid": rr(s_grid),
        "a_drag_au": rr(a_drag),
        "a_nodrag_au": rr(a_nodrag),
        "r_star_au": rr(r_star_au),
        "engulf_drag": event(res_d),
        "engulf_nodrag": event(res_n),
        "mdot_track": rr(tr.col("star_mdot")),
        "mdot_sc05": rr(sc05_rate(tr)),
    }
    dest = ROOT / "app" / "data" / "earth.json"
    dest.write_text(json.dumps(out, indent=0).replace("NaN", "null"))
    print(f"earth.json: engulf(drag)={out['engulf_drag']}, engulf(nodrag)={out['engulf_nodrag']}")


if __name__ == "__main__":
    build()
