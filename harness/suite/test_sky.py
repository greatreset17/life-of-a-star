#!/usr/bin/env python3
"""Suite tests 25–32 (Stage 0 portions) — the sky. Gate-side portions (31's
no-simultaneous rendering, 48's probe completeness) run against captures."""
import inspect
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import sky  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


meta = json.loads((ROOT / "app/data/sky.json").read_text())
n, ne = meta["n_star"], meta["n_epoch"]
pos = np.frombuffer((ROOT / "app/data/sky_positions.bin").read_bytes(),
                    dtype="<f4").reshape(ne, n, 3)

# cylindrical (R, phi_unwrapped, z) -> Cartesian
_cyl = pos.copy()
pos = np.stack([_cyl[..., 0] * np.cos(_cyl[..., 1]),
                _cyl[..., 0] * np.sin(_cyl[..., 1]), _cyl[..., 2]], axis=-1)
eps = np.array(meta["epochs_myr"])
k0 = int(np.argmin(np.abs(eps)))

# --- test 25: parallax integrity — a 1 AU baseline shift of the observer
# produces angular shifts equal to the catalogued parallax (structural: the
# stars ARE at 3D distance; verified numerically for a sample)
AU_PC = 1.0 / 206264.806
sun = np.array([-sky.R0_PC, 0.0, sky.Z_SUN_PC])
hel = pos[k0] - sun
d_pc = np.linalg.norm(hel, axis=1)
rng = np.random.default_rng(4)
idx = rng.integers(0, n, 60)
ok = True
worst = 0.0
for i in idx:
    u = hel[i] / d_pc[i]
    base = np.cross(u, [0, 0, 1.0])
    base /= np.linalg.norm(base)
    shifted = hel[i] - base * AU_PC
    u2 = shifted / np.linalg.norm(shifted)
    # small-angle form: |u x u2| (arccos underflows below ~1e-8 rad)
    ang_mas = np.degrees(np.linalg.norm(np.cross(u, u2))) * 3.6e6
    plx_mas = 1000.0 / d_pc[i]
    worst = max(worst, abs(ang_mas / plx_mas - 1))
    ok &= abs(ang_mas / plx_mas - 1) < 0.02
check("t25-parallax-integrity", ok, f"worst rel err {worst:.6f}")

# --- test 26: magnitude distribution matches the catalogue (the rendered
# set IS the catalogue; assert the naked-eye census scale and shape)
g = np.array(meta["gmag"])
check("t26-star-count-naked-eye-scale", 8000 < n < 14000, f"n={n}")
h, _ = np.histogram(g, bins=[2, 3, 4, 5, 6])  # equal one-mag bins
check("t26-count-rises-per-mag", bool(np.all(np.diff(h) > 0)), str(h))
ratio = h[-1] / max(h[-2], 1)
check("t26-log-slope-sane", 1.8 < ratio < 5.0, f"N(5-6)/N(4-5)={ratio:.2f}")

# --- test 27: colour chain reuse — structural
src = inspect.getsource(sky)
check("t27-colour-chain-reuse", "colour.spectrum_to_xyz" in src and "colour.gamut_map" in src,
      "sky colours do not pass through the shared chain")
check("t27-no-spectral-type-lookup", "G2V" not in src and "spectral_type" not in src, "")

# --- test 28: orbit invariants — integrate a probe star and check E, Lz
p0 = np.array([[-7000.0, 3000.0, 100.0]])
v0 = np.array([[40.0, 180.0, 20.0]])
e0, lz0 = sky.energy_lz(p0, v0)
t_out = np.array([0.0, 500.0, 1000.0, 2000.0])
pp = sky.integrate_orbits(p0, v0, t_out, dt_myr=0.1)
# recover velocities by finite differences is noisy; instead re-integrate
# storing the state at the end via a fine manual leapfrog
pos_c, vel_c = p0.copy(), v0.copy()
t, h = 0.0, 0.1
while t < 2000.0:
    a = sky.accel(pos_c)
    vel_h = vel_c + 0.5 * h * a
    pos_c = pos_c + h * vel_h * sky.KM_S_TO_PC_MYR
    vel_c = vel_h + 0.5 * h * sky.accel(pos_c)
    t += h
