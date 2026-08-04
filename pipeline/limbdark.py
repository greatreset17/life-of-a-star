"""Limb darkening — fork 18. Two published sources, one law:

  I(mu)/I(1) = 1 - sum_k a_k (1 - mu^(k/2)),  k = 1..4   (Claret 2000 form)

  - GIANTS (logg < 3.0 and Teff <= 8000): Neilson & Lester 2013a spherical
    SATLAS fits (J/A+A/554/A98 table5, V), interpolated in (Teff, logg, M)
    with M from the track — spherical geometry carries the soft, drooping
    limb of the extended photosphere, exactly the physics fork 18 needs.
  - OTHERWISE (Teff <= 50000): Claret & Bloemen 2011 planar ATLAS fits
    (J/A+A/529/A75 tableeq5, V, Z=0, xi=2, Met=L — the F method is not
    published for this band/composition; the fit's flux-integral error is
    carried by suite test 11's tolerance).
  - Teff > 50000: fork-15 edge evaluation at the Claret boundary with
    recorded dTeff (the star is sub-pixel there at any framing the piece
    uses; the excursion is still recorded, never hidden).

The support edges (Neilson Teff floor 3000 K for the coolest pulse tips,
logg floor -1.0) are edge-evaluated with recorded deltas, same pattern.
A single fixed coefficient set anywhere, or a uniform disk, is failure
state 9; the seam at (logg 3.0 / Teff 8000) is measured by the suite.
"""
from pathlib import Path

import numpy as np

from . import sources

LAW_EXPONENTS = (0.5, 1.0, 1.5, 2.0)
GIANT_LOGG_MAX = 3.0
GIANT_TEFF_MAX = 8000.0
PLANAR_TEFF_MAX = 50000.0


def _load_tsv(name, ncols):
    p = sources.require(name)
    rows = []
    for ln in Path(p).read_text().splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        parts = [q.strip() for q in ln.split("\t")]
        try:
            rows.append([float(v) for v in parts[:ncols]])
        except ValueError:
            continue
    return np.array(rows)


class LimbDarkening:
    def __init__(self):
        # neilson: Teff logg M f1 f2 f3 f4
        self.sph = _load_tsv("limb_neilson2013", 7)
        # claret: logg Teff a1 a2 a3 a4  -> reorder to Teff logg a1..a4
        c = _load_tsv("limb_claret2011", 6)
        self.pp = np.column_stack([c[:, 1], c[:, 0], c[:, 2], c[:, 3], c[:, 4], c[:, 5]])

    @staticmethod
    def _interp_grid(table, teff, logg, extra=None):
        """Inverse-distance interpolation over the bracketing nodes of an
        irregular (Teff, logg[, M]) table; support edges clamp WITH the
        excursion returned, never silently."""
        cols = [table[:, 0], table[:, 1]] + ([table[:, 2]] if extra is not None else [])
        want = [teff, logg] + ([extra] if extra is not None else [])
        sel = np.ones(len(table), bool)
        exc = []
        for c, w in zip(cols, want):
            vals = np.unique(c[sel])
            lo = vals[vals <= w].max() if (vals <= w).any() else vals.min()
            hi = vals[vals >= w].min() if (vals >= w).any() else vals.max()
            exc.append(float(np.clip(w, lo, hi) - w))
            sel &= (np.isclose(c, lo) | np.isclose(c, hi))
        nodes = table[sel]
        w_clamped = [w + e for w, e in zip(want, exc)]
        scales = [max(1.0, abs(x)) for x in w_clamped]
        d = np.zeros(len(nodes))
        for j, (c, w, s) in enumerate(zip(range(len(want)), w_clamped, scales)):
            d += ((nodes[:, j] - w) / s) ** 2
        wgt = 1.0 / np.maximum(d, 1e-12)
        wgt /= wgt.sum()
        acol = nodes[:, -4:]
        a = (wgt[:, None] * acol).sum(axis=0)
        return a, max(abs(e) for e in exc)

    def coefficients(self, teff, logg, mass):
        """Returns (a1..a4 array, source name, support excursion)."""
        if logg < GIANT_LOGG_MAX and teff <= GIANT_TEFF_MAX:
            a, exc = self._interp_grid(self.sph, teff, logg, extra=mass)
            return a, "neilson2013-spherical", exc
        t_eval = min(teff, PLANAR_TEFF_MAX)
        a, exc = self._interp_grid(self.pp, t_eval, logg)
        return a, "claret2011-planar", max(exc, abs(teff - t_eval))

    @staticmethod
    def profile(a, mu):
        mu = np.asarray(mu, float)
        out = np.ones_like(mu)
        for ak, ek in zip(a, LAW_EXPONENTS):
            out = out - ak * (1.0 - mu ** ek)
        return out

    @staticmethod
    def flux_ratio(a):
        """2 * int_0^1 I(mu)/I(1) mu dmu — the disk-average factor Stage 1
        multiplies into the L-derived surface brightness (suite test 11)."""
        mu = np.linspace(0.0, 1.0, 4001)
        prof = LimbDarkening.profile(a, mu)
        return float(2.0 * np.trapezoid(prof * mu, mu))
