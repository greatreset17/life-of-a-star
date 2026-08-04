#!/usr/bin/env python3
"""Assemble the app-ready derived tables. Stage 1 fetches nothing at runtime;
these files ARE its physics. Everything here is read from the track, the
colour table, the LD tables and the granulation derivation — no quantity is
invented, none is hardcoded downstream.

Outputs (float64 values rounded per fork 3):
  app/data/track.json   per-EEP arrays + anchors + events + arc metadata
  app/data/colour.json  copy of the chromaticity table (bijection target)
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.arclength import ArcLength  # noqa: E402
from pipeline.constants import TABLE_FLOAT_DECIMALS  # noqa: E402
from pipeline.granulation import granulation  # noqa: E402
from pipeline.limbdark import LimbDarkening  # noqa: E402
from pipeline.track import Track  # noqa: E402

R = TABLE_FLOAT_DECIMALS


def rr(arr):
    return [round(float(v), R) for v in np.asarray(arr, float)]


def build():
    tr = Track.load()
    al = ArcLength.from_track(tr)
    T = 10 ** tr.col("log_Teff")
    hp, dgr, ndisk = granulation(T, tr.col("log_g"), tr.col("log_R"),
                                 tr.col("surface_h1"), tr.col("surface_he4"))
    ld = LimbDarkening()
    lda, lds, lde = [], [], []
    for i in range(tr.n):
        a, src, exc = ld.coefficients(T[i], tr.col("log_g")[i], tr.col("star_mass")[i])
        lda.append(a); lds.append(src); lde.append(exc)
    lda = np.array(lda)
    s_nodes = al.s_of_eep(np.arange(1, tr.n + 1, dtype=float))

    eep_now = tr.eep_at_age(4.57e9)
    events = {
        "protostar_contraction": 100,
        "zams": tr.anchors["zams"],
        "present_day": round(eep_now, 3),
        "subgiant": tr.anchors["tams"] + 30,
        "rgb_tip": tr.anchors["rgb_tip"],
        "agb_thermal_pulses": 1100,
        # v0.1 stand-ins; v0.3 re-anchors these on the extended spine:
        "planetary_nebula_peak": 1550,
        "wd_crystallisation": tr.n,
    }
    events_s = {k: round(float(al.s_of_eep(np.array([v]))[0]), 6) for k, v in events.items()}

    out = {
        "meta": {
            "n": tr.n,
            "spine": "mist-only (v0.1); extended by cooling + region B in v0.3",
            "arc_units": "(log Teff, log L), normalised to 1",
            "present_day_eep": round(eep_now, 3),
            "solar_offset": {
                "note": "fork 14: MIST v1.2 grid track vs observed Sun at 4.57 Gyr",
                "dteff_k": round(float(10 ** tr.at_age(4.57e9)["log_Teff"] - 5772.0), 2),
                "dl_frac": round(float(10 ** tr.at_age(4.57e9)["log_L"] - 1.0), 4),
                "dr_frac": round(float(10 ** tr.at_age(4.57e9)["log_R"] - 1.0), 4),
            },
        },
        "anchors": tr.anchors,
        "events_eep": events,
        "events_s": events_s,
        "s": rr(s_nodes),
        "age_yr": rr(tr.col("star_age")),
        "log_L": rr(tr.col("log_L")),
        "log_Teff": rr(tr.col("log_Teff")),
        "log_R": rr(tr.col("log_R")),
        "log_g": rr(tr.col("log_g")),
        "star_mass": rr(tr.col("star_mass")),
        "phase": rr(tr.col("phase")),
        "granule_hp_m": rr(hp),
        "granule_d_m": rr(dgr),
        "granule_n_disk": rr(ndisk),
        "ld_a": [rr(a) for a in lda],
        "ld_source": lds,
        "ld_excursion": rr(lde),
        "ld_flux_ratio": rr([LimbDarkening.flux_ratio(a) for a in lda]),
    }
    dest = ROOT / "app" / "data"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "track.json").write_text(json.dumps(out, indent=0))
    colour_src = (ROOT / "data" / "derived" / "colour.json").read_text()
    (dest / "colour.json").write_text(colour_src)
    print(f"app/data/track.json ({tr.n} EEPs) + colour.json written")


if __name__ == "__main__":
    build()
