"""Granule scale from the pressure scale height — fork 4: the SCALE is
derived physics (this module, from the track alone); the internal texture of
a cell is procedural art (Stage 1). The line falls exactly here: nothing in
Stage 1 may alter the cell size this module derives.

  H_p = k T / (mu m_H g)      photospheric pressure scale height
  D   = A_GRAN * H_p          granule diameter (Freytag et al. 2002:
                              characteristic granule size ~10 pressure scale
                              heights for surface convection)
  N   = 4 R^2 / D^2           cell count across the visible disk
                              (pi R^2 / (pi (D/2)^2))

mu is the neutral-atomic mean molecular weight from the track's own surface
composition: mu = 1 / (X + Y/4 + Z/<A_Z>), <A_Z> = 15.5 (declared; the
photosphere is predominantly neutral at these Teff). Validation anchor:
present-day Sun gives H_p ~ 140 km, D ~ 1400 km, N_disk ~ 1e6.
"""
import numpy as np

from .constants import K_B, M_H, R_SUN_M

A_GRAN = 10.0
A_Z_MEAN = 15.5


def mu_neutral(x_h1, y_he4, z_rest):
    return 1.0 / (x_h1 + y_he4 / 4.0 + z_rest / A_Z_MEAN)


def granulation(teff_k, log_g_cgs, log_r_rsun, surface_h1, surface_he4):
    """Returns (H_p metres, D metres, N_disk). Vectorised."""
    teff_k = np.asarray(teff_k, float)
    g = 10.0 ** np.asarray(log_g_cgs, float) * 1e-2  # cgs cm/s^2 -> m/s^2
    z = np.clip(1.0 - np.asarray(surface_h1, float) - np.asarray(surface_he4, float), 0.0, 1.0)
    mu = mu_neutral(np.asarray(surface_h1, float), np.asarray(surface_he4, float), z)
    h_p = K_B * teff_k / (mu * M_H * g)
    d = A_GRAN * h_p
    r = 10.0 ** np.asarray(log_r_rsun, float) * R_SUN_M
    n_disk = 4.0 * r ** 2 / d ** 2
    return h_p, d, n_disk
