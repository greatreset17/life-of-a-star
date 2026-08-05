"""Chromaticity for the cooling tail — fork 23.

  Teff > 5000 K  : Koester (2010) DA model spectra through the SAME chain
                   (colour.spectrum_to_xyz / gamut_map), bilinear in
                   (Teff, logg) over the fetched node set.
  1500..5000 K   : no public cool-DA spectra exist; the Montreal photometry
                   tables (Bedard et al. 2020, incl. Blouin CIA physics)
                   tabulate SDSS ugriz AB magnitudes to 1500 K. A coarse SED
                   is reconstructed from the five AB band fluxes at their
                   published effective wavelengths and passed through the
                   IDENTICAL CIE chain — a spectrum sampled coarsely is
                   still a spectrum; nothing is white-balanced, nothing is
                   Planck. Mass-interpolated between the 0.5 and 0.6 tables.
  < 1500 K       : below the photometry tables (region B territory): the
                   chromaticity is evaluated at the 1500 K table edge with
                   the Teff excursion recorded — the fade to black is
                   luminance-driven and labelled extrapolated.

The 5000 K seam between the two pathways is measured by the suite.
"""
from pathlib import Path

import numpy as np

from . import colour, sources

# SDSS effective wavelengths, Angstrom (Doi et al. 2010) — published constants
SDSS_LEFF = {"u": 3557.0, "g": 4702.0, "r": 6175.0, "i": 7491.0, "z": 8946.0}
AB_ZERO_FNU = 3.631e-23  # W m^-2 Hz^-1 (3631 Jy)
C_MS = 2.99792458e8
KOESTER_FLOOR_K = 5000.0
MONTREAL_FLOOR_K = 1500.0


def load_montreal_tables():
    rows = {}
    for name, mass in (("montreal_table_05", 0.5), ("montreal_table_06", 0.6)):
        p = sources.require(name)
        lines = Path(p).read_text().splitlines()
        head = next(i for i, ln in enumerate(lines) if ln.strip().startswith("Teff"))
        cols = lines[head].split()
        # SDSS ugriz: the FIRST u g r i z run after the WISE/Spitzer block
        iu = cols.index("u")
        data = []
        for ln in lines[head + 1:]:
            parts = ln.split()
            if len(parts) < iu + 5:
                continue
            try:
                teff = float(parts[0])
            except ValueError:
                continue
            mags = [float(parts[iu + k]) for k in range(5)]
            data.append([teff] + mags)
        rows[mass] = np.array(data)
    return rows


