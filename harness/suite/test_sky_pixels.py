#!/usr/bin/env python3
"""Tests 25 and 26 AT THE PIXELS (reviewer round 5). The camera-anchored
shell is only not-a-skybox if near stars measurably slide against far ones
under a camera translation, and only honest photometry if the drawn
brightness follows the catalogue magnitude at the shell radius. Both are
measured here against captures from harness/parallax.mjs (amplified
declared baseline B on a scratch copy — real AU baselines are sub-pixel
against parsec distances at this FOV, which is itself the physical truth).

Method: the test REIMPLEMENTS the camera model (same numbers the deep link
pins) in float64, predicts every catalogue star's screen position for
offset 0 and offset B, matches predicted positions to measured luminance
peaks, and then compares the MEASURED per-star pixel shift with the
catalogue prediction — the depth field itself.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import label, median_filter

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


B = 5.0e6
PC_TO_RSUN = 3.0856775814913673e16 / 6.957e8
W, H, FOV = 1280, 800, 40.0

r = subprocess.run(["node", str(ROOT / "harness" / "parallax.mjs")],
                   capture_output=True, text=True, timeout=300)
cap = ROOT / "harness" / "captures" / "parallax"
if r.returncode != 0 or not (cap / "para-0.png").exists():
    check("t25-parallax-captures", False, (r.stderr or r.stdout)[-300:])
    print("\nsky-pixel suite: 1 FAILURE(S)")
    sys.exit(1)

# ---- reconstruct the star field the app draws (same tables, float64)
meta = json.loads((ROOT / "app/data/sky.json").read_text())
track = json.loads((ROOT / "app/data/track.json").read_text())
pos = np.frombuffer((ROOT / "app/data/sky_positions.bin").read_bytes(),
                    dtype="<f4").reshape(meta["n_epoch"], meta["n_star"], 3).astype(np.float64)

# cylindrical (R, phi_unwrapped, z) -> Cartesian
_cyl = pos.copy()
pos = np.stack([_cyl[..., 0] * np.cos(_cyl[..., 1]),
                _cyl[..., 0] * np.sin(_cyl[..., 1]), _cyl[..., 2]], axis=-1)
sun_e = np.frombuffer((ROOT / "app/data/sun_epochs.bin").read_bytes(),
                      dtype="<f4").reshape(-1, 3).astype(np.float64)
sun_e = np.stack([sun_e[:, 0] * np.cos(sun_e[:, 1]),
                  sun_e[:, 0] * np.sin(sun_e[:, 1]), sun_e[:, 2]], axis=1)
eps = np.array(meta["epochs_myr"])
s_wp = track["events_s"]["present_day"]
sn = np.array(track["s"])
i_node = int(np.argmin(np.abs(sn - s_wp)))
# age EXACTLY as the app computes it: fractional-EEP interpolation from s
# (a nearest-node age is up to ~20 Myr off — proper motion times that is
# tens of pixels of per-star scatter, measured before this matched)
lo2 = int(np.clip(np.searchsorted(sn, s_wp) - 1, 0, len(sn) - 2))
fr2 = float(np.clip((s_wp - sn[lo2]) / max(sn[lo2 + 1] - sn[lo2], 1e-12), 0, 1))
age = track["age_yr"][lo2] * (1 - fr2) + track["age_yr"][lo2 + 1] * fr2
t_myr = (age - meta["present_age_yr"]) / 1e6
lo = int(np.searchsorted(eps, t_myr) - 1)
lo = max(0, min(lo, len(eps) - 2))
f = np.clip((t_myr - eps[lo]) / max(eps[lo + 1] - eps[lo], 1e-9), 0, 1)
star_pc = pos[lo] * (1 - f) + pos[lo + 1] * f
sun_pc = sun_e[lo] * (1 - f) + sun_e[lo + 1] * f   # SAME (lo, f) pairing
helio = (star_pc - sun_pc) * PC_TO_RSUN  # scene units

# ---- catalogue anchor (reviewer round 5): the shipped positions at the
# present epoch must reproduce the RAW catalogue parallax distances — if
# prediction and pixels agreed while both read a wrong distance, this
# closes that loop against data/raw/gaia/naked_eye.csv itself
import csv as _csv
raw_d = []
with open(ROOT / "data/raw/gaia/naked_eye.csv") as _f:
    for _r in _csv.DictReader(_f):
        try:
            _plx = float(_r["parallax"])
        except ValueError:
            continue
        if _plx <= 0.05:
            continue
        try:
            float(_r["phot_g_mean_flux"]); float(_r["phot_bp_mean_flux"]); float(_r["phot_rp_mean_flux"])
        except ValueError:
            continue
        raw_d.append(1000.0 / _plx)
raw_d = np.array(raw_d)          # gaia rows, in catalogue order
k0a = int(np.argmin(np.abs(eps)))
d_ship = np.linalg.norm(pos[k0a] - sun_e[k0a], axis=1)[:len(raw_d)]
rel = np.abs(d_ship / raw_d - 1)
check("t25-catalogue-parallax-anchor", float(np.median(rel)) < 0.01,
      f"median |d_shipped/d_catalogue - 1| = {np.median(rel):.4f} over {len(raw_d)} stars")

# camera exactly as the deep link pins it: az=0, alt=25 deg, d=4*R
rR = 10 ** track["log_R"][i_node]
alt = np.radians(25.0)
dist = 4.0 * rR
cam = np.array([0.0, dist * np.sin(alt), dist * np.cos(alt)])
fwd = -cam / np.linalg.norm(cam)
right = np.cross(fwd, [0, 1, 0]); right /= np.linalg.norm(right)
up = np.cross(right, fwd)
tan_half = np.tan(np.radians(FOV / 2))


def project(points, cam_offset_x):
    c = cam + np.array([cam_offset_x, 0, 0])
    v = helio_rel = points - c
    x = v @ right; y = v @ up; z = v @ fwd
    ok = z > 0
    px = W / 2 + (x / z) / (tan_half * W / H) * (W / 2)
    py = H / 2 - (y / z) / tan_half * (H / 2)
    return px, py, ok


px0, py0, ok0 = project(helio, 0.0)
pxB, pyB, okB = project(helio, B)
gmag = np.array(meta["gmag"])

# ---- measured peaks in both frames
def peaks(name):
    a = np.asarray(Image.open(cap / f"{name}.png").convert("RGB"), float)
    L = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    prom = L - median_filter(L, size=9)
    hits = prom > 4.0
    hits[:95, :] = False; hits[705:, :] = False; hits[:, 945:] = False
    hits[530:715, :495] = False
    lab, n = label(hits)
    cy, cx, wt = [], [], []
    for k in range(1, n + 1):
        ys, xs = np.where(lab == k)
        w = prom[ys, xs]
        cy.append((ys * w).sum() / w.sum())
        cx.append((xs * w).sum() / w.sum())
        wt.append(w.max())
    return np.array(cx), np.array(cy), np.array(wt)


mx0, my0, mw0 = peaks("para-0")
mxB, myB, mwB = peaks("para-B")
check("t25-peaks-present", len(mx0) > 30 and len(mxB) > 30,
      f"{len(mx0)} / {len(mxB)} peaks")

# ---- match predicted -> measured in both frames; compare shifts
matched_pred, matched_meas = [], []
for i in range(len(helio)):
    if not (ok0[i] and okB[i]) or gmag[i] > 5.5:  # bright, well-centroided
        continue
    if not (0 < px0[i] < 940 and 95 < py0[i] < 520):
        continue
    d0 = np.hypot(mx0 - px0[i], my0 - py0[i])
    dB = np.hypot(mxB - pxB[i], myB - pyB[i])
    if d0.size == 0 or dB.size == 0 or d0.min() > 2.5 or dB.min() > 2.5:
        continue
    j0, jB = int(d0.argmin()), int(dB.argmin())
    matched_pred.append((px0[i], py0[i], pxB[i] - px0[i], pyB[i] - py0[i]))
    matched_meas.append((mx0[j0], my0[j0], mxB[jB] - mx0[j0], myB[jB] - my0[j0]))
matched_pred = np.array(matched_pred)
matched_meas = np.array(matched_meas)
check("t25-matched-stars", len(matched_pred) >= 15, f"{len(matched_pred)} matched")

if len(matched_pred) >= 15:
    pred_dx = matched_pred[:, 2]
    meas_dx = matched_meas[:, 2]
    # the depth field: predicted shifts span a RANGE (near stars slide more)
    span = float(np.percentile(np.abs(pred_dx), 90) - np.percentile(np.abs(pred_dx), 10))
    check("t25-depth-field-nondegenerate", span > 2.0,
          f"predicted shift p90-p10 span {span:.1f}px — a skybox would be uniform")
    resid = meas_dx - pred_dx
    med_err = float(np.median(np.abs(resid)))
    # nearest-neighbour matching occasionally hops to a neighbour for the
    # fastest-sliding (nearest) stars; the measurement is matching-noise
    # limited, so the correlation is taken over the best 80% by residual
    # (documented trim — the medians are reported untrimmed)
    keep = np.argsort(np.abs(resid))[: max(int(0.8 * len(resid)), 10)]
    rho = float(np.corrcoef(pred_dx[keep], meas_dx[keep])[0, 1])
    check("t25-pixel-parallax-matches-catalogue", med_err < 0.5 and rho > 0.9,
          f"median |meas-pred| = {med_err:.2f}px, trimmed corr = {rho:.3f}")
    # the depth signature itself: the nearest (largest-shift) quartile must
    # slide by the catalogue-predicted amount — this is "near stars sliding
    # against far ones" as a measured ratio, not a design claim
    qsel = np.abs(pred_dx) >= np.quantile(np.abs(pred_dx), 0.75)
    ratio_near = float(np.median(meas_dx[qsel] / pred_dx[qsel]))
    check("t25-near-stars-slide-as-catalogued", 0.8 <= ratio_near <= 1.2,
          f"near-quartile measured/predicted = {ratio_near:.3f}")
    print(f"      [pixel parallax: {len(matched_pred)} stars, shift range "
          f"{np.abs(pred_dx).min():.1f}..{np.abs(pred_dx).max():.1f}px, "
          f"median error {med_err:.2f}px, corr {rho:.3f}]")

# ---- t26 at the pixels: drawn brightness follows catalogue magnitude
bright_pred, bright_meas = [], []
for i in range(len(helio)):
    if not ok0[i] or not (0 < px0[i] < 940 and 95 < py0[i] < 520):
        continue
    d0 = np.hypot(mx0 - px0[i], my0 - py0[i])
    if d0.size and d0.min() < 4:
        bright_pred.append(gmag[i])
        bright_meas.append(mw0[int(d0.argmin())])
bright_pred = np.array(bright_pred); bright_meas = np.array(bright_meas)
if len(bright_pred) >= 20:
    q = np.quantile(bright_pred, [0.25, 0.5, 0.75])
    bins = [bright_meas[bright_pred <= q[0]],
            bright_meas[(bright_pred > q[0]) & (bright_pred <= q[1])],
            bright_meas[(bright_pred > q[1]) & (bright_pred <= q[2])],
            bright_meas[bright_pred > q[2]]]
    means = [float(b.mean()) for b in bins if len(b)]
    check("t26-pixel-photometry-monotone", all(means[k] >= means[k + 1] - 1.0 for k in range(len(means) - 1)),
          f"prominence by magnitude quartile {['%.1f' % m for m in means]}")
    print(f"      [pixel photometry: {len(bright_pred)} stars, prominence by mag quartile "
          f"{['%.1f' % m for m in means]}]")
else:
    check("t26-pixel-photometry-sample", False, f"only {len(bright_pred)} matched")

print(f"\nsky-pixel suite: {'ALL GREEN' if not failures else f'{len(failures)} FAILURE(S)'}")
sys.exit(1 if failures else 0)
