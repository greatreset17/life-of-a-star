#!/usr/bin/env python3
"""Assemble the v0.3 app tables: the FULL spine (MIST + cooling + region B),
the extended colour table, the nebula solution, and the re-anchored events
including the two epochal markers. Replaces app/data/track.json and
colour.json with spine-length versions (the MIST prefix is bit-identical in
content; arc-length s values change because the spine now runs to the
terminus — that is the pass's declared effect, not a silent drift).
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.colour_cooling import CoolingColour  # noqa: E402
from pipeline.constants import TABLE_FLOAT_DECIMALS  # noqa: E402
from pipeline.cooling import CoolingSpine  # noqa: E402
from pipeline.granulation import granulation  # noqa: E402
from pipeline.limbdark import LimbDarkening  # noqa: E402
from pipeline.nebula import Nebula  # noqa: E402
from pipeline.track import Track  # noqa: E402

R = TABLE_FLOAT_DECIMALS


def rr(a):
    return [round(float(v), R) for v in np.asarray(a, float)]


def build():
    tr = Track.load()
    cs = CoolingSpine.build(tr)
    n_m = tr.n

    # granulation over the whole spine: MIST rows use track surface comp;
    # cooling rows are a pure-H DA atmosphere (declared)
    hp = np.empty(cs.n); dg = np.empty(cs.n); nd = np.empty(cs.n)
    hp[:n_m], dg[:n_m], nd[:n_m] = granulation(
        cs.teff[:n_m], cs.log_g[:n_m], cs.log_r[:n_m],
        tr.col("surface_h1"), tr.col("surface_he4"))
    hp[n_m:], dg[n_m:], nd[n_m:] = granulation(
        cs.teff[n_m:], cs.log_g[n_m:], cs.log_r[n_m:],
        np.ones(cs.n - n_m), np.zeros(cs.n - n_m))

    # limb darkening over the spine (WD rows: Claret edge, excursion recorded)
    ld = LimbDarkening()
    lda, lds, lde, ldf = [], [], [], []
    for i in range(cs.n):
        a, src, exc = ld.coefficients(cs.teff[i], cs.log_g[i], cs.mass[i])
        lda.append([round(float(v), R) for v in a])
        lds.append(src); lde.append(round(float(exc), 2))
        ldf.append(round(LimbDarkening.flux_ratio(a), R))

    # colour: MIST prefix from the existing table; cooling + region B rows
    # via fork 23's pathways
    base = json.loads((ROOT / "data" / "derived" / "colour.json").read_text())["rows"]
    cc = CoolingColour(ROOT)
    rows = list(base)
    for i in range(n_m, cs.n):
        rgb, xy, exc, src, t_exc = cc.row(cs.teff[i], cs.log_g[i], cs.mass[i])
        rows.append({
            "eep": i + 1, "teff": round(float(cs.teff[i]), 2),
            "logg": round(float(cs.log_g[i]), 4), "grid": src,
            "dlogg_edge": 0.0, "teff_edge": t_exc,
            "xy": [round(v, R) for v in xy],
            "rgb_lin": [round(v, R) for v in rgb],
            "excursion": round(exc, R),
        })

    # events on the new spine
    xf = cs.crystal_frac
    onset = int(np.argmax(xf > 0.01))
    done = int(np.argmax(xf > 0.97))
    ev_eep = {
        "protostar_contraction": 100,
        "zams": tr.anchors["zams"],
        "present_day": cs.markers["present_day"],
        "subgiant": tr.anchors["tams"] + 30,
        # the tip row itself is labelled CHeB's first instant by MIST; land
        # the waypoint on the branch it names (critic: caption and probe
        # disagreed at the piece's emotional peak)
        "rgb_tip": tr.anchors["rgb_tip"] - 1,
        "agb_thermal_pulses": 1100,
        "planetary_nebula_peak": None,   # filled from the nebula solution
        "wd_crystallisation": onset + 1,
    }

    # nebula
    nb = Nebula(tr, ROOT)
    sol = nb.solve()
    em = nb.emission(sol)
    lum = np.array([e["l_lines_w"] for e in em])
    ages_full = cs.age_yr
    t_abs = np.array([e["t_yr"] for e in em]) + nb.t0
    s_of_age = lambda t: float(np.interp(t, ages_full, cs.s))
    ipk = int(lum.argmax())
    for e, ta in zip(em, t_abs):
        e["s"] = round(s_of_age(ta), 6)
    pn_peak_s = em[ipk]["s"]

    events_s = {}
    for k, v in ev_eep.items():
        if k == "present_day":
            events_s[k] = round(v["s"], 6)
        elif k == "planetary_nebula_peak":
            events_s[k] = pn_peak_s
        elif k == "wd_crystallisation":
            events_s[k] = round(float(cs.s[onset]), 6)
        else:
            events_s[k] = round(float(cs.s[v - 1]), 6)
    markers = {
        "present_day": {**cs.markers["present_day"]},
        "existence": {**cs.markers["existence"]},
        "crystallisation": {"s_onset": float(cs.s[onset]), "s_complete": float(cs.s[done]),
                            "teff_onset": float(cs.teff[onset]), "teff_complete": float(cs.teff[done])},
        "join": {"s": float(cs.s[cs.join_index]), **cs.join_report},
        "horizon": {"s": float(cs.s[cs.horizon_index]), "teff_k": float(cs.teff[cs.horizon_index])},
    }

    out = {
        "meta": {
            "n": cs.n, "n_mist": n_m,
            "spine": "mist + bedard cooling (mass-interpolated 0.5398) + region B (fork 9)",
            "join_index": cs.join_index, "horizon_index": cs.horizon_index,
            "solar_offset": json.loads((ROOT / "app" / "data" / "track.json").read_text())["meta"]["solar_offset"],
            "regionb": {"law": "debye-exponential", "tau_yr": cs.regionb_anchor["tau_yr"]},
        },
        "anchors": tr.anchors,
        "events_s": events_s,
        "markers": markers,
        "s": rr(cs.s),
        "age_yr": rr(cs.age_yr),
        "log_L": rr(cs.log_l),
        "log_Teff": rr(np.log10(cs.teff)),
        "log_R": rr(cs.log_r),
        "log_g": rr(cs.log_g),
        "star_mass": rr(cs.mass),
        "phase": rr(cs.phase),
        "crystal_frac": rr(cs.crystal_frac),
        "data_state": cs.data_state,
        "granule_hp_m": rr(hp),
        "granule_d_m": rr(dg),
        "granule_n_disk": rr(nd),
        "ld_a": lda,
        "ld_source": lds,
        "ld_excursion": lde,
        "ld_flux_ratio": ldf,
    }
    dest = ROOT / "app" / "data"
    (dest / "track.json").write_text(json.dumps(out, indent=0))
    (dest / "colour.json").write_text(json.dumps(
        {"source": "spectrum -> CIE -> XYZ -> linear sRGB -> Oklab gamut map; cooling tail per fork 23",
         "rows": rows}, indent=0))
    (dest / "nebula.json").write_text(json.dumps({
        "meta": {"m_ejected_msun": nb.m_ejected, "v_slow_kms": nb.v_slow / 1e3,
                 "note": "interacting winds solved; sphericity/T_e/thin-shell asserted (fork 5)"},
        "steps": em}, indent=0))
    # keep the derived-side copies for identity hashing
    (ROOT / "data" / "derived" / "spine.json").write_text(json.dumps(
        {"n": cs.n, "join": markers["join"], "horizon": markers["horizon"],
         "markers": {k: v for k, v in markers.items()}}, indent=0, default=float))
    print(f"extended spine: {cs.n} nodes ({n_m} MIST + {cs.horizon_index - n_m + 1} cooling "
          f"+ {cs.n - cs.horizon_index - 1} region B); PN peak s={pn_peak_s}; "
          f"crystallisation onset s={events_s['wd_crystallisation']}")


if __name__ == "__main__":
    build()
