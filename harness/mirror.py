#!/usr/bin/env python3
"""Tier 1 — the physics mirror.

Independent implementations of the core numerical claims, runnable headless.
Where Stage 0 / Stage 1 compute a quantity, this module computes it a second
way and disagreement is the signal. This file deliberately shares NO code with
pipeline/ (shared inputs are correct — the CIE table is the same published
table — shared code would make agreement vacuous). Where the shipped Stage 1
JS can be executed directly under Node, prefer that to a reimplementation;
this mirror covers the numerics that cannot be run that way.

All arithmetic here is float64 (see fork 3 in pipeline/constants.py).

Subcommands:
  selftest                     known-answer tests of the mirror itself
  cie <spectrum.csv>           chromaticity + linear-sRGB direction of a spectrum
  arclength <track.csv> cx cy  arc length along two named columns
  orbit ...                    two-body integration under M(t) with attribution
  discriminate ...             numerical-vs-bookkeeping residual discrimination

Known-answer notes: the Planck function appears below ONLY as a harness test
vector (CIE Illuminant A, whose chromaticity is a published constant). It is
not part of any render or pipeline colour path; the failure state "a Planck
blackbody anywhere in the colour path" refers to the shipped colour chain,
which this file is not on.
"""
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CMF_PATH = ROOT / "data" / "raw" / "cie" / "ciexyz31.csv"

# IEC 61966-2-1 XYZ -> linear sRGB matrix (D65 primaries; applied to raw XYZ,
# no chromatic adaptation of the source — the star is never white-balanced).
XYZ_TO_SRGB = np.array([
    [3.2404542, -1.5371385, -0.4985314],
    [-0.9692660, 1.8760108, 0.0415560],
    [0.0556434, -0.2040259, 1.0572252],
])

G_SI = 6.67430e-11  # CODATA 2018


