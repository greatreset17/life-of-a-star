"""The colour chain — the ONLY path from a spectrum to a chromaticity,
anywhere in this project. The star's photosphere, the nebula's line emission
and every background star pass through these same functions; that single
ownership is the structural guarantee behind "derived, never chosen"
(fork 1, suite tests 13/17/27). No white balancing is applied anywhere:
the XYZ->sRGB matrix is fixed, the source is never adapted to a white point.

Quadrature note: this module integrates on a 1 nm resampled grid (rectangle
rule); the harness mirror integrates by trapezoid on the native 5 nm CMF
grid. The two implementations agreeing to ~1e-3 in (x, y) is a meaningful
cross-check precisely because the quadratures differ.
"""
import gzip
from pathlib import Path

import numpy as np

from . import sources

# IEC 61966-2-1 XYZ -> linear sRGB (D65 primaries). Applied to raw XYZ.
XYZ_TO_SRGB = np.array([
    [3.2404542, -1.5371385, -0.4985314],
    [-0.9692660, 1.8760108, 0.0415560],
    [0.0556434, -0.2040259, 1.0572252],
])

# Oklab (Ottosson 2020) — algorithm constants for the fork-1 gamut mapping,
# not colours: the mapping holds Oklab hue and lightness, compresses chroma.
_OK_M1 = np.array([
    [0.4122214708, 0.5363325363, 0.0514459929],
    [0.2119034982, 0.6806995451, 0.1073969566],
    [0.0883024619, 0.2817188376, 0.6299787005],
])
_OK_M2 = np.array([
    [0.2104542553, 0.7936177850, -0.0040720468],
    [1.9779984951, -2.4285922050, 0.4505937099],
    [0.0259040371, 0.7827717662, -0.8086757660],
])

_cmf_cache = None


def cmf_1nm():
    """CIE 1931 2-deg CMFs resampled to a 1 nm grid (fork 13 source)."""
    global _cmf_cache
    if _cmf_cache is None:
        path = sources.require("cie_cmf")
        rows = np.array([[float(v) for v in ln.split(",")[:4]]
                         for ln in Path(path).read_text().splitlines() if ln.strip()])
        wl = np.arange(rows[0, 0], rows[-1, 0] + 0.5, 1.0)
        cmf = np.stack([np.interp(wl, rows[:, 0], rows[:, 1 + i]) for i in range(3)], axis=1)
        _cmf_cache = (wl, cmf)
    return _cmf_cache


def spectrum_to_xyz(wl_nm, flux):
    """Rectangle-rule convolution with the CMFs on the 1 nm grid. The
    spectrum must cover the CMF support; missing coverage raises rather than
    zero-fills (no-fallback)."""
    wl, cmf = cmf_1nm()
    if wl_nm[0] > wl[0] or wl_nm[-1] < wl[-1]:
        raise ValueError(
            f"spectrum support [{wl_nm[0]:.0f},{wl_nm[-1]:.0f}] nm does not cover "
            f"CMF band [{wl[0]:.0f},{wl[-1]:.0f}] nm — refusing to zero-fill")
    f = np.interp(wl, wl_nm, flux)
    return (f[:, None] * cmf).sum(axis=0)


def xyz_to_xy(xyz):
    s = float(xyz.sum())
    return (float(xyz[0] / s), float(xyz[1] / s))


def _srgb_dir(xyz):
    rgb = XYZ_TO_SRGB @ (np.asarray(xyz, float) / xyz[1])
    return rgb / rgb.max()