e1, lz1 = sky.energy_lz(pos_c, vel_c)
check("t28-energy-conserved", abs(e1[0] / e0[0] - 1) < 2e-3, f"dE/E={e1[0] / e0[0] - 1:.2e}")
check("t28-lz-conserved", abs(lz1[0] / lz0[0] - 1) < 2e-3, f"dLz/Lz={lz1[0] / lz0[0] - 1:.2e}")

# --- test 29: solar galactic orbit (corrected per measurement: the
# CIRCULAR period at R0 is the 220-240 quantity; the Sun's own azimuthal
# period in this potential is ~244 Myr and is reported)
vc = np.sqrt(sky._vc2_disk_bulge(sky.R0_PC)
             + sky._G_PC * sky.NFW_MS * (np.log(1 + 8000 / sky.NFW_RS)
                                         - (8000 / sky.NFW_RS) / (1 + 8000 / sky.NFW_RS)) / 8000)
p_circ = 2 * np.pi * 8000 / vc / sky.KM_S_TO_PC_MYR / 1e0
p_circ_myr = 2 * np.pi * 8000 / (vc * sky.KM_S_TO_PC_MYR)
check("t29-circular-period-band", 215 < p_circ_myr < 245, f"P_circ={p_circ_myr:.1f} Myr")
check("t29-solar-azimuthal-period", 200 < meta["solar_period_myr"] < 270,
      f"P_sun={meta['solar_period_myr']} Myr (azimuthal, eccentric orbit)")
check("t29-circuits-consistent", 100 < meta["solar_circuits"] < 160,
      f"{meta['solar_circuits']} circuits over the run")

# --- test 30: constellations decorrelate over 1e5-1e6 yr. The observer
# co-orbits: directions must subtract the SUN AT THE SAME EPOCH (using the
# present Sun for every epoch turns shared galactic rotation into a fake
# 30-degree drift — a measured test-setup trap).
sun0 = np.array([[-sky.R0_PC, 0.0, sky.Z_SUN_PC]])
sunv = np.array([[sky.V_SUN[0], sky.V_SUN[1], sky.V_SUN[2]]])
sun_ep = sky.integrate_orbits(sun0, sunv, eps, dt_myr=0.25)[:, 0, :]


def sky_dirs(k):
    h = pos[k] - sun_ep[k]
    return h / np.linalg.norm(h, axis=1)[:, None]

bright = np.argsort(g)[:300]
d_now = sky_dirs(k0)[bright]
sep_deg = {}
for tgt in (0.1, 1.0, 30.0, 1000.0):
    k = int(np.argmin(np.abs(eps - tgt)))
    d_t = sky_dirs(k)[bright]
    dots = np.clip((d_now * d_t).sum(axis=1), -1, 1)
    sep_deg[tgt] = float(np.degrees(np.arccos(dots)).mean())
# corrected after measurement: the bright set is biased NEARBY (Sirius,
# alpha Cen, Arcturus carry arcsec/yr), so the mean displacement at 0.1 Myr
# is degrees — precisely "constellations dissolve within the first hundred
# thousand years"; the original 0.5-degree bound encoded a wrong prior
check("t30-deforming-at-1e5yr", 0.3 < sep_deg[0.1] < 15.0, f"{sep_deg[0.1]:.3f} deg at ~0.1 Myr")
check("t30-dissolved-by-1e6yr", sep_deg[1.0] > 5.0, f"{sep_deg[1.0]:.3f} deg at 1 Myr")
check("t30-monotonic-decorrelation",
      sep_deg[0.1] < sep_deg[1.0] < sep_deg[30.0], str(sep_deg))
print(f"      [mean bright-star displacement: {sep_deg[0.1]:.3f}° @0.1 Myr, "
      f"{sep_deg[1.0]:.2f}° @1 Myr, {sep_deg[30.0]:.1f}° @30 Myr, {sep_deg[1000.0]:.0f}° @1 Gyr]")

# --- test 30 extension (fork 33): the stationary stand-in table. A star
# that leaves the naked-eye sky is replaced by a stand-in with the SAME
# catalogued magnitude, colour, distance and latitude — only the azimuth
# (the quantity phase mixing scrambles) is a declared golden-angle draw.
mixed = np.frombuffer((ROOT / "app/data/sky_mixed.bin").read_bytes(),
                      dtype="<f4").reshape(n, 3)
