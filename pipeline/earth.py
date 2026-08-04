"""Earth's orbital evolution under three simultaneous effects — fork 10:
M(t) is the track's own star_mass and nothing else; Schroeder & Cuntz enters
as an evaluated comparison, never a second integration.

Orbit-averaged evolution of the semi-major axis (circular orbit, e=0,
declared):

  (1/a) da/dt =  - Mdot/(M+m)                                [mass loss]
                 - (12/21) f_red (M_env/M) q(1+q) (R/a)^8 / tau_f   [tide]
                 - 2 F_drag v a / (G (M+m) m_E) / a * a      [ram drag]

  tau_f  = (M_env R^2 / L)^(1/3)      convective friction time (Zahn 1977/89)
  f_red  = min(1, (P_orb / (2 tau_f))^2)   Goldreich–Nicholson reduction
  q      = m_E / M
  F_drag = 0.5 C_d pi R_E^2 rho v_rel^2;  rho = |Mdot_wind|/(4 pi a^2 v_wind)

Direct N-body integration over 1e10 orbits is impossible and is not
attempted; the harness's vector mirror validates the averaged rates over
short windows instead (Tier 1). The integration is RK45 by step control,
NOT symplectic, and is not called symplectic (fork 7); the per-effect
attribution ledger and dt-scaling discrimination carry the conservation
monitoring (suite tests 44, 45).

Engulfment is a solve_ivp terminal EVENT — a sign change of a - R_star
solved inside the step, never a comparison at output-grid boundaries
(suite test 43). The inspiral inside the envelope is beyond the declared
boundary: the piece ends the orbit at photospheric contact.
"""
import numpy as np
from scipy.integrate import solve_ivp

from .constants import AU_M, G_SI, L_SUN_W, M_SUN_KG, R_SUN_M, YEAR_S

M_EARTH_KG = 5.9722e24
R_EARTH_M = 6.371e6
C_DRAG = 1.0  # order-unity drag coefficient, declared
TIDE_PREFACTOR = 12.0 / 21.0  # 6 * (2/21), Zahn convective-envelope calibration


