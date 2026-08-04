#!/usr/bin/env python3
"""Visual metrics measured from the gate captures themselves (suite tests
41 + the critic's attack counter-tests). Philosophy: per-phase acceptance
RANGES, membership not convergence; ranges were measured on an accepted
build and DECLARED — a later build must stay in range, not equal a number.

  granule pitch    autocorrelation of the disk-centre crop vs the pitch the
                   probe's own numbers predict (closes critic attack 2: a
                   shader-side cell-size change the CPU probes cannot see)
  luminance budget mean background luminance per phase (closes attack 3:
                   quiet brightening of the nebula/void outside any probe)
  paint metrics    lane depth ratio and stroke variation at disk centre
  ending quiet     16-px block mottle at the terminus

Run with --measure to print raw values without judging.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent.parent
CAPS = ROOT / "harness" / "captures"

failures = []
MEASURE = "--measure" in sys.argv


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


labels = sorted([d for d in CAPS.iterdir() if d.is_dir() and (d / "summary.json").exists()],
                key=lambda d: (d / "summary.json").stat().st_mtime)
cap = labels[-1]
print(f"      [capture set: {cap.name}]")
track = json.loads((ROOT / "app/data/track.json").read_text())


def lum(png):
    a = np.asarray(Image.open(png).convert("RGB"), float)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def probe(wp):
    return json.loads((cap / f"{wp}.probe.json").read_text())["probe"]


# geometry of the gated frame: 1280x800, fov 40 deg, cam_d = 4 photospheric
# radii, star centred at (640, 400)
H, FOV, CAM_D = 800, 40.0, 4.0
disk_r_px = np.tan(np.arcsin(1.0 / CAM_D)) / np.tan(np.radians(FOV / 2)) * (H / 2)

# ---- granule pitch (attack-2 counter-test) on the resolved-cell phases
for wp in ("rgb_tip", "agb_thermal_pulses"):
    png = cap / f"{wp}.png"
    if not png.exists():
        continue
    p = probe(wp)
    s = float(p["s"])
    sn = track["s"]
    i = min(range(len(sn)), key=lambda k: abs(sn[k] - s))
    r_m = 10 ** track["log_R"][i] * 6.957e8
    cell_ang = track["granule_d_m"][i] / r_m          # radians on the surface
    # apparent pitch at disk centre: D / (dist - R) projected to pixels
    pitch_px = cell_ang / (CAM_D - 1.0) / np.tan(np.radians(FOV / 2)) * (H / 2)
    crop = lum(png)[400 - 110:400 + 110, 640 - 110:640 + 110]
    c = crop - crop.mean()
    # radial autocorrelation: first prominent minimum ~ half pitch
    f = np.fft.fft2(c)
    ac = np.fft.ifft2(f * np.conj(f)).real
    ac = np.fft.fftshift(ac) / ac.max()
    cy, cx = np.array(ac.shape) // 2
    prof = np.array([ac[cy, cx + k] for k in range(0, 100)])
    # measured pitch = lag of the first local maximum after the first minimum
    dm = np.where(np.diff(prof) > 0)[0]
    if len(dm) == 0:
        check(f"t41-{wp}-pitch-measurable", MEASURE, "no autocorrelation minimum")
        continue
    k_min = int(dm[0])
    k_max = k_min + int(np.argmax(prof[k_min:k_min + 60]))
    measured = float(k_max)
    if MEASURE:
        print(f"      [{wp}: predicted pitch {pitch_px:.1f}px, measured {measured:.1f}px]")
    else:
        check(f"t41-{wp}-granule-pitch", 0.55 * pitch_px < measured < 1.8 * pitch_px,
              f"measured {measured:.1f}px vs predicted {pitch_px:.1f}px")

# ---- paint metrics at disk centre (giant phases; targets from the critic,
# measured then declared)
for wp in ("rgb_tip", "agb_thermal_pulses"):
    png = cap / f"{wp}.png"
    if not png.exists():
        continue
    crop = lum(png)[400 - 100:400 + 100, 640 - 100:640 + 100]
    p10, p90 = np.percentile(crop, 10), np.percentile(crop, 90)
    ratio = p10 / max(p90, 1e-9)
    spread = float(crop.std() / max(crop.mean(), 1e-9))
    if MEASURE:
        print(f"      [{wp}: lane p10/p90 {ratio:.3f}, std/mean {spread:.3f}]")
    else:
        check(f"t41-{wp}-lane-depth", 0.35 <= ratio <= 0.75, f"p10/p90 = {ratio:.3f}")
        check(f"t41-{wp}-stroke-variation", spread >= 0.05, f"std/mean = {spread:.3f}")

# ---- per-phase background luminance budget (attack-3 counter-test);
# region avoids every UI card and the disk at all phases
REGION = (slice(120, 430), slice(40, 300))
BUDGET = {  # measured on the accepted build, then DECLARED as ranges
    "protostar_contraction": (0.0, 6.0),
    "zams": (0.0, 6.0),
    "present_day": (0.0, 6.0),
    "subgiant": (0.0, 6.0),
    "rgb_tip": (0.0, 8.0),
    "agb_thermal_pulses": (0.0, 8.0),
    "planetary_nebula_peak": (2.0, 60.0),   # the veil: present but faint
    "wd_crystallisation": (0.0, 8.0),
    # floor 2.0 ASSERTS the galaxy's presence at the ending — the build in
    # which the band threshold withheld it measured 1.93 and must fail here
    "black_dwarf_terminus": (2.0, 12.0),
}
for wp, (lo, hi) in BUDGET.items():
    png = cap / f"{wp}.png"
    if not png.exists():
        continue
    m = float(lum(png)[REGION].mean())
    if MEASURE:
        print(f"      [{wp}: background mean {m:.2f}/255]")
    else:
        check(f"t41-{wp}-luminance-budget", lo <= m <= hi, f"mean {m:.2f} not in [{lo},{hi}]")

# ---- nebula veil structure (declared asphericity must read as structure,
# not a flat fill) and the quiet of the ending
png = cap / "planetary_nebula_peak.png"
if png.exists():
    reg = lum(png)[REGION]
    cv = float(reg.std() / max(reg.mean(), 1e-9))
    if MEASURE:
        print(f"      [nebula background CV {cv:.3f}]")
    else:
        check("t41-nebula-veil-structured", cv >= 0.10, f"CV = {cv:.3f}")
png = cap / "black_dwarf_terminus.png"
if png.exists():
    reg = lum(png)[REGION]
    h16 = reg[: reg.shape[0] // 16 * 16, : reg.shape[1] // 16 * 16]
    blocks = h16.reshape(-1, 16, h16.shape[1] // 16, 16).mean(axis=(1, 3))
    mot = float(blocks.std() / max(blocks.mean(), 1e-9))
    if MEASURE:
        print(f"      [terminus block-16 std/mean {mot:.3f}]")
    else:
        check("t41-terminus-quiet", mot <= 0.35, f"block std/mean = {mot:.3f}")

print(f"\nvisual-metrics suite: {'ALL GREEN' if not failures else f'{len(failures)} FAILURE(S)'}")
sys.exit(1 if failures and not MEASURE else 0)
