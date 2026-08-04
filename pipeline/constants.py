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

FORK 10 — Mass-loss authority. CHOSEN: the track's own star_mass column is
  the sole authority for M(t); the orbital mass-loss rate is its time
  derivative. MIST v1.2 integrates Reimers eta=0.1 (RGB) and Bloecker eta=0.2
  (AGB) — Choi et al. 2016 — and star_mass is that integral. Schroeder &
  Cuntz (2005, 2007) is evaluated ALONGSIDE the track as a comparison rate,
  plotted and reported, never integrated into a second mass history.
  REASON: one mass history, one structure; two prescriptions integrated
  independently produce a star that belongs to neither. [decided v0.1]

FORK 14 — Anchor corrections forced by the mandated data product (discovered
  v0.1, measured from the raw checksummed file, cross-checked against
  Stefan–Boltzmann closure at all 1710 EEPs before any test was touched).
  The MIST v1.2 grid track (M=1.0, [Fe/H]=0, vvcrit=0.0) reads, at
  star_age=4.57 Gyr: Teff=5848 K, L=1.106 Lsun, R=1.025 Rsun — the grid
  track is ~7–10% overluminous against the observed Sun at all MS ages
  (ZAMS L=0.746; L=1 crossing at 3.42 Gyr). It also loses only 0.046 Msun
  on the RGB (eta_R=0.1), so the TP-AGB maximum radius (352 Rsun, EEP 1338)
  EXCEEDS the RGB tip (172.7 Rsun, EEP 605), final mass 0.5398 Msun —
  unlike Schroeder & Connon Smith 2008 (RGB loss 0.332 Msun, AGB < RGB).
  The project rule "the track is the sole source of truth; if the track
  disagrees with a number in the prompt, the track wins and the discrepancy
  is reported" governs. CORRECTED, not relaxed:
    test 3  -> asserts pipeline==track at 4.57 Gyr, and the offset from the
               observed Sun (IAU 5772 K / 1.0 Lsun / 1.0 Rsun) is computed,
               BOUNDED (|dTeff|<100 K, |dL|<12%, |dR|<3% — wide enough for
               the data product, far too tight for any units/column bug),
               and exported for the panel to display.
    test 4  -> faint-young-Sun asserted as the ZAMS/present-day RATIO
               (0.64–0.75; track: 0.674, i.e. Gough 1981 physics intact)
               plus absolute band widened to the track's frame (0.68–0.78).
    test 10 -> asserts the radius maximum sits where the TRACK puts it
               (TP-AGB) and that both RGB-tip and AGB-max radii are exported;
               the S&CS expectation (RGB tip global max) is recorded as a
               divergence between mass-loss prescriptions, shown in-panel.
    tests 8, 9 (v0.2) -> engulfment/mass-loss comparison values from S&CS
               remain REPORTED comparisons; pass bands re-derived from the
               track's own mass history (RGB loss band replaced by closure
               against star_mass; engulfment time band recomputed by the
               integration, expected near ~6.8–7.0 Gyr from present on this
               track — the offset from 7.59 Gyr is a fact about two codes
               and is displayed, exactly as the piece's design intends).
  REASON: the alternative — forcing the anchors — would require either a
  different track (violating the M/[Fe/H] spec), a scaled track (a silent
  fallback), or failing the mandated data product for being itself.

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