class EarthOrbit:
    def __init__(self, track):
        self.tr = track
        t = track.col("star_age")
        # strictly increasing time grid for interpolation
        keep = np.concatenate([[True], np.diff(t) > 0])
        self.t = t[keep]
        cols = ["star_mass", "star_mdot", "log_L", "log_R", "he_core_mass",
                "v_wind_Km_per_s"]
        self.c = {k: track.col(k)[keep] for k in cols}

    def _interp(self, key, t):
        return np.interp(t, self.t, self.c[key])

    def rates(self, t, a_m, drag=True, ledger_massloss=True):
        """Returns (da/dt total [m/yr], per-effect dict)."""
        M = self._interp("star_mass", t) * M_SUN_KG
        Mdot = self._interp("star_mdot", t) * M_SUN_KG / YEAR_S  # kg/s, <=0
        L = 10 ** self._interp("log_L", t) * L_SUN_W
        R = 10 ** self._interp("log_R", t) * R_SUN_M
        Menv = max((self._interp("star_mass", t) - self._interp("he_core_mass", t)), 0.0) * M_SUN_KG
        mu = G_SI * (M + M_EARTH_KG)

        # effect 1: mass loss
        d_ml = -(Mdot / (M + M_EARTH_KG)) * a_m  # m/s (positive: expansion)

        # effect 2: equilibrium tide into the convective envelope
        d_tide = 0.0
        if Menv > 0 and L > 0:
            tau_f = (Menv * R * R / L) ** (1.0 / 3.0)
            p_orb = 2 * np.pi * np.sqrt(a_m ** 3 / mu)
            f_red = min(1.0, (p_orb / (2.0 * tau_f)) ** 2)
            q = M_EARTH_KG / M
            d_tide = -TIDE_PREFACTOR * f_red * (Menv / M) * q * (1 + q) \
                * (R / a_m) ** 8 / tau_f * a_m  # m/s, < 0

        # effect 3: ram-pressure drag against the wind
        d_drag = 0.0
        if drag and Mdot < 0:
            v_wind = max(self._interp("v_wind_Km_per_s", t), 1e-3) * 1e3
            rho = -Mdot / (4 * np.pi * a_m ** 2 * v_wind)
            v_orb = np.sqrt(mu / a_m)
            v_rel2 = v_orb ** 2 + v_wind ** 2
            f = 0.5 * C_DRAG * np.pi * R_EARTH_M ** 2 * rho * v_rel2
            d_drag = -2.0 * f * np.sqrt(v_rel2) * a_m ** 2 / (mu * M_EARTH_KG) * 1.0

        parts = {"massloss": d_ml if ledger_massloss else 0.0,
                 "tide": d_tide if drag else 0.0,
                 "drag": d_drag if drag else 0.0}
        total = d_ml + (d_tide if drag else 0.0) + (d_drag if drag else 0.0)
        return total * YEAR_S, parts  # m per year

    def integrate(self, drag=True, a0_au=1.0, rtol=1e-9, n_out=2000):
        """State vector [a, I_massloss, I_tide, I_drag]: the attribution
        ledger is integrated BY the same adaptive scheme as the orbit, so
        closure a(t)-a0 = sum(I_k) holds to solver tolerance and the
        unattributed residual measures the integrator, not the quadrature."""
        t0, t1 = float(self.t[0]), float(self.t[-1])

        def rhs(t, y):
            a = max(y[0], 1e3)
            dadt, parts = self.rates(t, a, drag=drag)
            return [dadt, parts["massloss"] * YEAR_S / 1.0,
                    parts["tide"] * YEAR_S / 1.0, parts["drag"] * YEAR_S / 1.0]

        def hit(t, y):
            r_m = 10 ** self._interp("log_R", t) * R_SUN_M
            return y[0] - r_m
        hit.terminal = True
        hit.direction = -1

        t_eval = np.geomspace(max(t0, 1e3), t1, n_out)
        sol = solve_ivp(rhs, (t0, t1), [a0_au * AU_M, 0.0, 0.0, 0.0],
                        method="RK45", rtol=rtol, atol=1.0, t_eval=t_eval,
                        events=hit, max_step=(t1 - t0) / 400)
        tt, aa = sol.t, sol.y[0]
        led = {"massloss": float(sol.y[1, -1]), "tide": float(sol.y[2, -1]),
               "drag": float(sol.y[3, -1])}
        da_total = aa[-1] - aa[0]
        attributed = sum(led.values())
        engulfed = len(sol.t_events[0]) > 0
        return {
            "engulfed": engulfed,
            "t_engulf_yr": float(sol.t_events[0][0]) if engulfed else None,
            "t_yr": tt, "a_m": aa,
            "a_yr": aa / AU_M,
            "M_yr": np.interp(tt, self.t, self.c["star_mass"]),
            "ledger": {
                "attributed": led,
                "residual_frac": float((da_total - attributed) / max(abs(da_total), 1e-30)),
            },
        }

    def discriminate(self, broken_effect="tide"):
        """Test-45 machinery: tighten the solver tolerance tenfold — a
        numerical residual falls with it; a bookkeeping residual (an effect
        acting but dropped from the attribution) does not."""
        def resid(rtol, broken):
            r = self.integrate(rtol=rtol)
            led = dict(r["ledger"]["attributed"])
            att = sum(led.values()) - (led[broken_effect] if broken else 0.0)
            da = r["a_m"][-1] - r["a_m"][0]
            return abs((da - att) / max(abs(da), 1e-30))

        out = {}
        floor = 1e-10  # below this, the residual is rounding noise: numerical
        for name, broken in (("intact", False), ("broken", True)):
            r1, r2 = resid(1e-7, broken), resid(1e-9, broken)
            ratio = max(r1, 1e-16) / max(r2, 1e-16)
            if r1 < floor and r2 < floor:
                verdict = "numerical"  # at the machine floor; nothing to scale
            else:
                verdict = "numerical" if ratio > 5.0 else "bookkeeping-or-physics"
            out[name] = {"r_loose": r1, "r_tight": r2, "ratio": float(ratio),
                         "verdict": verdict}
        return out


def sc05_rate(track):
    """Schroeder & Cuntz 2005 mass-loss rate EVALUATED along the track for
    the panel's prescription-divergence readout (Msun/yr, negative).
    Never integrated (fork 10)."""
    eta = 8e-14
    L = 10 ** track.col("log_L")
    R = 10 ** track.col("log_R")
    M = track.col("star_mass")
    T = 10 ** track.col("log_Teff")
    g_ratio = 10 ** 4.4377 / np.maximum(10 ** track.col("log_g"), 1e-10)
    return -eta * L * R / M * (T / 4000.0) ** 3.5 * (1.0 + g_ratio / 4300.0)
