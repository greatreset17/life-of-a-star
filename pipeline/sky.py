"""The sky — real stars, real positions, real colours (fork 26).

Catalogue: Gaia DR3 to G < 6.5, supplemented at the bright end by Hipparcos
(V < 3.6) where Gaia saturates — both published catalogues, deduplicated by
position. Chromaticity: each star's G/BP/RP (or Johnson B/V) fluxes form a
coarse SED at the SVO-published pivot wavelengths, fed through the IDENTICAL
CIE chain as the Sun (fork 23's precedent; test 27 checks the reuse
structurally). Scotopic luminance factors come from the same SEDs against
the CIE 1951 V'(lambda) table (the Purkinje shift is data, not taste).

Positions: parallax -> 3D; the sky is a volume, never a sphere. Stars with
non-positive or missing parallax are EXCLUDED and counted in the meta (an
absence is information; a substituted distance would be a fallback).

Orbits: linear space motion is only valid to ~1e5-1e6 yr; beyond, orbits are
integrated in a Bovy (2015) MWPotential2014-class potential — Miyamoto-Nagai
disk + Hernquist bulge + NFW halo, the halo amplitude solved so that
v_c(R0) = 220 km/s (published structure, one derived normalisation).
Leapfrog, vectorised over all stars; energy and L_z are suite invariants.
Existence and luminosity are FROZEN at the present epoch (declared boundary:
no population synthesis; test 32 enforces it structurally).
"""
import csv
from pathlib import Path

import numpy as np

from . import colour, sources
from .constants import G_SI, M_SUN_KG

PC_M = 3.0856775814913673e16
KM_S_TO_PC_MYR = 1.0227121650537077  # km/s in pc/Myr
K_PM = 4.740470463533348             # (mas/yr)*(kpc) -> km/s

# SVO Filter Profile Service pivots (Angstrom) and Vega zero points (Jy)
BANDS = {
    "G": (6217.59, 3228.75), "BP": (5109.71, 3552.01), "RP": (7769.02, 2554.95),
    "B": (4368.39, 4015.68), "V": (5486.31, 3620.46),
}

# ICRS -> galactic rotation (IAU/Hipparcos standard matrix)
A_G = np.array([
    [-0.0548755604162154, -0.8734370902348850, -0.4838350155487132],
    [+0.4941094278755837, -0.4448296299600112, +0.7469822444972189],
    [-0.8676661490190047, -0.1980763734312015, +0.4559837761750669],
])

R0_PC = 8000.0
Z_SUN_PC = 20.8
V_SUN = np.array([11.1, 232.24, 7.25])  # km/s, U toward GC, V rotation, W north

# potential (fork 27): masses in Msun, lengths in pc
MN_M, MN_A, MN_B = 6.8e10, 3000.0, 280.0
HQ_M, HQ_A = 5.0e9, 600.0
NFW_RS = 16000.0
_G_PC = G_SI * M_SUN_KG / PC_M / 1e6  # G in pc (km/s)^2 / Msun


def _vc2_disk_bulge(r_pc):
    z = 0.0
    s = np.sqrt(r_pc ** 2 + (MN_A + np.sqrt(z ** 2 + MN_B ** 2)) ** 2)
    vc2_d = _G_PC * MN_M * r_pc ** 2 / s ** 3
    vc2_b = _G_PC * HQ_M * r_pc / (r_pc + HQ_A) ** 2
    return vc2_d + vc2_b


def nfw_amplitude():
    """Solve the halo mass scale so v_c(R0) = 220 km/s exactly."""
    need = 220.0 ** 2 - _vc2_disk_bulge(R0_PC)
    x = R0_PC / NFW_RS
    mfrac = np.log(1 + x) - x / (1 + x)
    return need * R0_PC / (_G_PC * mfrac)  # M_s such that M(r)=M_s*mfrac(r)


NFW_MS = nfw_amplitude()