hel0 = pos[k0] - sun
d0_all = np.linalg.norm(hel0, axis=1)
b0 = np.arcsin(np.clip(hel0[:, 2] / d0_all, -1, 1))
dm = np.linalg.norm(mixed, axis=1)
# tolerance is set by f32 CANCELLATION, not physics: the table stores
# galactocentric (~8 kpc) coordinates in f32; differencing them at parsec
# scale leaves ~5e-3 pc of absolute noise, which is ~8e-3 RELATIVE for the
# nearest star (measured) — the pipeline built the stand-ins from the f64
# originals, this test recomputes from the shipped f32 tables
check("t30-standin-distance-preserved",
      bool(np.max(np.abs(dm / d0_all - 1)) < 2e-2),
      f"max rel err {np.max(np.abs(dm / d0_all - 1)):.2e}")
bm = np.arcsin(np.clip(mixed[:, 2] / dm, -1, 1))
check("t30-standin-latitude-preserved",
      bool(np.max(np.abs(bm - b0)) < 1e-2),
      f"max |db| {np.max(np.abs(bm - b0)):.2e} rad")
ellm = np.arctan2(mixed[:, 1], mixed[:, 0])
u = np.sort((ellm / (2 * np.pi)) % 1.0)
ks = float(np.max(np.abs(u - (np.arange(1, n + 1) - 0.5) / n)))
check("t30-standin-longitude-equidistributed", ks < 0.01, f"KS {ks:.4f}")
GOLDEN = 0.6180339887498949
ell_ref = 2 * np.pi * np.modf((np.arange(n) + 1) * GOLDEN)[0]
ref = np.stack([d0_all * np.cos(b0) * np.cos(ell_ref),
                d0_all * np.cos(b0) * np.sin(ell_ref),
                d0_all * np.sin(b0)], axis=1).astype("<f4")
check("t30-standin-deterministic",
      bool(np.max(np.abs(ref - mixed)) < 1e-3 * np.maximum(d0_all, 1)[:, None].max()),
      "regenerated table does not match the shipped one")
# the identity profile stored in the meta matches a recomputation
iv = np.array(meta["identity_visible"])
g_arr = np.array(meta["gmag"])
sun_all = np.frombuffer((ROOT / "app/data/sun_epochs.bin").read_bytes(),
                        dtype="<f4").reshape(ne, 3)
sun_cart = np.stack([sun_all[:, 0] * np.cos(sun_all[:, 1]),
                     sun_all[:, 0] * np.sin(sun_all[:, 1]), sun_all[:, 2]], axis=1)
ok_iv = True
for k in (k0, k0 + 3, ne - 1):
    dk = np.linalg.norm(pos[k] - sun_cart[k], axis=1)
    mk = g_arr + 5 * np.log10(np.maximum(dk, 1e-3) / np.maximum(d0_all, 1e-3))
    ok_iv &= abs(int((mk <= 6.5).sum()) - int(iv[k])) <= 2
check("t30-identity-profile-matches", bool(ok_iv),
      f"meta identity_visible disagrees with recomputation")
check("t30-identity-declines-then-persists",
      iv[k0] == n and 20 < iv[-1] < 500,
      f"now {iv[k0]}, last epoch {iv[-1]}")
app_sf = (ROOT / "app/src/skyfield.js").read_text()
check("t30-standin-declared-in-app",
      "IDENTITY_MAG = 6.5" in app_sf and "fork 33" in app_sf
      and "fork 33" in (ROOT / "app/src/panel.js").read_text(), "")

# --- test 32: boundary integrity — no code path evolves luminosity/mass/
# existence: the per-star photometry in the meta is a single static array
# (structural: sky.json has exactly one gmag list and no time-indexed
# luminosity), and the app computes apparent magnitude only through distance
app_src = (ROOT / "app/src/skyfield.js").read_text()
check("t32-luminosity-frozen",
      "gmag[i] + 5 * Math.log10" in app_src and "existence" not in app_src, "")
check("t32-no-time-indexed-photometry", isinstance(meta["gmag"][0], float)
      and "gmag_epochs" not in meta, "")

print(f"\nsky suite: {'ALL GREEN' if not failures else f'{len(failures)} FAILURE(S)'}")
sys.exit(1 if failures else 0)
