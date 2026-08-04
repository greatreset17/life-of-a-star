"""Named constants and THE FORK BLOCK — the canonical record of every decision
point where two defensible choices existed and one was taken. Not the prompt,
not the docs: this block. A fork discovered during implementation is added here
the moment it is taken. Suite test 49 checks that every constant governing a
declared fork is referenced from this block and that each fork names a reason.

================================ FORK BLOCK ================================

FORK 1 — Gamut policy. Derived chromaticities leave sRGB, worst on the cool
  branch. CHOSEN: perceptual gamut mapping in Oklab — hue and lightness held,
  chroma compressed toward the boundary (binary-search projection toward the
  achromatic axis at constant L, h); the out-of-gamut excursion (Oklab chroma
  distance) is recorded per EEP and exposed in the panel. REJECTED: nearest
  in-gamut substitute / per-channel clip, because clipping destroys the
  derivation exactly where it matters most. Governs: GAMUT_MAP_METHOD.
  [decided v0.1]

FORK 3 — Precision split. CHOSEN: float64 for everything offline (pipeline and
  harness mirror); f32 only inside the GPU shader, with the boundary at the
  Stage 0 table files (tables are written float64-derived values rounded to
  f32-representable decimals so Stage 1 upload is exact). REASON: offline cost
  is irrelevant, shader f64 is unavailable; a declared boundary at the table
  file makes the split auditable. Governs: TABLE_FLOAT_DECIMALS. [decided v0.0]

FORK 7 — Integrator honesty. The orbital integration (mirror and pipeline) is
  RK4 / adaptive step control. It is NOT symplectic and is nowhere called
  symplectic. Conservation is held by step control and MONITORED continuously
  (energy ledger with per-substep attribution; unattributed residual is the
  alarm, with a mechanical dt-scaling discrimination between numerical and
  bookkeeping residuals — harness/mirror.py discriminate_residual). REASON:
  the problem has time-varying M(t) and dissipative terms, where symplecticity
  buys nothing; honesty about that beats a misleading label. [decided v0.0]

FORK 12 — Harness probe surface (discovered v0.0). The visual gate needs
  application state without test hooks in shipping source. CHOSEN: the
  instrument panel IS the probe surface — its [data-q] elements are shipped,
  user-facing functionality displaying exactly the quantities the gate needs;
  the gate reads them and writes nothing. Waypoint/camera/tier arrive via
  public deep-link URL parameters (shipped feature), so harness assumptions
  are explicit per-run, never inherited from app defaults. REJECTED: a
  window-level state export, because it exists only for verification and
  would be a test seam. [decided v0.0]

FORK 13 — CIE observer provenance (discovered v0.0). CHOSEN: CIE 1931 2-deg
  standard observer, 5 nm tabulation, retrieved from CVRL (ciexyz31.csv,
  checksummed in the manifest). 2-deg not 10-deg because point-like stellar
  images are foveal; 1931 not 2006 because the sRGB colorimetry the display
  chain targets is defined against 1931. Governs: CMF_SOURCE. [decided v0.0]

============================== END FORK BLOCK ==============================

Remaining forks (2, 4, 5, 6, 8, 9, 10, 11, …) are declared here in the pass
that decides them; an undeclared fork is failure state 53.
"""

# fork 3
TABLE_FLOAT_DECIMALS = 9  # round-trips exactly through IEEE-754 binary32

# fork 13
CMF_SOURCE = "data/raw/cie/ciexyz31.csv"
CMF_SHA256 = "a61eb7a6d3aa3cede8b0baf2b63d01610a124038c3238390ba5b5540829d7dde"

# physical constants (CODATA 2018 / IAU 2015 nominal)
G_SI = 6.67430e-11          # m^3 kg^-1 s^-2
SIGMA_SB = 5.670374419e-8   # W m^-2 K^-4
K_B = 1.380649e-23          # J K^-1
M_H = 1.6735575e-27         # kg (hydrogen atom)
R_SUN_M = 6.957e8           # IAU nominal
L_SUN_W = 3.828e26          # IAU nominal
M_SUN_KG = 1.98892e30
AU_M = 1.495978707e11
YEAR_S = 3.15576e7          # Julian year