# ---------------------------------------------------------------- CIE chain
def load_cmf():
    rows = []
    with open(CMF_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            rows.append([float(p) for p in parts[:4]])
    arr = np.array(rows)
    return arr[:, 0], arr[:, 1:4]  # wavelengths [nm], (xbar, ybar, zbar)


def spectrum_to_xyz(wl_nm, flux):
    """Trapezoidal convolution of a spectrum with the CIE 1931 2-deg CMFs.

    Spectrum is interpolated onto the CMF wavelength grid; flux outside the
    spectrum's own support is treated as zero (the CMF support defines the
    visible band; a spectrum that does not cover it is the caller's error).
    """
    cw, cmf = load_cmf()
    f = np.interp(cw, wl_nm, flux, left=0.0, right=0.0)
    xyz = np.trapezoid(f[:, None] * cmf, cw, axis=0)
    return xyz


def xyz_to_chromaticity(xyz):
    s = xyz.sum()
    return (float(xyz[0] / s), float(xyz[1] / s))


def xyz_to_linear_srgb_dir(xyz):
    """Linear sRGB direction, normalised so Y=1. No per-channel clamping here:
    out-of-gamut values are reported as they are (gamut mapping is a separate,
    declared step — fork 1)."""
    rgb = XYZ_TO_SRGB @ (xyz / xyz[1])
    return [float(v) for v in rgb]


def planck_spd(wl_nm, t_k):
    # Harness test vector ONLY (Illuminant A); see module docstring.
    wl = wl_nm * 1e-9
    c1, c2 = 3.741771e-16, 1.4388e-2
    return c1 / (wl ** 5) / (np.exp(c2 / (wl * t_k)) - 1.0)


# ---------------------------------------------------------------- arc length
def arc_length(x, y):
    dx, dy = np.diff(np.asarray(x, float)), np.diff(np.asarray(y, float))
    seg = np.hypot(dx, dy)
    return float(seg.sum()), seg


# ---------------------------------------------------------------- orbit
class OrbitMirror:
    """Two-body orbit under time-varying stellar mass, with per-substep
    attribution of every effect that acts on the orbital energy.

    Integrator: RK4 with fixed substeps per orbit (order 4). It is NOT
    symplectic and is not called symplectic (fork 7): conservation is held by
    step control and monitored, not guaranteed by construction.

    Attribution ledger: specific orbital energy eps = v^2/2 - GM/r changes
    only through (a) the explicit time-dependence of the potential,
    d eps/dt |_massloss = -(dM/dt) G / r, and (b) the power of any
    non-gravitational force, F_drag . v. Both are integrated alongside the
    state. The unattributed residual  d_eps_total - sum(attributed)  is the
    monitored quantity; physics lives in the ledger, numerics in the residual.
    """

    def __init__(self, m0_kg, mdot_fn=None, drag_fn=None):
        self.m0 = m0_kg
        self.mdot_fn = mdot_fn or (lambda t: 0.0)
        self.drag_fn = drag_fn  # drag_fn(t, r_vec, v_vec) -> accel vec, or None

    def mass(self, t):
        # M(t) = m0 + integral(mdot); caller supplies mdot consistent with this
        # via precomputed cumulative mass in mdot_fn closures when needed.
        raise NotImplementedError

    def integrate(self, r0, v0, t0, t1, mass_fn, nsteps, ledger_massloss=True):
        """mass_fn(t) -> (M, dMdt). Returns final state + attribution ledger."""
        r = np.array(r0, float)
        v = np.array(v0, float)
        t = t0
        dt = (t1 - t0) / nsteps
        att_massloss = 0.0
        att_drag = 0.0
        M, _ = mass_fn(t0)
        eps0 = 0.5 * v @ v - G_SI * M / np.linalg.norm(r)

        def acc(t, r, v):
            M, _ = mass_fn(t)
            a = -G_SI * M * r / np.linalg.norm(r) ** 3
            if self.drag_fn is not None:
                a = a + self.drag_fn(t, r, v)
            return a

        for _ in range(nsteps):
            # RK4 on (r, v)
            k1r, k1v = v, acc(t, r, v)
            k2r, k2v = v + 0.5 * dt * k1v, acc(t + 0.5 * dt, r + 0.5 * dt * k1r, v + 0.5 * dt * k1v)
            k3r, k3v = v + 0.5 * dt * k2v, acc(t + 0.5 * dt, r + 0.5 * dt * k2r, v + 0.5 * dt * k2v)
            k4r, k4v = v + dt * k3v, acc(t + dt, r + dt * k3r, v + dt * k3v)
            r_new = r + dt / 6.0 * (k1r + 2 * k2r + 2 * k3r + k4r)
            v_new = v + dt / 6.0 * (k1v + 2 * k2v + 2 * k3v + k4v)
            # attribution over the substep (midpoint quadrature)
            tm = t + 0.5 * dt
            rm = 0.5 * (r + r_new)
            vm = 0.5 * (v + v_new)
            Mm, dMdtm = mass_fn(tm)
            if ledger_massloss:
                att_massloss += (-dMdtm * G_SI / np.linalg.norm(rm)) * dt
            if self.drag_fn is not None:
                att_drag += float(self.drag_fn(tm, rm, vm) @ vm) * dt
            r, v, t = r_new, v_new, t + dt

        M1, _ = mass_fn(t1)
        eps1 = 0.5 * v @ v - G_SI * M1 / np.linalg.norm(r)
        a1 = -G_SI * M1 / (2 * eps1)
        ledger = {
            "d_eps_total": eps1 - eps0,
            "att_massloss": att_massloss,
            "att_drag": att_drag,
            "residual": (eps1 - eps0) - att_massloss - att_drag,
            "eps0": eps0, "eps1": eps1,
        }
        return r, v, a1, M1, ledger


def discriminate_residual(run_fn, nsteps, order=4, ratio_tol=2.5):
    """Mechanical numerical-vs-bookkeeping discrimination.

    run_fn(nsteps) -> unattributed residual. A numerical residual scales as
    dt^order: halving dt divides it by ~2^order. A bookkeeping/physics residual
    (an effect acting but missing from the ledger) is dt-independent. The
    discrimination is the measured scaling exponent, no human opinion involved.
    """
    r1 = abs(run_fn(nsteps))
    r2 = abs(run_fn(nsteps * 2))
    if r1 == 0.0 and r2 == 0.0:
        return {"verdict": "numerical", "r1": r1, "r2": r2, "measured_order": float("inf")}
    if r2 == 0.0:
        return {"verdict": "numerical", "r1": r1, "r2": r2, "measured_order": float("inf")}
    p = math.log2(r1 / r2) if r1 > 0 else 0.0
    verdict = "numerical" if p > order - ratio_tol else "bookkeeping-or-physics"
    return {"verdict": verdict, "r1": r1, "r2": r2, "measured_order": p}


# ---------------------------------------------------------------- self-tests
def selftest():
    failures = []

    def check(name, ok, detail=""):
        print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  [{detail}]"))
        if not ok:
            failures.append(name)

    cw, cmf = load_cmf()
    check("cmf-loaded-95-rows", cw.shape[0] == 95 and cw[0] == 360.0 and cw[-1] == 830.0,
          f"rows={cw.shape[0]} first={cw[0]} last={cw[-1]}")

    # equal-energy spectrum -> illuminant E chromaticity (1/3, 1/3)
    wl = np.linspace(300.0, 900.0, 1201)
    x, y = xyz_to_chromaticity(spectrum_to_xyz(wl, np.ones_like(wl)))
    check("cie-equal-energy-E", abs(x - 1 / 3) < 2e-3 and abs(y - 1 / 3) < 2e-3, f"xy=({x:.5f},{y:.5f})")

    # Illuminant A (Planck 2856 K test vector) -> published (0.44758, 0.40745)
    x, y = xyz_to_chromaticity(spectrum_to_xyz(wl, planck_spd(wl, 2856.0)))
    check("cie-illuminant-A", abs(x - 0.44758) < 2e-3 and abs(y - 0.40745) < 2e-3, f"xy=({x:.5f},{y:.5f})")

    # narrow line at a CMF node reproduces the locus chromaticity of that node
    i = int(np.where(cw == 555.0)[0][0])
    locus = cmf[i] / cmf[i].sum()
    line = np.exp(-0.5 * ((wl - 555.0) / 0.8) ** 2)
    x, y = xyz_to_chromaticity(spectrum_to_xyz(wl, line))
    check("cie-locus-555", abs(x - locus[0]) < 2e-3 and abs(y - locus[1]) < 2e-3,
          f"xy=({x:.5f},{y:.5f}) vs ({locus[0]:.5f},{locus[1]:.5f})")

    # sRGB matrix: D65 white point -> (1,1,1)
    rgb = XYZ_TO_SRGB @ np.array([0.95047, 1.0, 1.08883])
    check("srgb-d65-white", np.allclose(rgb, 1.0, atol=2e-3), f"rgb={rgb}")

    # arc length: unit circle -> 2*pi
    th = np.linspace(0, 2 * np.pi, 20001)
    total, _ = arc_length(np.cos(th), np.sin(th))
    check("arclength-circle", abs(total - 2 * np.pi) < 1e-6, f"L={total}")

    # orbit: pure Kepler, 100 orbits, energy conserved by step control
    AU, MSUN, YR = 1.495978707e11, 1.98892e30, 3.15576e7
    om = OrbitMirror(MSUN)
    vc = math.sqrt(G_SI * MSUN / AU)
    mass_const = lambda t: (MSUN, 0.0)
    _, _, a1, _, led = om.integrate([AU, 0, 0], [0, vc, 0], 0.0, 100 * YR, mass_const, nsteps=100 * 400)
    check("orbit-kepler-energy", abs(led["d_eps_total"] / led["eps0"]) < 1e-6,
          f"rel-drift={led['d_eps_total'] / led['eps0']:.3e}")
    check("orbit-kepler-a", abs(a1 / AU - 1.0) < 1e-6, f"a={a1 / AU}")

    # orbit: slow mass loss, adiabatic invariant a*M conserved; ledger closes
    tau = 1e5 * YR  # M falls ~1% over 1000 yr of integration: slow vs orbit
    mass_lin = lambda t: (MSUN * (1 - t / tau), -MSUN / tau)
    _, _, a1, M1, led = om.integrate([AU, 0, 0], [0, vc, 0], 0.0, 1000 * YR, mass_lin, nsteps=1000 * 400)
    aM = a1 * M1 / (AU * MSUN)
    check("orbit-massloss-aM-invariant", abs(aM - 1.0) < 1e-4, f"aM/aM0={aM:.8f}")
    check("orbit-massloss-ledger-closure",
          abs(led["residual"]) < 1e-6 * abs(led["eps0"]),
          f"residual={led['residual']:.3e} eps0={led['eps0']:.3e}")

    # discrimination: a deliberately broken ledger is identified as bookkeeping,
    # an intact ledger's residual is identified as numerical
    def run(nsteps, broken):
        _, _, _, _, led = om.integrate([AU, 0, 0], [0, vc, 0], 0.0, 200 * YR, mass_lin,
                                       nsteps=nsteps, ledger_massloss=not broken)
        return led["residual"]

    d_ok = discriminate_residual(lambda n: run(n, broken=False), nsteps=200 * 200)
    d_bad = discriminate_residual(lambda n: run(n, broken=True), nsteps=200 * 200)
    check("discriminate-intact-is-numerical", d_ok["verdict"] == "numerical", json.dumps(d_ok))
    check("discriminate-broken-is-bookkeeping", d_bad["verdict"] == "bookkeeping-or-physics", json.dumps(d_bad))

    print(f"\nmirror selftest: {'ALL GREEN' if not failures else f'{len(failures)} FAILURE(S)'}")
    return 0 if not failures else 1


# ---------------------------------------------------------------- CLI
def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == "selftest":
        return selftest()
    if cmd == "cie":
        wl, fl = [], []
        with open(args[0]) as f:
            for row in csv.reader(f):
                if row and not row[0].lstrip().startswith("#"):
                    wl.append(float(row[0])); fl.append(float(row[1]))
        xyz = spectrum_to_xyz(np.array(wl), np.array(fl))
        out = {"xy": xyz_to_chromaticity(xyz), "linear_srgb_dir": xyz_to_linear_srgb_dir(xyz)}
        print(json.dumps(out, indent=2))
        return 0
    if cmd == "arclength":
        path, cx, cy = args[0], args[1], args[2]
        with open(path) as f:
            r = csv.DictReader(f)
            xs, ys = zip(*[(float(row[cx]), float(row[cy])) for row in r])
        total, _ = arc_length(xs, ys)
        print(json.dumps({"arc_length": total, "n": len(xs)}))
        return 0
    print(f"unknown subcommand: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
