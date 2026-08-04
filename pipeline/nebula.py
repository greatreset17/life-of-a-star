"""The planetary nebula — interacting winds, a computed ionisation front,
and line-emission colour through the one CIE chain. Solved: the swept shell's
dynamics (thin-shell, energy-driven bubble in the superwind's r^-2 medium),
the time-dependent ionisation balance, the H recombination + [OIII]/[NII]
line spectrum and its chromaticity. Asserted (fork 5): spherical symmetry,
T_e = 1e4 K in the ionised gas, thin-shell thickness 0.1 R_s, O++/N+ ionic
fractions; instabilities and filamentary fine structure are NOT solved.

Wind speeds are DERIVED from the track's own M and R via the escape-speed
relation (the track's v_wind column is unpopulated on the AGB):
  v_slow = 0.5 * v_esc(AGB end)      observed AGB winds run ~0.3-0.5 v_esc
  v_fast(t) = v_esc(core)            CSPN winds run at ~their escape speed
Ejecta mass and the superwind rate are the track's own (fork 10).

Atomic constants (published, cited): case-B alpha_Hbeta = 3.03e-14 cm^3/s,
Halpha/Hbeta = 2.86, Hgamma/Hbeta = 0.468, Hdelta/Hbeta = 0.259 (Osterbrock
& Ferland 2006, T_e = 1e4 K); alpha_B = 2.59e-13 cm^3/s. [OIII]: Omega = 2.29
(collisional strength 3P-1D), E_ul = 2.48 eV, 5007:4959 = 3:1. [NII]:
Omega = 2.64, E_ul = 1.89 eV, 6583:6548 = 3:1.
"""
import gzip
import json
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

from .constants import AU_M, G_SI, K_B, L_SUN_W, M_H, M_SUN_KG, R_SUN_M, YEAR_S

ALPHA_B = 2.59e-19        # m^3/s
ALPHA_HBETA = 3.03e-20    # m^3/s (effective, case B)
H_PLANCK = 6.62607015e-34
C_MS = 2.99792458e8
EV = 1.602176634e-19
T_E = 1.0e4               # K, asserted (fork 5)
SHELL_THICKNESS = 0.1     # of R_s, asserted (fork 5)
V_SLOW_FRACTION = 0.5     # of v_esc at the AGB end, declared
LINES = {  # nm, energy source, ratio-to-reference
    "hbeta": 486.1, "halpha": 656.3, "hgamma": 434.0, "hdelta": 410.2,
    "oiii5007": 500.7, "oiii4959": 495.9, "nii6583": 658.3, "nii6548": 654.8,
}


def q_ionising_table(root):
    """Ionising-photon fraction per unit luminosity from the full-range EUV
    SEDs: for each fetched node, Q/L = int_{<91.2nm}(F lam/hc) dlam / int F dlam.
    Returns sorted arrays (teff, q_over_l [photons/W]). Cached to
    data/derived/qtable.json — a pure function of the checksummed node set."""
    cache = Path(root) / "data" / "derived" / "qtable.json"
    man = json.loads((Path(root) / "data/raw/spectra_euv/nodes_manifest.json").read_text())
    if cache.exists():
        c = json.loads(cache.read_text())
        if c.get("n_nodes") == len(man):
            return np.array(c["teff"]), np.array(c["q_frac"])
    rows = []
    for v in man.values():
        wl, fx = [], []
        with gzip.open(Path(root) / v["file"], "rt") as f:
            for ln in f:
                if ln.startswith("#"):
                    continue
                a, b = ln.split()[:2]
                wl.append(float(a)); fx.append(float(b))
        wl = np.array(wl); fx = np.array(fx)
        o = np.argsort(wl); wl, fx = wl[o], fx[o]
        keep = np.concatenate([[True], np.diff(wl) > 0])
        wl, fx = wl[keep], fx[keep]
        total = np.trapezoid(fx, wl)
        m = wl < 911.8
        if m.sum() > 5 and total > 0:
            q = np.trapezoid(fx[m] * (wl[m] * 1e-10) / (H_PLANCK * C_MS), wl[m]) / total
        else:
            q = 0.0
        rows.append((v["teff"], q))
    rows.sort()
    t = np.array([r[0] for r in rows])
    q = np.array([r[1] for r in rows])
    # collapse duplicate teff (different logg) by mean — q(teff) is smooth
    ut = np.unique(t)
    uq = np.array([q[t == x].mean() for x in ut])
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"n_nodes": len(man), "teff": list(ut), "q_frac": list(uq)}))
    return ut, uq


