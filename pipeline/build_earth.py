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

from pipeline.constants import AU_M, R_SUN_M, TABLE_FLOAT_DECIMALS  # noqa: E402
from pipeline.cooling import CoolingSpine  # noqa: E402
from pipeline.earth import EarthOrbit, sc05_rate  # noqa: E402
from pipeline.track import Track  # noqa: E402

R = TABLE_FLOAT_DECIMALS


def rr(a):
    return [round(float(v), R) for v in np.asarray(a, float)]


def build():
    tr = Track.load()
    # slider positions live on the FULL spine's arc length (v0.3+)
    cs = CoolingSpine.build(tr)
    eo = EarthOrbit(tr)
    ages = tr.col("star_age")

    def s_of_age(t_yr):
        return np.interp(np.atleast_1d(t_yr), cs.age_yr, cs.s)

    res_d = eo.integrate(drag=True)
    res_n = eo.integrate(drag=False)

    # the drawn-curve grid is the TRACK's own age nodes (dense exactly where
    # the star changes — a geomspace output grid steps ~90 Myr near the tip
    # and misses the 50-Myr radius spike entirely, so the drawn curves never
    # met at the engulfment dot; measured by the critic pass), plus the
    # integrator's own output where the orbit lives
    t_grid = np.unique(np.concatenate([res_n["t_yr"], ages]))
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
        # the capture radius is R(t_event) BY DEFINITION of the terminal
        # condition a = R; reading a from the coarse output grid instead
        # straddles the final tidal plunge and misreports it (0.99 vs the
        # true 0.80 AU — caught by external review cross-checking failure
        # state 8)
        r_au = float(10 ** np.interp(t, ages, tr.col("log_R")) * R_SUN_M / AU_M)
        return {"t_yr": round(t, 1), "s": round(float(s_of_age(t)[0]), 6),
                "a_au": round(r_au, 6)}

    # the ruthless numbers for the toggle's honest meaning (fork 21): how
    # much the no-drag Earth clears the RGB tip by — and how far the AGB
    # then reaches beyond its orbit anyway
    i_tip = int(np.argmax(10 ** tr.col("log_R")[:tr.anchors["tp_agb_begin"]]))
    t_tip = float(ages[i_tip])
    r_tip_au = float(10 ** tr.col("log_R")[i_tip] * R_SUN_M / AU_M)
    a_nd_tip = float(np.interp(t_tip, res_n["t_yr"], res_n["a_yr"]))
    i_max = int(np.argmax(10 ** tr.col("log_R")))
    t_max = float(ages[i_max])
    r_max_au = float(10 ** tr.col("log_R")[i_max] * R_SUN_M / AU_M)
    a_nd_max = float(np.interp(t_max, res_n["t_yr"], res_n["a_yr"],
                               right=res_n["a_yr"][-1]))

    out = {
        "meta": {
            "note": "fork 21: on MIST v1.2 the no-drag Earth is also engulfed (AGB, geometry); drag moves death to the RGB tip. S&CS 2008: 7.59 Gyr from present, RGB loss 0.332 Msun — divergence displayed.",
            "ledger_residual_frac": res_d["ledger"]["residual_frac"],
            "attributed_m": res_d["ledger"]["attributed"],
            "r_rgb_tip_au": round(r_tip_au, 4),
            "r_agb_max_au": round(r_max_au, 4),
            "nodrag_rgb_miss_au": round(a_nd_tip - r_tip_au, 4),
            "nodrag_agb_overrun_au": round(r_max_au - a_nd_max, 4),
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