def accel(pos_pc):
    """Acceleration (km/s per Myr) for positions (N,3) in pc, vectorised."""
    x, y, z = pos_pc[:, 0], pos_pc[:, 1], pos_pc[:, 2]
    r2 = x * x + y * y
    r = np.sqrt(r2 + z * z) + 1e-3
    rho = np.sqrt(r2) + 1e-3
    # Miyamoto-Nagai
    zb = np.sqrt(z * z + MN_B ** 2)
    denom = (r2 + (MN_A + zb) ** 2) ** 1.5
    ax = -_G_PC * MN_M * x / denom
    ay = -_G_PC * MN_M * y / denom
    az = -_G_PC * MN_M * z * (MN_A + zb) / (zb * denom)
    # Hernquist bulge
    hq = -_G_PC * HQ_M / (r * (r + HQ_A) ** 2)
    ax += hq * x; ay += hq * y; az += hq * z
    # NFW
    xh = r / NFW_RS
    mfrac = np.log(1 + xh) - xh / (1 + xh)
    nf = -_G_PC * NFW_MS * mfrac / r ** 3
    ax += nf * x; ay += nf * y; az += nf * z
    # (km/s)^2/pc -> km/s per Myr: multiply by 1/(pc per km/s/Myr)
    return np.stack([ax, ay, az], axis=1) * KM_S_TO_PC_MYR


def load_catalog(root):
    """Assemble the star list: position (pc, galactocentric), velocity
    (km/s galactocentric), band fluxes, with exclusion accounting."""
    rows, excluded = [], {"no_parallax": 0, "no_bands": 0}
    with open(Path(root) / "data/raw/gaia/naked_eye.csv") as f:
        for r in csv.DictReader(f):
            try:
                plx = float(r["parallax"])
            except ValueError:
                excluded["no_parallax"] += 1
                continue
            if plx <= 0.05:
                excluded["no_parallax"] += 1
                continue
            try:
                fg = float(r["phot_g_mean_flux"])
                fbp = float(r["phot_bp_mean_flux"])
                frp = float(r["phot_rp_mean_flux"])
            except ValueError:
                excluded["no_bands"] += 1
                continue
            rv = r["radial_velocity"]
            rows.append({
                "ra": float(r["ra"]), "dec": float(r["dec"]), "plx": plx,
                "pmra": float(r["pmra"] or 0), "pmdec": float(r["pmdec"] or 0),
                "rv": float(rv) if rv not in ("", "null") else None,
                "gmag": float(r["phot_g_mean_mag"]),
                "sed": {"G": fg, "BP": fbp, "RP": frp}, "src": "gaia",
            })
    # Hipparcos bright supplement, deduplicated against Gaia by position
    gaia_bright = np.array([[r["ra"], r["dec"]] for r in rows if r["gmag"] < 4.5])
    with open(Path(root) / "data/raw/gaia/hipparcos_bright.tsv") as f:
        for ln in f:
            if ln.startswith("#") or not ln.strip():
                continue
            p = [q.strip() for q in ln.split("\t")]
            if len(p) < 8:
                continue
            try:
                ra, dec, plx = float(p[1]), float(p[2]), float(p[3])
                vmag, bv = float(p[6]), float(p[7])
            except ValueError:
                continue
            if plx <= 0.05:
                excluded["no_parallax"] += 1
                continue
            if len(gaia_bright) and np.min(
                    (gaia_bright[:, 0] - ra) ** 2 * np.cos(np.radians(dec)) ** 2
                    + (gaia_bright[:, 1] - dec) ** 2) < (2 / 60) ** 2:
                continue  # already in Gaia
            # Johnson B, V fluxes from V and B-V via the SVO zero points
            fv = BANDS["V"][1] * 10 ** (-0.4 * vmag)
            fb = BANDS["B"][1] * 10 ** (-0.4 * (vmag + bv))
            rows.append({
                "ra": ra, "dec": dec, "plx": plx,
                "pmra": float(p[4] or 0), "pmdec": float(p[5] or 0), "rv": None,
                "gmag": vmag, "sed": {"B": fb, "V": fv}, "src": "hip",
            })
    return rows, excluded


def star_chromaticity(sed):
    """Coarse SED (band fluxes) -> chromaticity + scotopic factor, through
    the one chain. Fluxes are converted Jy-relative -> F_lambda ~ F_nu/l^2."""
    wl_nm, flam = [], []
    for band, flux in sorted(sed.items(), key=lambda kv: BANDS[kv[0]][0]):
        lam_a, zp = BANDS[band]
        # Gaia e-/s fluxes and Jy-scaled fluxes both enter as RELATIVE F_nu;
        # chromaticity is scale-free. F_lambda ∝ F_nu / lambda^2.
        wl_nm.append(lam_a / 10.0)
        flam.append(flux / (lam_a ** 2))
    wl_nm, flam = np.array(wl_nm), np.array(flam)
    # extend flat beyond the outer pivots to cover the CMF support (the CMFs
    # themselves vanish at the edges, so the extension carries ~no weight)
    wl_full = np.concatenate([[300.0], wl_nm, [900.0]])
    fl_full = np.concatenate([[flam[0]], flam, [flam[-1]]])
    xyz = colour.spectrum_to_xyz(wl_full, fl_full)
    rgb, exc = colour.gamut_map(xyz)
    # scotopic/photopic factor via V'(lambda)
    wl_s, vp = _scotopic()
    f_i = np.interp(wl_s, wl_full, fl_full)
    s_lum = float((f_i * vp).sum())
    p_lum = float(xyz[1])
    return rgb, exc, (s_lum / p_lum if p_lum > 0 else 1.0)


