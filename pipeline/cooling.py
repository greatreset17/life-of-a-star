"""The cooling extension — Montreal (Bedard et al. 2020) sequences
interpolated to the mass the track actually leaves behind, joined to the
MIST spine, continued past the data horizon under one named analytic law
(region B), and integrated into a single arc-length parameterisation to the
declared terminus.

fork 11 (the join): MIST's WDCS end (Teff 47623 K) lies inside the Montreal
sequences' range. Matched across the join: Teff (the cooling spine begins at
exactly MIST's final Teff) and time (the sequence age axis is offset so the
join is simultaneous). Checked, not matched: L and R — two independent codes
meet here and their discontinuity is measured and asserted small (test 18).

fork 9 (region B): beyond the last tabulated point, Debye-regime cooling —
Teff(t) = T_h exp(-(t - t_h)/tau) with tau = -T_h / (dTeff/dt)|_h taken from
the last tabulated interval, R frozen at the horizon value, L = 4 pi R^2
sigma Teff^4. Anchored in value and first derivative by construction; the
panel state changes exactly once, at the horizon; region B is labelled for
its entire duration and drawn lighter in the HR diagram.

fork 2 (terminus and horizon): the data horizon is where Bedard et al. end
(~1470 K, the coolest tabulated model); the terminus is TERMINUS_TEFF_K,
declared in constants with its reason. The existence marker is the crossing
below COOLEST_WD_OBSERVED_K, inside the tabulated region.
"""
import re
from pathlib import Path

import numpy as np

from . import sources
from .arclength import ArcLength
from .constants import (COOLEST_WD_OBSERVED_K, L_SUN_W, R_SUN_M, SIGMA_SB,
                        TERMINUS_TEFF_K)

L_SUN_CGS = 3.828e33  # erg/s (IAU nominal, matching the Montreal L column)


def parse_seq(path):
    """Montreal seq_* file -> dict of arrays. Record = 3 wrapped lines:
    Mod Teff logg R[cm] Age[yr] L[erg/s] / logTc logPc logrhoc Mx/M logqx /
    Lnu logH logHe logC logO."""
    txt = Path(path).read_text()
    num = r"([\d.E+-]+)"
    pat = (rf"^\s*(\d+)\s+{num}\s+{num}\s+{num}\s+{num}\s+{num}\s*\n"
           rf"\s*{num}\s+{num}\s+{num}\s+{num}\s+{num}\s*\n"
           rf"\s*{num}\s+{num}\s+{num}\s+{num}\s+{num}")
    rows = np.array([[float(v) for v in m] for m in re.findall(pat, txt, re.M)])
    return {
        "teff": rows[:, 1], "logg": rows[:, 2], "r_cm": rows[:, 3],
        "age": rows[:, 4], "l_cgs": rows[:, 5], "log_tc": rows[:, 6],
        "crystal": rows[:, 9],
    }


