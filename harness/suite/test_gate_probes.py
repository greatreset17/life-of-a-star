#!/usr/bin/env python3
"""Suite tests 31, 36 (cross-regime identity), 48 (gate completeness) —
run against the newest gate capture set: the probes ARE the evidence."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CAPS = ROOT / "harness" / "captures"

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


labels = sorted([d for d in CAPS.iterdir() if d.is_dir() and (d / "summary.json").exists()],
                key=lambda d: (d / "summary.json").stat().st_mtime)
cap = labels[-1]
print(f"      [capture set: {cap.name}]")
summary = json.loads((cap / "summary.json").read_text())

# --- test 48: every capture carries its probe; a screenshot without one
# would have been refused by the gate — verify the artefacts agree
probes = {}
for c in summary["captures"]:
    wp = c["waypoint"]
    png = cap / f"{wp}.png"
    pj = cap / f"{wp}.probe.json"
    check(f"t48-{wp}-probe-present", c["ok"] and png.exists() and pj.exists(),
          "capture without probe")
    if pj.exists():
        probes[wp] = json.loads(pj.read_text())["probe"]

req = set(summary["assumptions"]["probe_required_keys"])
for wp, p in probes.items():
    missing = req - set(p)
    check(f"t48-{wp}-probe-complete", not missing, f"missing {missing}")

# --- test 36: derived vs rendered granule counts are separate numbers,
# rendered never exceeds derived, and the derived value matches the
# pipeline table at that waypoint (cross-regime identity: one derivation)
track = json.loads((ROOT / "app/data/track.json").read_text())
for wp, p in probes.items():
    gd = float(p["granules_derived"])
    gr = float(p["granules_rendered"])
    check(f"t36-{wp}-rendered-le-derived", gr <= gd * 1.001, f"{gr} > {gd}")
    s = float(p["s"])
    # nearest spine node to the probe's s
    sn = track["s"]
    i = min(range(len(sn)), key=lambda k: abs(sn[k] - s))
    want = track["granule_n_disk"][i]
    check(f"t36-{wp}-derived-matches-pipeline", abs(gd / want - 1) < 0.05,
          f"probe {gd:.3e} vs table {want:.3e}")

# --- test 31: adaptation monotonicity — visible star count decreases with
# the field brightness; no capture pairs a saturated photosphere with a
# populated star field
rows = []
for wp, p in probes.items():
    lum = 10 ** float(p["log_l"])
    rows.append((wp, lum, float(p["sky_visible"]), float(p["adaptation"])))
sat = [(w, l, v) for w, l, v, a in rows if l > 100.0]
for w, l, v in sat:
    check(f"t31-{w}-no-starfield-when-bright", v <= 30,
          f"L={l:.0f} Lsun yet {v:.0f} stars visible")
bright_v = [v for _, l, v, _ in rows if l > 100]
dim_v = [v for _, l, v, _ in rows if l < 1.0]
if bright_v and dim_v:
    check("t31-dimmer-shows-more", max(bright_v) <= max(dim_v) + 1,
          f"bright max {max(bright_v)}, dim max {max(dim_v)}")

print(f"\ngate-probe suite: {'ALL GREEN' if not failures else f'{len(failures)} FAILURE(S)'}")
sys.exit(1 if failures else 0)