class Nebula:
    def __init__(self, track, root):
        self.tr = track
        self.root = root
        i0 = track.anchors["post_agb"] - 1
        self.i0 = i0
        self.t0 = track.col("star_age")[i0]
        self.ages = track.col("star_age")[i0:] - self.t0
        self.teff = 10 ** track.col("log_Teff")[i0:]
        self.logl = track.col("log_L")[i0:]
        self.mass = track.col("star_mass")[i0:]
        self.logr = track.col("log_R")[i0:]
        self.mdot = track.col("star_mdot")[i0:]
        # superwind properties from the last TP-AGB phase
        j0, j1 = track.anchors["tp_agb_begin"] - 1, i0
        self.m_ejected = float(track.col("star_mass")[j0] - track.col("star_mass")[j1])
        m_end = track.col("star_mass")[j1] * M_SUN_KG
        r_end = 10 ** track.col("log_R")[j1] * R_SUN_M
        v_esc_agb = np.sqrt(2 * G_SI * m_end / r_end)
        self.v_slow = V_SLOW_FRACTION * v_esc_agb
        self.mdot_sw = abs(float(np.min(track.col("star_mdot")[j0:j1]))) * M_SUN_KG / YEAR_S
        # composition from the track's own surface
        x_h = track.col("surface_h1")[j1]
        self.n_o_over_h = (track.col("surface_o16")[j1] / 16.0) / x_h
        self.n_n_over_h = (track.col("surface_n14")[j1] / 14.0) / x_h
        self.x_h_mass = x_h
        self.q_teff, self.q_frac = q_ionising_table(root)

    def _interp(self, arr, t):
        return np.interp(t, self.ages, arr)

    def v_fast(self, t):
        m = self._interp(self.mass, t) * M_SUN_KG
        r = 10 ** self._interp(self.logr, t) * R_SUN_M
        return np.sqrt(2 * G_SI * m / r)

    def solve(self, t_end=None):
        """Shell mechanics only (4 smooth states); the ionisation balance is
        EQUILIBRIUM per output step (fork 5): the recombination time in the
        shell (~1e2-1e3 yr) is far below the evolutionary timescale (1e4 yr),
        so x follows Q quasi-statically — the front still rises with the
        core's photon output and recedes as it fades."""
        t_end = t_end or float(self.ages[-1])
        rho0_r2 = self.mdot_sw / (4 * np.pi * self.v_slow)  # rho(r) = rho0_r2/r^2

        t_sw = self.m_ejected * M_SUN_KG / self.mdot_sw / YEAR_S  # superwind duration, yr

        def rhs(t, y):
            r_s, v_s, m_s, e_b = y
            r_s = max(r_s, 1e9)
            m_s = max(m_s, 1e20)
            e_b = max(e_b, 0.0)
            rho = rho0_r2 / r_s ** 2
            sweep = 4 * np.pi * r_s ** 2 * rho * max(v_s - self.v_slow, 0.0)
            # the superwind is FINITE: gas launched over t_sw years occupies
            # [v_slow*t, v_slow*(t+t_sw)]; beyond its outer edge, or once the
            # whole ejecta is swept, there is nothing left to sweep
            r_outer = self.v_slow * (t + t_sw) * YEAR_S
            if r_s >= r_outer or m_s >= self.m_ejected * M_SUN_KG:
                sweep = 0.0
            p_b = e_b / (2 * np.pi * r_s ** 3)
            mdot_f = abs(self._interp(self.mdot, t)) * M_SUN_KG / YEAR_S
            vf = self.v_fast(t)
            dv = (4 * np.pi * r_s ** 2 * p_b + sweep * (self.v_slow - v_s)) / m_s
            de = 0.5 * mdot_f * vf ** 2 - p_b * 4 * np.pi * r_s ** 2 * v_s
            return [v_s * YEAR_S, dv * YEAR_S, sweep * YEAR_S, de * YEAR_S]

        t0 = 100.0
        y0 = [self.v_slow * t0 * YEAR_S, self.v_slow * 1.05,
              self.mdot_sw * t0 * YEAR_S, 0.0]
        t_eval = np.linspace(t0, t_end, 400)
        sol = solve_ivp(rhs, (t0, t_end), y0, method="LSODA",
                        t_eval=t_eval, rtol=1e-7,
                        atol=[1e6, 1e-3, 1e18, 1e25])
        # equilibrium ionised fraction per output step
        x_ion = np.zeros(len(sol.t))
        for k in range(len(sol.t)):
            r_s, v_s, m_s, e_b = sol.y[:, k]
            l_w = 10 ** self._interp(self.logl, sol.t[k]) * L_SUN_W
            qfrac = float(np.interp(self._interp(self.teff, sol.t[k]),
                                    self.q_teff, self.q_frac))
            q = qfrac * l_w
            n_h_tot = m_s * self.x_h_mass / M_H
            vol = 4 * np.pi * r_s ** 2 * (SHELL_THICKNESS * r_s)
            n_h = n_h_tot / vol
            # Q = alpha_B * (n_h x)^2 * vol  ->  x
            x = np.sqrt(q / max(ALPHA_B * n_h * n_h * vol, 1e-300))
            x_ion[k] = min(float(x), 1.0)
        sol.x_ion = x_ion
        return sol

    def emission(self, sol):
        """Per output step: line luminosities (W), chromaticity via the one
        CIE chain, shell state, mass closure."""
        from . import colour
        out = []
        for k in range(len(sol.t)):
            r_s, v_s, m_s, e_b = sol.y[:, k]
            t = sol.t[k]
            n_h_tot = m_s * self.x_h_mass / M_H
            x = float(sol.x_ion[k])
            vol = 4 * np.pi * r_s ** 2 * (SHELL_THICKNESS * r_s)
            n_h = n_h_tot / vol
            n_e = n_h * x
            v_ion = vol * x
            # H recombination lines (case B)
            nu_hb = C_MS / (LINES["hbeta"] * 1e-9)
            l_hb = ALPHA_HBETA * n_e * n_e * v_ion * H_PLANCK * nu_hb
            lines = {"hbeta": l_hb, "halpha": 2.86 * l_hb,
                     "hgamma": 0.468 * l_hb, "hdelta": 0.259 * l_hb}
            # [OIII], [NII]: two-level collisional excitation
            for sp, (omega, e_ul, main, sec, abund, frac) in {
                "oiii": (2.29, 2.48, "oiii5007", "oiii4959", self.n_o_over_h, 0.8),
                "nii": (2.64, 1.89, "nii6583", "nii6548", self.n_n_over_h, 0.2),
            }.items():
                n_ion_sp = abund * frac * n_h * x
                # q12 = 8.629e-6 Omega/(omega1 sqrt(T)) cm^3/s -> x1e-6 in m^3/s
                q_coll = 8.629e-12 / np.sqrt(T_E) * omega / 9.0 * np.exp(-e_ul * EV / (K_B * T_E))
                l_tot = n_e * n_ion_sp * v_ion * q_coll * e_ul * EV
                lines[main] = 0.75 * l_tot
                lines[sec] = 0.25 * l_tot
            # chromaticity: the line spectrum through the same chain
            wl = np.linspace(300.0, 900.0, 3001)
            spec = np.zeros_like(wl)
            for name, lam in LINES.items():
                spec += lines[name] * np.exp(-0.5 * ((wl - lam) / 1.0) ** 2)
            l_sum = sum(lines.values())
            if l_sum > 0 and spec.max() > 0:
                xyz = colour.spectrum_to_xyz(wl, spec)
                rgb, exc = colour.gamut_map(xyz)
                xy = colour.xyz_to_xy(xyz)
            else:
                rgb, exc, xy = [0.0, 0.0, 0.0], 0.0, [0.0, 0.0]
            out.append({
                "t_yr": float(t), "r_s_au": float(r_s / AU_M),
                "v_s_kms": float(v_s / 1e3), "m_shell_msun": float(m_s / M_SUN_KG),
                "x_ion": x, "l_lines_w": float(l_sum),
                "rgb_lin": [round(float(v), 6) for v in rgb],
                "excursion": round(float(exc), 6), "xy": [round(float(v), 6) for v in xy],
            })
        return out
