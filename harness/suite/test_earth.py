#!/usr/bin/env python3
"""Suite tests 7, 8, 9, 14, 43, 44, 45 — Earth's fate. Written before
pipeline/earth.py existed.

Bands follow fork 14: MIST v1.2's own mass history (eta_R = 0.1) governs;
Schroeder & Connon Smith 2008 values are REPORTED comparisons, not targets.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.constants import AU_M, R_SUN_M  # noqa: E402
from pipeline.earth import EarthOrbit, sc05_rate  # noqa: E402
from pipeline.track import Track  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


tr = Track.load()

# --- test 14: mass closure within the one prescription — the track's own
# star_mdot column integrates to its own star_mass column
age = tr.col("star_age")
mdot = tr.col("star_mdot")  # Msun/yr, negative
m = tr.col("star_mass")
m_rec = m[0] + np.concatenate([[0.0], np.cumsum(0.5 * (mdot[1:] + mdot[:-1]) * np.diff(age))])
closure = float(np.abs(m_rec[-1] - m[-1]))
check("t14-mass-closure", closure < 0.01, f"|integral - column| = {closure:.5f} Msun")

# RGB mass loss from the track itself (fork 14: eta_R=0.1 -> small)
dm_rgb = float(m[tr.anchors["tams"] - 1] - m[tr.anchors["rgb_tip"] - 1])
check("t08-rgb-mass-loss-track-band", 0.02 <= dm_rgb <= 0.09, f"dM_RGB = {dm_rgb:.4f} Msun")
print(f"      [S&CS 2008 comparison: track RGB loss {dm_rgb:.3f} vs their 0.332 Msun — "
      f"mass-loss prescription divergence, reported per fork 10/14]")

# --- the integration
eo = EarthOrbit(tr)
res = eo.integrate()
check("t09-engulfment-occurs", res["engulfed"], "Earth survived — effect 1 alone? (failure state 6)")
t_eng_from_present = (res["t_engulf_yr"] - 4.57e9) / 1e9
check("t09-engulfment-time-band", 6.4 <= t_eng_from_present <= 7.5,
      f"{t_eng_from_present:.3f} Gyr from present")
print(f"      [engulfment {t_eng_from_present:.3f} Gyr from present; S&CS 7.59 — offset "
      f"{t_eng_from_present - 7.59:+.2f} Gyr, a fact about two codes, displayed in-panel]")

# --- the drag toggle (corrected per fork 21, measured): on THIS track the
# no-drag Earth is ALSO engulfed — MIST v1.2's weak RGB mass loss leaves the
# orbit at ~1.36 AU while the AGB reaches 1.64 AU, so geometry alone closes
# the gap on the AGB. What drag changes is WHEN and WHERE: tides capture the
# Earth ~130 Myr earlier, at the RGB tip. Both facts are asserted; the
# S&CS narrative (no-drag survival) is reported as prescription divergence.
res_nodrag = eo.integrate(drag=False)
age_tip = tr.col("star_age")[tr.anchors["rgb_tip"] - 1]
check("t09-no-drag-still-engulfed-by-agb-geometry", res_nodrag["engulfed"],
      "no-drag Earth survived — not this track's answer")
check("t09-drag-kills-at-rgb-tip", abs(res["t_engulf_yr"] - age_tip) < 2e7,
      f"drag engulfment at {res['t_engulf_yr']:.4e} vs RGB tip {age_tip:.4e}")
check("t09-no-drag-death-later-on-agb",
      res_nodrag["t_engulf_yr"] - res["t_engulf_yr"] > 5e7
      and res_nodrag["t_engulf_yr"] > age_tip + 5e7,
      f"no-drag at {res_nodrag['t_engulf_yr']:.4e}")
print(f"      [fork 21: drag -> RGB-tip death at {res['t_engulf_yr'] / 1e9:.4f} Gyr; "
      f"no drag -> AGB death at {res_nodrag['t_engulf_yr'] / 1e9:.4f} Gyr; "
      f"the toggle decides WHEN and WHERE, not WHETHER]")

# --- test 7 + 44: with drag off, a*(M+m) conserved to stated tolerance and
# ledger attributes; with drag on, change fully attributed
aM0 = res_nodrag["a_yr"][0] * res_nodrag["M_yr"][0]
aM1 = res_nodrag["a_yr"][-1] * res_nodrag["M_yr"][-1]
drift = abs(aM1 / aM0 - 1.0)
check("t07-aM-invariant-nodrag", drift < 1e-4, f"a*M drift = {drift:.2e}")
led = res["ledger"]
resid = abs(led["residual_frac"])
check("t44-ledger-closure", resid < 1e-3,
      f"unattributed residual = {resid:.2e} of total da")
check("t44-effects-recorded", set(led["attributed"]) == {"massloss", "tide", "drag"},
      str(led["attributed"].keys()))

# --- test 45: discrimination machinery against a deliberate bookkeeping error
d = eo.discriminate()
check("t45-intact-numerical", d["intact"]["verdict"] == "numerical", json.dumps(d["intact"]))
check("t45-broken-bookkeeping", d["broken"]["verdict"] == "bookkeeping-or-physics",
      json.dumps(d["broken"]))

# --- test 43: the engulfment crossing is solved INSIDE the integration
# (event time differs from every output-grid node, and neither a finer
# output grid nor a tighter tolerance moves it)
tg = res["t_engulf_yr"]
check("t43-event-not-on-grid", float(np.min(np.abs(res["t_yr"] - tg))) > 0.0,
      "event time coincides exactly with an output node")
res_fine = eo.integrate(n_out=8000, rtol=1e-10)
check("t43-event-solver-independent",
      abs(res_fine["t_engulf_yr"] - tg) < 2e5,
      f"dt_event = {abs(res_fine['t_engulf_yr'] - tg):.1e} yr under refinement")

# --- Schroeder & Cuntz 2005 comparison rate: evaluated, not integrated
sc = sc05_rate(tr)
i_tip = tr.anchors["rgb_tip"] - 1
ratio = abs(sc[i_tip]) / max(abs(mdot[i_tip]), 1e-30)
check("t08-sc05-order-of-magnitude", 0.05 < ratio < 50,
      f"SC05/track at RGB tip = {ratio:.2f}")

# --- the shipped event table's capture radius must equal R(track) at the
# event time BY DEFINITION of the terminal condition (the coarse-output-grid
# readout bug reported 0.99 AU where the truth was 0.75 — caught by external
# review against failure state 8)
import json as _json  # noqa: E402

etab = _json.loads((ROOT / "app/data/earth.json").read_text())
for key in ("engulf_drag", "engulf_nodrag"):
    ev2 = etab[key]
    r_here = float(10 ** np.interp(ev2["t_yr"], tr.col("star_age"), tr.col("log_R"))
                   * R_SUN_M / AU_M)
    check(f"t09-{key}-capture-radius-is-track-R",
          abs(ev2["a_au"] / r_here - 1) < 0.01,
          f"table {ev2['a_au']:.4f} vs track R {r_here:.4f} AU")
m = etab["meta"]
check("t08-rgb-tip-radius-exported", abs(m["r_rgb_tip_au"] - 0.803) < 0.01,
      f"{m['r_rgb_tip_au']}")
check("t08-agb-exceeds-rgb-tip-recorded", m["r_agb_max_au"] > m["r_rgb_tip_au"],
      "fork 14: the track's AGB outgrows its RGB tip")
check("t09-nodrag-miss-and-overrun-positive",
      m["nodrag_rgb_miss_au"] > 0 and m["nodrag_agb_overrun_au"] > 0,
      str(m))
print(f"      [no drag: clears the RGB tip by {m['nodrag_rgb_miss_au']:.3f} AU; "
      f"the AGB reaches {m['nodrag_agb_overrun_au']:.3f} AU beyond the orbit anyway]")

# --- Tier 1 mirror: the averaged mass-loss expansion against the harness's
# direct vector integrator (v0.0), over a short window with an amplified
# constant rate — two implementations, two formulations, one answer
sys.path.insert(0, str(ROOT / "harness"))
from mirror import OrbitMirror  # noqa: E402

M_SUN, AU, YR = 1.98892e30, 1.495978707e11, 3.15576e7
G = 6.67430e-11
tau = 2e4 * YR  # lose 1.5% over 300 yr — fast but adiabatic (P=1 yr << tau)
om = OrbitMirror(M_SUN)
mass_fn = lambda t: (M_SUN * (1 - t / tau), -M_SUN / tau)
vc = np.sqrt(G * M_SUN / AU)
_, _, a_direct, M1, _ = om.integrate([AU, 0, 0], [0, vc, 0], 0.0, 300 * YR,
                                     mass_fn, nsteps=300 * 600)
a_avg = AU * M_SUN / M1  # averaged prediction: a*M conserved
rel = abs(a_direct / a_avg - 1.0)
check("t07-mirror-vector-vs-averaged", rel < 1e-3,
      f"direct {a_direct / AU:.6f} AU vs averaged {a_avg / AU:.6f} AU (rel {rel:.2e})")

print(f"\nearth suite: {'ALL GREEN' if not failures else f'{len(failures)} FAILURE(S)'}")
sys.exit(1 if failures else 0)
