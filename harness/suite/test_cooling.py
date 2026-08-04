#!/usr/bin/env python3
"""Suite tests 18–24 (Stage 0 portion) — the cooling extension. Written
before pipeline/cooling.py existed. The join tolerance starts at the brief's
1%; if the two published codes genuinely disagree by more, the fork-14
pattern applies and the correction is recorded, never silent."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.constants import COOLEST_WD_OBSERVED_K, TERMINUS_TEFF_K  # noqa: E402
from pipeline.cooling import CoolingSpine  # noqa: E402
from pipeline.track import Track  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        failures.append(name)


tr = Track.load()
cs = CoolingSpine.build(tr)

# --- test 18 (corrected per fork 11, measured): Teff and time are matched
# across the join by construction; L and R belong to two independent codes
# whose young-WD envelopes differ, and their measured discontinuity
# (dL/L = -7.8%, dR/R = -4.2%) is asserted within bounds that would still
# catch a wrong bracketing mass or a units slip (those produce >20%), and
# is REPORTED in the panel and marked in the HR diagram, never smoothed.
j = cs.join_report
check("t18-join-teff-continuous", abs(j["dteff_frac"]) < 1e-6, f"dTeff={j['dteff_frac']:.2e}")
check("t18-join-age-continuous", abs(j["dage_yr"]) < 1.0, f"dage={j['dage_yr']:.1f} yr")
check("t18-join-L-two-codes-bounded", abs(j["dl_frac"]) < 0.12, f"dL/L = {j['dl_frac']:+.4f}")
check("t18-join-R-two-codes-bounded", abs(j["dr_frac"]) < 0.06, f"dR/R = {j['dr_frac']:+.4f}")
print(f"      [fork 11: join at {j['teff_k']:.0f} K, dL/L={j['dl_frac']:+.3%}, "
      f"dR/R={j['dr_frac']:+.3%} — two published codes, reported on-screen]")
# first derivative of log L with respect to arc length keeps its sign
ji = cs.join_index
dl_before = cs.log_l[ji - 1] - cs.log_l[ji - 2]
dl_after = cs.log_l[ji + 1] - cs.log_l[ji]
check("t18-join-derivative-sign", dl_before * dl_after > 0,
      f"dlogL steps {dl_before:+.4f} / {dl_after:+.4f}")

# --- test 22: data horizon integrity
teff = cs.teff
state = np.array(cs.data_state)
h = cs.horizon_index
check("t22-horizon-at-last-tabulated", state[h] == "tabulated" and state[h + 1] == "extrapolated",
      f"states around horizon: {state[max(0, h - 1):h + 3]}")
check("t22-state-changes-once", int(np.sum(state[:-1] != state[1:])) == 1,
      f"{np.sum(state[:-1] != state[1:])} changes")
# anchoring: value and first derivative at the horizon within 1%
check("t22-anchor-value", abs(cs.regionb_anchor["dvalue_frac"]) < 0.01,
      f"{cs.regionb_anchor['dvalue_frac']:.4f}")
check("t22-anchor-derivative", abs(cs.regionb_anchor["dderiv_frac"]) < 0.01,
      f"{cs.regionb_anchor['dderiv_frac']:.4f}")

# --- test 21: terminus and travel budget
check("t21-terminus", abs(teff[-1] - TERMINUS_TEFF_K) < 1.0, f"end Teff={teff[-1]:.1f}")
check("t21-arc-finite", np.isfinite(cs.s).all() and cs.s[-1] == 1.0, "")
# no single phase above its cap: cooling tail (join onward) and region B
frac_cool = 1.0 - cs.s[cs.join_index]
frac_b = 1.0 - cs.s[h]
check("t21-cooling-tail-cap", frac_cool < 0.45, f"cooling tail arc share {frac_cool:.3f}")
check("t21-regionb-cap", frac_b < 0.15, f"region B arc share {frac_b:.3f}")

# --- test 20: crystallisation shoulder — dTeff/dt not monotonic across it
ages = cs.age_yr
xf = cs.crystal_frac
in_x = (xf > 0.02) & (xf < 0.98) & (np.array(cs.data_state) == "tabulated")
rate = np.gradient(teff, ages)
r_in = rate[in_x]
check("t20-shoulder-nonmonotonic", bool((np.diff(r_in) > 0).any() and (np.diff(r_in) < 0).any()),
      "dTeff/dt monotonic across crystallisation")

# --- test 19: latent-heat delay ~ Gyr against a Mestel extrapolation of the
# pre-onset cooling (the suppressed comparison is TEST machinery, not physics)
onset = int(np.argmax(xf > 0.01))
done = int(np.argmax(xf > 0.97))
t_actual = ages[done] - ages[onset]
pre = slice(max(cs.join_index + 5, onset - 40), onset)
# Mestel-like: t ∝ Teff^(-7/2)  =>  fit t = A*T^-3.5 + B on pre-onset data
A = np.vstack([teff[pre] ** -3.5, np.ones(len(ages[pre]))]).T
coef, *_ = np.linalg.lstsq(A, ages[pre], rcond=None)
t_mestel = (coef[0] * teff[done] ** -3.5 + coef[1]) - (coef[0] * teff[onset] ** -3.5 + coef[1])
delay = (t_actual - t_mestel) / 1e9
check("t19-latent-heat-delay-gyr", 0.4 < delay < 6.0,
      f"actual {t_actual / 1e9:.2f} Gyr vs Mestel-extrapolated {t_mestel / 1e9:.2f} Gyr -> delay {delay:.2f} Gyr")
print(f"      [crystallisation: onset {teff[onset]:.0f} K, complete {teff[done]:.0f} K, "
      f"delay {delay:.2f} Gyr vs suppressed extrapolation]")

# --- tests 23, 24: the two epochal markers
mk = cs.markers
check("t23-present-on-ms", mk["present_day"]["phase"] == "main sequence",
      mk["present_day"]["phase"])
check("t23-present-age", abs(mk["present_day"]["age_yr"] - 4.57e9) < 5e7,
      f"{mk['present_day']['age_yr']:.3e}")
ex = mk["existence"]
check("t24-existence-below-coolest-observed", ex["teff_k"] <= COOLEST_WD_OBSERVED_K,
      f"{ex['teff_k']:.0f} K")
check("t24-existence-after-crystallisation-complete", ex["age_yr"] > ages[done],
      f"marker at {ex['age_yr']:.3e} vs completion {ages[done]:.3e}")
check("t24-existence-tabulated-region", ex["data_state"] == "tabulated", ex["data_state"])

print(f"\ncooling suite: {'ALL GREEN' if not failures else f'{len(failures)} FAILURE(S)'}")
sys.exit(1 if failures else 0)