class CoolingSpine:
    """The full spine: MIST rows + cooling rows + region B rows, with
    per-node data_state, crystallised fraction, and the two markers."""

    @classmethod
    def build(cls, track, n_regionb=40):
        self = cls()
        s050 = parse_seq(sources.require("montreal_seq_050"))
        s055 = parse_seq(sources.require("montreal_seq_055"))
        m_final = float(track.col("star_mass")[-1])
        w = (m_final - 0.50) / 0.05  # weight toward the 0.55 sequence

        # interpolate each sequence onto a common descending-Teff grid, then
        # blend in mass at fixed Teff
        t_hi = min(s050["teff"].max(), s055["teff"].max())
        t_lo = max(s050["teff"].min(), s055["teff"].min())
        teff_grid = np.geomspace(t_hi, t_lo, 400)

        def at(seq, key):
            o = np.argsort(seq["teff"])
            return np.interp(teff_grid, seq["teff"][o], seq[key][o])

        cool = {k: (1 - w) * at(s050, k) + w * at(s055, k)
                for k in ("logg", "r_cm", "age", "l_cgs", "crystal")}

        # ---- the join (fork 11)
        mist_end_teff = 10 ** track.col("log_Teff")[-1]
        mist_end_age = track.col("star_age")[-1]
        mist_end_l = 10 ** track.col("log_L")[-1]
        mist_end_r = 10 ** track.col("log_R")[-1]
        keep = teff_grid < mist_end_teff
        age_at_join = float(np.interp(-mist_end_teff, -teff_grid, cool["age"]))
        l_at_join = float(np.interp(-mist_end_teff, -teff_grid, cool["l_cgs"])) / L_SUN_CGS
        r_at_join = float(np.interp(-mist_end_teff, -teff_grid, cool["r_cm"])) * 1e-2 / R_SUN_M
        self.join_report = {
            "teff_k": mist_end_teff,
            "dteff_frac": 0.0,
            "dage_yr": 0.0,
            "dl_frac": l_at_join / mist_end_l - 1.0,
            "dr_frac": r_at_join / mist_end_r - 1.0,
        }

        c_teff = teff_grid[keep]
        c_age = cool["age"][keep] - age_at_join + mist_end_age
        c_logl = np.log10(cool["l_cgs"][keep] / L_SUN_CGS)
        c_logr = np.log10(cool["r_cm"][keep] * 1e-2 / R_SUN_M)
        c_logg = cool["logg"][keep]
        c_xf = cool["crystal"][keep]

        # ---- region B (fork 9)
        t_h = float(c_teff[-1])
        dtdt_h = (c_teff[-1] - c_teff[-2]) / (c_age[-1] - c_age[-2])
        tau = -t_h / dtdt_h
        r_h = 10 ** c_logr[-1]
        b_teff = np.geomspace(t_h, TERMINUS_TEFF_K, n_regionb + 1)[1:]
        b_age = c_age[-1] + tau * np.log(t_h / b_teff)
        b_logl = np.log10(4 * np.pi * (r_h * R_SUN_M) ** 2 * SIGMA_SB * b_teff ** 4 / L_SUN_W)
        # anchoring self-check: value exact by construction; derivative vs table
        dtdt_law = -t_h / tau
        self.regionb_anchor = {
            "tau_yr": tau,
            "dvalue_frac": 0.0,
            "dderiv_frac": dtdt_law / dtdt_h - 1.0,
        }

        # ---- assemble the full spine
        n_mist = track.n
        self.teff = np.concatenate([10 ** track.col("log_Teff"), c_teff, b_teff])
        self.log_l = np.concatenate([track.col("log_L"), c_logl, b_logl])
        self.log_r = np.concatenate([track.col("log_R"), c_logr,
                                     np.full(n_regionb, np.log10(r_h))])
        self.log_g = np.concatenate([track.col("log_g"), c_logg,
                                     np.full(n_regionb, c_logg[-1])])
        self.age_yr = np.concatenate([track.col("star_age"), c_age, b_age])
        self.mass = np.concatenate([track.col("star_mass"),
                                    np.full(len(c_teff) + n_regionb, m_final)])
        self.phase = np.concatenate([track.col("phase"),
                                     np.full(len(c_teff) + n_regionb, 10.0)])
        self.crystal_frac = np.concatenate([np.zeros(n_mist), c_xf,
                                            np.full(n_regionb, c_xf[-1])])
        self.data_state = (["tabulated"] * (n_mist + len(c_teff))
                           + ["extrapolated"] * n_regionb)
        self.join_index = n_mist  # first cooling node
        self.horizon_index = n_mist + len(c_teff) - 1  # last tabulated node
        self.n = len(self.teff)

        # ---- arc length over the whole spine, to the terminus and no further
        al = ArcLength.from_xy(np.log10(self.teff), self.log_l)
        self.s = al.s_of_eep(np.arange(1, self.n + 1, dtype=float))
        self.arc = al

        # ---- the two epochal markers, from the elapsed-time and temperature
        # integrals (never captions)
        # the present is the interpolated INSTANT 4.57 Gyr, not the nearest
        # EEP row (which sits 28 Myr early — 28 Myr of real orbital
        # phase-mixing makes that a visibly different sky)
        i_now = int(np.argmin(np.abs(track.col("star_age") - 4.57e9)))
        s_now = float(np.interp(4.57e9, self.age_yr, self.s))
        # existence: first crossing below the coolest observed white dwarf,
        # searched only in the cooling tail
        tail = slice(self.join_index, self.n)
        below = np.where(self.teff[tail] < COOLEST_WD_OBSERVED_K)[0]
        i_ex = self.join_index + int(below[0])
        # solve the crossing time by local inversion (not a node comparison)
        i0 = i_ex - 1
        f = (COOLEST_WD_OBSERVED_K - self.teff[i0]) / (self.teff[i_ex] - self.teff[i0])
        t_cross = self.age_yr[i0] + f * (self.age_yr[i_ex] - self.age_yr[i0])
        s_cross = self.s[i0] + f * (self.s[i_ex] - self.s[i0])
        self.markers = {
            "present_day": {
                "age_yr": 4.57e9,
                "s": s_now,
                "phase": "main sequence" if track.col("phase")[i_now] == 0.0 else "not-ms",
            },
            "existence": {
                "teff_k": COOLEST_WD_OBSERVED_K,
                "age_yr": float(t_cross),
                "s": float(s_cross),
                "data_state": self.data_state[i0],
            },
        }
        return self
