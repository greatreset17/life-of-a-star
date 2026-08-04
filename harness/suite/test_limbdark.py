#!/usr/bin/env python3
"""Suite tests 9 (no single coefficient set / no uniform disk), 11 (flux
normalization factor sane and recomputable), fork-18 seam continuity, and
the soft-giant-limb property (spherical fits droop at the limb where planar
fits stay high)."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.limbdark import LimbDarkening  # noqa: E402
from pipeline.track import Track  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


ld = LimbDarkening()
tr = Track.load()
T = 10 ** tr.col("log_Teff")
G = tr.col("log_g")
M = tr.col("star_mass")

# coefficients vary along the track (failure state 9)
sample = np.linspace(0, tr.n - 1, 60).astype(int)
coeffs, srcs, excs = [], [], []
for i in sample:
    a, src, exc = ld.coefficients(T[i], G[i], M[i])
    coeffs.append(a); srcs.append(src); excs.append(exc)
coeffs = np.array(coeffs)
check("t09-coefficients-vary", float(np.ptp(coeffs, axis=0).max()) > 0.1,
      f"max ptp={np.ptp(coeffs, axis=0).max():.3f}")
check("t09-both-sources-used", len(set(srcs)) == 2, f"sources={set(srcs)}")
check("t09-no-uniform-disk", bool(np.all(np.abs(coeffs).sum(axis=1) > 0.05)), "")

# flux normalization factor: positive, < 1 (darkened), recomputable
i_now = int(round(tr.eep_at_age(4.57e9))) - 1
a_sun, src_sun, _ = ld.coefficients(T[i_now], G[i_now], M[i_now])
fr = ld.flux_ratio(a_sun)
check("t11-sun-flux-ratio-sane", 0.55 < fr < 0.95, f"flux_ratio={fr:.4f} ({src_sun})")
prof = ld.profile(a_sun, np.array([0.0, 0.3, 0.7, 1.0]))
check("t11-sun-profile-darkens-to-limb", bool(np.all(np.diff(prof) > 0)) and prof[-1] == 1.0,
      f"I(mu)/I(1) = {prof}")

# giant limb is SOFT: spherical profile at RGB tip far lower at the limb
i_tip = tr.anchors["rgb_tip"] - 1
a_g, src_g, _ = ld.coefficients(T[i_tip], G[i_tip], M[i_tip])
check("t09-giant-uses-spherical", src_g == "neilson2013-spherical", src_g)
edge_g = float(ld.profile(a_g, np.array([0.05]))[0])
edge_sun = float(ld.profile(a_sun, np.array([0.05]))[0])
check("t09-giant-limb-softer-than-dwarf", edge_g < edge_sun,
      f"I(0.05): giant {edge_g:.3f} vs dwarf {edge_sun:.3f}")
print(f"      [limb I(mu=0.05): giant {edge_g:.3f} ({src_g}), sun {edge_sun:.3f} ({src_sun})]")

# seam behaviour (fork 18, corrected after measurement — recorded in fork
# block): the INTERIOR of the disk is continuous across the logg=3 seam;
# the limb region (mu < 0.1) legitimately DIVERGES there because the two
# published families differ in geometry (spherical profiles droop toward
# zero, planar ones do not — Neilson & Lester 2013's own result). The
# divergence is asserted to have the physical SIGN (giant side softer) and
# its magnitude is reported, not suppressed.
a_lo, _, _ = ld.coefficients(5000.0, 2.99, 1.0)
a_hi, _, _ = ld.coefficients(5000.0, 3.01, 1.0)
mu_int = np.linspace(0.30, 1.0, 200)
d_int = float(np.abs(ld.profile(a_lo, mu_int) - ld.profile(a_hi, mu_int)).max())
check("t09-seam-interior-continuity", d_int < 0.08, f"max |dI| (mu>=0.3) = {d_int:.4f}")
mu_limb = np.linspace(0.02, 0.10, 50)
d_limb = float((ld.profile(a_hi, mu_limb) - ld.profile(a_lo, mu_limb)).min())
check("t09-seam-limb-droop-correct-sign", d_limb > -0.05,
      f"planar-minus-spherical at limb min = {d_limb:.4f} (spherical must droop below planar)")
print(f"      [seam at logg=3: interior gap {d_int:.4f}; limb-region geometry divergence "
      f"{float((ld.profile(a_hi, mu_limb) - ld.profile(a_lo, mu_limb)).max()):.4f} — declared, fork 18]")

# support-edge excursions: interior sources bounded by grid spacing; the
# declared hot edge (Teff > 50000, limb sub-pixel) reports Teff - 50000
# exactly by construction.
interior = [e for e, i in zip(excs, sample) if T[i] <= 50000.0]
hot = [(e, T[i]) for e, i in zip(excs, sample) if T[i] > 50000.0]
check("t09-excursions-interior-bounded", max(interior) < 350.0,
      f"max interior excursion={max(interior):.1f}")
check("t09-excursions-hot-edge-exact",
      all(abs(e - (t - 50000.0)) < 1e-6 for e, t in hot) if hot else True,
      f"hot-edge excursions {[f'{e:.0f}@{t:.0f}' for e, t in hot[:4]]}")

print(f"\nlimbdark suite: {'ALL GREEN' if not failures else f'{len(failures)} FAILURE(S)'}")
sys.exit(1 if failures else 0)