class CoolingColour:
    def __init__(self, root):
        self.root = root
        self.mont = load_montreal_tables()
        import json
        nm = json.loads((Path(root) / "data" / "raw" / "spectra" / "nodes_manifest.json").read_text())
        self.koester_nodes = sorted(
            [(v["teff"], v["logg"]) for v in nm.values() if v["grid"] == "koester2"])

    def _koester_xyz(self, teff, logg):
        teffs = sorted({t for t, _ in self.koester_nodes})
        t_lo = max([t for t in teffs if t <= teff], default=teffs[0])
        t_hi = min([t for t in teffs if t >= teff], default=teffs[-1])
        cell = []
        for tv in {t_lo, t_hi}:
            gs = sorted({g for t, g in self.koester_nodes if t == tv})
            g_lo = max([g for g in gs if g <= logg], default=gs[0])
            g_hi = min([g for g in gs if g >= logg], default=gs[-1])
            cell += [[tv, g_lo], [tv, g_hi]]
        wl, flux = colour.interp_spectrum(self.root, "koester2",
                                          [list(c) for c in {tuple(c) for c in cell}],
                                          teff, logg)
        return colour.spectrum_to_xyz(wl, flux)

    def _montreal_xyz(self, teff, mass):
        t_eval = max(teff, MONTREAL_FLOOR_K)
        w = np.clip((mass - 0.5) / 0.1, 0.0, 1.0)
        mags = []
        for m_tab, tab in ((0.5, self.mont[0.5]), (0.6, self.mont[0.6])):
            o = np.argsort(tab[:, 0])
            mags.append([np.interp(t_eval, tab[o, 0], tab[o, 1 + k]) for k in range(5)])
        mags = (1 - w) * np.array(mags[0]) + w * np.array(mags[1])
        # AB magnitude -> F_nu -> F_lambda at the band effective wavelengths
        leff = np.array([SDSS_LEFF[b] for b in "ugriz"])  # Angstrom
        fnu = AB_ZERO_FNU * 10 ** (-0.4 * mags)
        flam = fnu * C_MS / (leff * 1e-10) ** 2  # per metre; scale-free chain
        # coarse SED on nm axis
        return colour.spectrum_to_xyz(leff / 10.0, flam), abs(teff - t_eval)

    # fork 35 — visible fraction of the emission, per pathway:
    #   koester : Y / integral(F dlambda) over the model spectrum (the same
    #             ratio the main-track table uses)
    #   montreal: the ABSOLUTE route — the tables give absolute AB mags, so
    #             the V-weighted luminosity is known outright; the bolometric
    #             is 4 pi R^2 sigma T^4 with R from the row's own (M, log g)
    #             — the panel's own displayed law, no Planck SED anywhere.
    #             The two definitions are cross-calibrated at the measured
    #             5000 K seam (one declared factor, like every other seam).
    #   < 1500 K: both integrals ride t_eval at the table edge, so the
    #             fraction is edge-held exactly like the chromaticity.
    _G_SI = 6.674e-11
    _SIGMA_SB = 5.670374419e-8
    _PC10_M = 10 * 3.0856775814913673e16
    _MSUN_KG = 1.98892e30

    def _koester_fvis(self, teff, logg):
        teffs = sorted({t for t, _ in self.koester_nodes})
        t_lo = max([t for t in teffs if t <= teff], default=teffs[0])
        t_hi = min([t for t in teffs if t >= teff], default=teffs[-1])
        cell = []
        for tv in {t_lo, t_hi}:
            gs = sorted({g for t, g in self.koester_nodes if t == tv})
            g_lo = max([g for g in gs if g <= logg], default=gs[0])
            g_hi = min([g for g in gs if g >= logg], default=gs[-1])
            cell += [[tv, g_lo], [tv, g_hi]]
        wl, flux = colour.interp_spectrum(self.root, "koester2",
                                          [list(c) for c in {tuple(c) for c in cell}],
                                          teff, logg)
        return float(colour.spectrum_to_xyz(wl, flux)[1]
                     / max(np.trapezoid(flux, wl), 1e-300))

    def _montreal_fvis_raw(self, teff, mass, logg):
        (xyz, _) = self._montreal_xyz(teff, mass)
        t_eval = max(teff, MONTREAL_FLOOR_K)
        r_m = np.sqrt(self._G_SI * mass * self._MSUN_KG / (10.0 ** logg * 1e-2))
        l_bol = 4 * np.pi * r_m ** 2 * self._SIGMA_SB * t_eval ** 4
        return float(xyz[1] * 4 * np.pi * self._PC10_M ** 2 / max(l_bol, 1e-300))

    def _seam_factor(self):
        if not hasattr(self, "_seam_k"):
            fk = self._koester_fvis(KOESTER_FLOOR_K, 8.0)
            fm = self._montreal_fvis_raw(KOESTER_FLOOR_K, 0.5398, 8.0)
            self._seam_k = fk / max(fm, 1e-300)
        return self._seam_k

    def row(self, teff, logg, mass):
        """Returns (rgb_lin, xy, excursion_gamut, source, teff_excursion, f_vis)."""
        if teff > KOESTER_FLOOR_K:
            xyz = self._koester_xyz(teff, logg)
            t_exc = 0.0
            src = "koester2-spectrum"
            f_vis = self._koester_fvis(teff, logg)
        else:
            xyz, t_exc = self._montreal_xyz(teff, mass)
            src = "montreal-ugriz-sed"
            f_vis = self._montreal_fvis_raw(teff, mass, logg) * self._seam_factor()
        rgb, exc = colour.gamut_map(xyz)
        return ([float(v) for v in rgb], list(colour.xyz_to_xy(xyz)),
                float(exc), src, float(t_exc), float(f_vis))