_scot_cache = None


def _scotopic():
    global _scot_cache
    if _scot_cache is None:
        rows = np.array([[float(v) for v in ln.split(",")[:2]]
                         for ln in Path(sources.require("cie_scotopic")).read_text().splitlines()
                         if ln.strip()])
        _scot_cache = (rows[:, 0], rows[:, 1])
    return _scot_cache


def to_galactocentric(rows):
    """Positions (pc) and velocities (km/s) in the galactocentric frame."""
    n = len(rows)
    pos = np.empty((n, 3)); vel = np.empty((n, 3))
    n_rv = 0
    for i, r in enumerate(rows):
        ra, dec = np.radians(r["ra"]), np.radians(r["dec"])
        d_pc = 1000.0 / r["plx"]
        u_icrs = np.array([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])
        # unit vectors for pm components
        e_ra = np.array([-np.sin(ra), np.cos(ra), 0.0])
        e_dec = np.array([-np.sin(dec) * np.cos(ra), -np.sin(dec) * np.sin(ra), np.cos(dec)])
        v_t = K_PM * (d_pc / 1000.0)
        rv = r["rv"] if r["rv"] is not None else 0.0
        if r["rv"] is not None:
            n_rv += 1
        v_icrs = rv * u_icrs + v_t * (r["pmra"] * e_ra + r["pmdec"] * e_dec)
        u_gal = A_G @ u_icrs
        v_gal = A_G @ v_icrs
        pos[i] = np.array([-R0_PC, 0.0, Z_SUN_PC]) + d_pc * u_gal
        vel[i] = V_SUN + v_gal
    return pos, vel, n_rv


def integrate_orbits(pos0, vel0, t_out_myr, dt_myr=0.25):
    """Leapfrog from t=0 over the (sorted, signed) output epochs. Returns
    positions (n_epochs, N, 3). Also integrates energy/L_z diagnostics."""
    out = np.empty((len(t_out_myr), len(pos0), 3), dtype=np.float32)

    def run(direction, epochs_idx):
        pos = pos0.copy()
        vel = vel0.copy() * direction
        t = 0.0
        targets = [(abs(t_out_myr[j]), j) for j in epochs_idx]
        targets.sort()
        k = 0
        while k < len(targets):
            t_next, j = targets[k]
            while t < t_next:
                h = min(dt_myr, t_next - t)
                a = accel(pos)
                vel_h = vel + 0.5 * h * a
                pos = pos + h * vel_h * KM_S_TO_PC_MYR  # km/s -> pc/Myr
                vel = vel_h + 0.5 * h * accel(pos)
                t += h
            out[j] = pos.astype(np.float32)
            k += 1

    fw = [j for j, tv in enumerate(t_out_myr) if tv >= 0]
    bw = [j for j, tv in enumerate(t_out_myr) if tv < 0]
    run(+1.0, fw)
    run(-1.0, bw)
    return out


def energy_lz(pos, vel):
    """Specific energy ((km/s)^2) and L_z (pc km/s) — suite invariants."""
    r = np.linalg.norm(pos, axis=1)
    rho = np.sqrt(pos[:, 0] ** 2 + pos[:, 1] ** 2)
    zb = np.sqrt(pos[:, 2] ** 2 + MN_B ** 2)
    phi_d = -_G_PC * MN_M / np.sqrt(rho ** 2 + (MN_A + zb) ** 2)
    phi_b = -_G_PC * HQ_M / (r + HQ_A)
    xh = r / NFW_RS
    phi_h = -_G_PC * NFW_MS * np.log(1 + xh) / r
    ke = 0.5 * (vel ** 2).sum(axis=1)
    lz = pos[:, 0] * vel[:, 1] - pos[:, 1] * vel[:, 0]
    return ke + phi_d + phi_b + phi_h, lz