def gamut_map(xyz):
    """fork 1: perceptual gamut mapping. Returns (rgb_lin_dir in [0,1],
    excursion) where excursion is the Oklab chroma removed (0 if in gamut).
    Hue and lightness are held; chroma alone is compressed toward the
    achromatic axis until the colour enters the sRGB gamut. Never a
    per-channel clip."""
    rgb = _srgb_dir(xyz)
    if rgb.min() >= 0.0:
        return rgb, 0.0
    # out of gamut: compress chroma at constant Oklab L, h
    lab_true = _oklab_extrapolated(rgb)
    L, a, b = lab_true
    C_true = float(np.hypot(a, b))
    lo, hi = 0.0, 1.0
    for _ in range(48):
        t = 0.5 * (lo + hi)
        rgb_t = _oklab_inverse(np.array([L, a * t, b * t]))
        if rgb_t.min() >= -1e-9 and rgb_t.max() <= 1.0 + 1e-9:
            lo = t
        else:
            hi = t
    rgb_m = np.clip(_oklab_inverse(np.array([L, a * lo, b * lo])), 0.0, 1.0)
    rgb_m = rgb_m / rgb_m.max()
    return rgb_m, C_true * (1.0 - lo)


def _oklab_extrapolated(rgb_lin):
    """Oklab of a possibly out-of-gamut linear sRGB triple: the cube root is
    taken with sign so negative channels keep meaning (Ottosson's own
    extension for gamut mapping)."""
    lms = _OK_M1 @ rgb_lin
    return _OK_M2 @ (np.sign(lms) * np.abs(lms) ** (1.0 / 3.0))


def _oklab_inverse(lab):
    lms13 = np.linalg.solve(_OK_M2, lab)
    return np.linalg.solve(_OK_M1, lms13 ** 3)


# ------------------------------------------------------------ node spectra
_node_cache = {}


def load_node(root, grid, teff, logg):
    key = (grid, round(teff, 1), round(logg, 2))
    if key not in _node_cache:
        p = Path(root) / "data" / "raw" / "spectra" / grid / f"t{teff:07.1f}_g{logg:+.2f}.txt.gz"
        if not p.exists():
            raise sources.SourceUnavailable(
                f"spectrum:{grid}/t{teff:.0f}g{logg:+.2f}", "node file absent")
        wl, fx = [], []
        with gzip.open(p, "rt") as f:
            for ln in f:
                if ln.startswith("#"):
                    continue
                a, b = ln.split()[:2]
                wl.append(float(a)); fx.append(float(b))
        wl = np.asarray(wl) / 10.0  # Angstrom -> nm
        fx = np.asarray(fx)
        o = np.argsort(wl)
        wl, fx = wl[o], fx[o]
        # collapse duplicate wavelengths (some grids repeat band edges)
        keep = np.concatenate([[True], np.diff(wl) > 0])
        _node_cache[key] = (wl[keep], fx[keep])
    return _node_cache[key]


def interp_spectrum(root, grid, cell, teff, logg):
    """Bilinear interpolation of log-flux over the (teff, logg) cell on a
    common 1 nm grid. cell is the list of available [teff, logg] corners
    (2, 3 or 4 of them; fewer than 4 happens at fork-15/16 support edges,
    where the available corners at the clamped coordinate are used)."""
    wl, _ = cmf_1nm()
    teffs = sorted({c[0] for c in cell})
    loggs_at = {tv: sorted({c[1] for c in cell if c[0] == tv}) for tv in teffs}

    def logf_at(tv, gv):
        w, f = load_node(root, grid, tv, gv)
        fi = np.interp(wl, w, f)
        return np.log10(np.maximum(fi, 1e-300))

    def logf_teff(tv):
        gs = loggs_at[tv]
        if len(gs) == 1:
            return logf_at(tv, gs[0])
        g0, g1 = gs[0], gs[-1]
        u = np.clip((logg - g0) / (g1 - g0), 0.0, 1.0)
        return (1 - u) * logf_at(tv, g0) + u * logf_at(tv, g1)

    if len(teffs) == 1:
        lf = logf_teff(teffs[0])
    else:
        t0, t1 = teffs[0], teffs[-1]
        v = np.clip((np.log10(teff) - np.log10(t0)) / (np.log10(t1) - np.log10(t0)), 0.0, 1.0)
        lf = (1 - v) * logf_teff(t0) + v * logf_teff(t1)
    return wl, 10.0 ** lf
