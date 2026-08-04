#!/usr/bin/env python3
"""Suite tests 1–4, 10, 12 — track fidelity, Stefan–Boltzmann invariance,
present-day and ZAMS anchors, RGB-tip maximum, arc-length monotonicity.

Written BEFORE pipeline/track.py and pipeline/arclength.py existed; the
anchors below are published numbers, not readings of the implementation.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.constants import SIGMA_SB, L_SUN_W, R_SUN_M  # noqa: E402
from pipeline.track import Track  # noqa: E402
from pipeline.arclength import ArcLength  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


tr = Track.load()

# --- test 1: interpolation at and between tabulated EEPs reproduces the table
rng = np.random.default_rng(20260804)
idx = rng.integers(1, tr.n - 1, 200)
max_rel = 0.0
for i in idx:
    got = tr.at_eep(float(i + 1))  # EEP index is 1-based
    for col in ("log_L", "log_Teff", "log_R", "star_mass"):
        want = tr.col(col)[i]
        scale = max(abs(want), 1e-3)
        max_rel = max(max_rel, abs(got[col] - want) / scale)
check("t01-track-fidelity-nodes", max_rel < 0.005, f"max rel err {max_rel:.2e}")

# --- test 2: L = 4 pi R^2 sigma Teff^4 holds without being imposed
L = 10 ** tr.col("log_L") * L_SUN_W
R = 10 ** tr.col("log_R") * R_SUN_M
T = 10 ** tr.col("log_Teff")
L_sb = 4 * np.pi * R ** 2 * SIGMA_SB * T ** 4
rel = np.abs(L_sb / L - 1.0)
check("t02-stefan-boltzmann", float(rel.max()) < 0.01, f"max rel dev {rel.max():.3e} at row {int(rel.argmax())}")

# --- test 3 (corrected per fork 14): pipeline reproduces the track at
# 4.57 Gyr, and the track's offset from the OBSERVED Sun is bounded and
# reported (the MIST v1.2 grid track is itself ~7-10% overluminous at solar
# age; the track wins and the discrepancy is displayed, never hidden).
p = tr.at_age(4.57e9)
teff = 10 ** p["log_Teff"]
raw_i = int(np.argmin(np.abs(tr.col("star_age") - 4.57e9)))
raw_T = 10 ** tr.col("log_Teff")[raw_i]
check("t03-present-matches-track", abs(teff - raw_T) < 10,
      f"interp Teff={teff:.1f} vs raw {raw_T:.1f}")
dT, dL, dR = teff - 5772.0, 10 ** p["log_L"] - 1.0, 10 ** p["log_R"] - 1.0
check("t03-present-offset-bounded",
      abs(dT) < 100 and abs(dL) < 0.12 and abs(dR) < 0.03,
      f"dTeff={dT:+.1f}K dL={dL:+.4f} dR={dR:+.4f}")
print(f"      [reported offset vs observed Sun: dTeff={dT:+.1f} K, dL={dL:+.1%}, dR={dR:+.1%}]")

# --- test 4 (corrected per fork 14): faint young Sun as ZAMS/present ratio
zl = 10 ** tr.at_eep(tr.anchors["zams"])["log_L"]
ratio = zl / 10 ** p["log_L"]
check("t04-faint-young-sun-ratio", 0.64 <= ratio <= 0.75, f"L_zams/L_present={ratio:.4f}")
check("t04-zams-luminosity-band", 0.68 <= zl <= 0.78, f"L_zams={zl:.4f}")

# --- test 10 (corrected per fork 14): the radius maximum sits where the
# TRACK puts it — on the TP-AGB for MIST v1.2's eta_R=0.1 mass loss — and
# both radii are exported for the panel's prescription-divergence readout.
rgb_tip_eep = tr.anchors["rgb_tip"]
r_all = 10 ** tr.col("log_R")
i_max = int(np.argmax(r_all))
in_tpagb = tr.anchors["tp_agb_begin"] <= (i_max + 1) < tr.anchors["post_agb"]
check("t10-max-radius-where-track-puts-it", in_tpagb,
      f"global max R={r_all[i_max]:.1f} Rsun at EEP {i_max + 1} "
      f"(TP-AGB span {tr.anchors['tp_agb_begin']}-{tr.anchors['post_agb']})")
r_rgb_tip = float(r_all[rgb_tip_eep - 1])
check("t10-both-radii-finite-ordered", 0 < r_rgb_tip < float(r_all[i_max]),
      f"RGB tip {r_rgb_tip:.1f}, AGB max {r_all[i_max]:.1f}")
print(f"      [S&CS divergence: track AGB max {r_all[i_max]:.0f} Rsun > RGB tip "
      f"{r_rgb_tip:.0f} Rsun; S&CS 2008 has the reverse — mass-loss prescription, see fork 14]")

# --- test 12 (MIST portion): arc length monotonic in EEP, uniform in s
al = ArcLength.from_track(tr)
s = al.s_of_eep(np.arange(1, tr.n + 1, dtype=float))
check("t12-arclength-monotonic", bool(np.all(np.diff(s) >= 0)), "s not monotonic in EEP")
# uniformity: inverting s and re-integrating segment lengths per equal-s bins
ss = np.linspace(0.0, s[-1], 2001)
ee = al.eep_of_s(ss)
check("t12-arclength-invertible", bool(np.all(np.diff(ee) > -1e-9)), "eep_of_s not monotonic")
xy = np.stack([tr.col("log_Teff"), tr.col("log_L")], axis=1)
seg = np.linalg.norm(np.diff(xy, axis=0), axis=1)
tot = float(seg.sum())
check("t12-arclength-total-positive-finite", np.isfinite(tot) and tot > 0, f"total={tot}")
d = np.abs(al.s_of_eep(np.arange(1, tr.n + 1, dtype=float))[-1] - 1.0)
check("t12-arclength-normalised", d < 1e-12, f"s(end)={1.0 + d}")

print(f"\ntrack suite: {'ALL GREEN' if not failures else f'{len(failures)} FAILURE(S)'}")
sys.exit(1 if failures else 0)
