#!/usr/bin/env python3
"""Suite test 36 (Stage 0 portion) + granulation anchors: H_p derived from
the track alone; Sun ~1e6 disk cells; giant a handful-to-hundreds; count
continuous along the track (no rendering-regime dependence exists in Stage 0
by construction — the single implementation is pipeline/granulation.py; the
cross-regime identity check runs against Stage 1's probe in the gate)."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.granulation import granulation  # noqa: E402
from pipeline.track import Track  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


tr = Track.load()
T = 10 ** tr.col("log_Teff")
hp, d, n = granulation(T, tr.col("log_g"), tr.col("log_R"),
                       tr.col("surface_h1"), tr.col("surface_he4"))

i_now = int(round(tr.eep_at_age(4.57e9))) - 1
check("t36-sun-hp-140km", 100e3 < hp[i_now] < 200e3, f"H_p={hp[i_now] / 1e3:.0f} km")
check("t36-sun-granule-1400km", 1.0e6 < d[i_now] < 2.0e6, f"D={d[i_now] / 1e3:.0f} km")
check("t36-sun-1e6-cells", 3e5 < n[i_now] < 3e6, f"N_disk={n[i_now]:.2e}")

RSUN = 6.957e8
i_tip = tr.anchors["rgb_tip"] - 1
check("t36-rgb-tip-few-cells", 3 < n[i_tip] < 3000, f"N_disk={n[i_tip]:.0f}")
print(f"      [RGB tip: H_p={hp[i_tip] / RSUN:.2f} Rsun, D={d[i_tip] / RSUN:.1f} Rsun, N={n[i_tip]:.0f}]")

check("t36-count-finite-positive", bool(np.all(np.isfinite(n)) and np.all(n > 0)), "")
# continuity: adjacent-EEP count ratio bounded (no discontinuity anywhere)
ratio = np.abs(np.diff(np.log10(n)))
check("t36-count-continuous-along-track", float(ratio.max()) < 0.5,
      f"max |dlog10 N| per EEP = {ratio.max():.3f} at {int(ratio.argmax()) + 1}")

print(f"\ngranulation suite: {'ALL GREEN' if not failures else f'{len(failures)} FAILURE(S)'}")
sys.exit(1 if failures else 0)
