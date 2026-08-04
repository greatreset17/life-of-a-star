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
  [decided v0.1]

FORK 15 — Spectral-grid support boundary in log g (discovered v0.1). No
  published hydrostatic atmosphere grid reaches below logg = -0.5 (BT-Settl
  floor -0.5; MARCS spherical/standard floor -0.5, verified against both
  services). 65 TP-AGB pulse-tip EEPs (941-1351, Teff 2667-2825 K) sit at
  logg down to -0.788 — physically these are pulsating dust-enshrouded LPVs
  for which hydrostatic atmospheres genuinely do not exist. CHOSEN: the
  region-B pattern applied in logg — chromaticity evaluated AT the grid edge
  (logg = -0.5), the per-EEP excursion Dlogg recorded in the table, exposed
  as its own panel readout ("spectral grid: edge-evaluated, Dlogg=…"), never
  folded into data_state (which test 22 reserves for the cooling horizon).
  REJECTED: silent clamp (a fallback), and refusing to render 24% of arc
  length that the track legitimately traverses. Governs: SPECTRA_LOGG_FLOOR.
  [decided v0.1]

FORK 16 — Spectral-grid ownership of the (Teff, logg) plane (discovered
  v0.1). One grid cannot cover 2667-120518 K at logg -0.79..+7.64. CHOSEN
  (single-ownership assignment, two seam crossings along the whole track):
    Teff <= 7000                          -> BT-Settl (Allard+ 2012, AGSS2009)
    7000 < Teff <= 50000 and logg <= 5.0  -> ATLAS9 (Castelli & Kurucz 2003)
    Teff > 50000, or Teff > 20000 & logg > 5.0 -> TMAP grid 2 (H+He, TheoSSA)
  Seams are declared constants (SPECTRA_SEAM_COOL_K, SPECTRA_SEAM_HOT_K);
  the chromaticity discontinuity across each seam is MEASURED and asserted
  small by a suite test, never blended away by an invented crossfade.
  Koester DA joins for the white-dwarf cooling table in v0.3.
  MEASURED REALITY (recorded v0.1): the hot seam sits at 40000 K because the
  track's logg crosses TMAP2's floor (4.0) there; in 32000-40000 K the track
  (logg 3.6-4.0) lies below BOTH CK03's and TMAP2's floors, and in
  8300-9250 K below CK03's — those rows are fork-15 edge evaluations with
  recorded Dlogg (max +0.56 at 9147 K, ~+0.38 at 32000 K). Accepted because
  integrated visible chromaticity is nearly logg-insensitive for smooth
  hot continua (unlike the fully-covered cool molecular bands). NAMED
  UPGRADE PATH if the seam/edge tests ever show a visible artefact: TLUSTY
  BSTAR2006 (15-30 kK, logg>=1.75) + OSTAR2002 (27.5-55 kK, logg>=3.0),
  both served by SVO. [decided v0.1]

FORK 17 — Composition held at [M/H]=0, alpha=0 for BT-Settl/ATLAS9
  (discovered v0.1). The track's surface metallicity drifts slightly with
  diffusion and dredge-up; the spectral grids are fetched at the single
  solar-metallicity node. REASON: the chromaticity effect of |d[M/H]| ~ 0.1
  is far below the gamut-mapping displacement already applied, and a 2-D
  (Teff, logg) interpolation with a fixed third axis keeps every retrieved
  node inside the manifest's declared subset. [decided v0.1]

FORK 18 — Limb-darkening sources (decided v0.1). One law (Claret 4-param),
  two published fits: Neilson & Lester 2013 SPHERICAL SATLAS (V) for giants
  (logg < 3, Teff <= 8000), interpolated in (Teff, logg, M) with M from the
  track — sphericity carries the soft drooping giant limb; Claret & Bloemen
  2011 planar ATLAS (Johnson V, case-sensitive ==V in the VizieR query — a
  plain V ALSO matches Stromgren v, a measured pitfall that produced a
  wrong dark profile before it was caught) elsewhere up to 50000 K; above
  that, fork-15 edge evaluation with excursion = Teff - 50000 (limb is
  sub-pixel there). MEASURED SEAM FACT: at the logg=3 seam the disk
  interior is continuous (max |dI| ~ 0.03) while the limb region (mu<0.1)
  diverges by ~0.23 — this is the geometry-family difference itself
  (spherical profiles droop to zero, planar do not; Neilson & Lester's own
  result) and is recorded, not blended. Upgrade path: the same catalog's
  raw I(mu) profiles. Met=L (least-squares) because the flux-conserving
  variant is not published for this band/composition; test 11 carries the
  fit's integral error in its tolerance. [decided v0.1]

FORK 19 — Colour premises corrected by measurement (recorded v0.1). Three
  claims the project brief carried were tested against the mandated data and
  falsified; the tests were CORRECTED to assert what is true, with the
  original intent preserved by stronger checks:
  (a) "The M giant pushes past the display primaries." MEASURED: the
      integrated photospheric chromaticity never leaves sRGB anywhere on
      the track (coolest branch tops at x=0.467, near CCT 2700 K —
      displayable, like an incandescent bulb). Test 33's non-zero-excursion
      assertion moved to the gamut-mapping MACHINERY (synthetic line) and
      to the nebula's line emission (v0.3), which genuinely leaves sRGB.
  (b) "A 3100 K giant and a 3100 K blackbody are visibly different
      colours." MEASURED: TiO carves the SPD enormously (705-715 nm at 17%
      of pseudo-continuum vs 91% for Planck) but the INTEGRATED chromaticity
      lands 0.0054 from the Planck point — the bands cut nearly
      locus-symmetrically. Test 6 now asserts the band structure directly
      (depth < 0.5) and keeps a swapped-chain tripwire (dxy > 0.003).
  (c) x(Teff) monotonicity holds per luminosity class, not globally
      (blanketed giants deviate up to 0.037 from the locus; A-types via
      the Balmer jump). Tests assert MS rank-correlation and calibrated
      locus adjacency (< 0.05) instead.
  [decided v0.1]

FORK 21 — The drag toggle's meaning, corrected by the calculation
  (recorded v0.2). The brief's premise — disable tidal+dynamical drag and
  the curves miss, the Earth survives — is FALSE on the mandated track:
  MIST v1.2's eta_R=0.1 leaves the RGB nearly massless-loss-free, the orbit
  expands only to ~1.36 AU, and the TP-AGB photosphere (1.64 AU) overruns
  it by pure geometry. MEASURED: with drag, tides capture the Earth at the
  RGB tip (11.336 Gyr, 6.77 Gyr from present); without drag it dies anyway,
  ~130 Myr later, swallowed on the AGB. CHOSEN: the toggle ships with its
  honest meaning — drag decides WHEN and WHERE, not WHETHER — and the panel
  says exactly that, alongside the S&CS-2008 comparison in which the
  no-drag Earth does survive (their 0.332 Msun RGB loss pushes the orbit
  beyond their smaller AGB). The outcome is a calculation, not a script,
  and this is what the calculation says on this data. Computing effect 1
  alone remains failure state 6 — it is also, on this track, no longer the
  comforting answer. [decided v0.2]

FORK 22 — Orbit-averaged evolution (decided v0.2). CHOSEN: the two-body
  problem is advanced as orbit-averaged ODEs in a(t) (e=0 held), because 1e10 orbits
  cannot be integrated directly and the averaged equations are the standard
  treatment (S&CS 2008, Villaver & Livio 2009). The harness's vector
  integrator (Tier 1) validates the averaged mass-loss rate over short
  windows; tide and drag prefactors are declared constants
  (TIDE_PREFACTOR, C_DRAG in pipeline/earth.py). Engulfment = photospheric
  contact, a terminal event; the inspiral inside the envelope is outside
  the declared boundary. [decided v0.2]

FORK 11 — The MIST-to-cooling join (decided v0.3). CHOSEN: the cooling
  spine begins at exactly MIST's final Teff (47623 K) — Teff and TIME are
  matched by construction (the Bedard age axis is offset so the join is
  simultaneous). Allowed to be discontinuous and MEASURED: L (-7.8%) and R
  (-4.2%) — MIST's young-white-dwarf envelope and the Bedard et al. 2020
  models are two independent codes and do not agree at the handoff; the
  discontinuity is reported in the panel, the join is marked in the HR
  diagram, and the suite bounds it at 12%/6% (a wrong bracketing mass or a
  units slip produces >20%). REJECTED: smoothing/blending (a silent edit of
  both codes), and joining in L instead (which would move the mismatch into
  Teff, the axis the colour chain keys on). Sequences: seq_050/055_thick
  interpolated to the track's final mass 0.5398 Msun. [decided v0.3]

FORK 2 — Terminus and data horizon (decided v0.3). CHOSEN: two constants —
  the HORIZON is where the Bedard tables end (~1470 K — they run further than
  the brief guessed); the TERMINUS is TERMINUS_TEFF_K = 500 K, a factor ~6
  below the coolest OBSERVED white dwarf (COOLEST_WD_OBSERVED_K = 3000 K,
  WD J2147-4035, Elms et al. 2022), deep black-dwarf regime, chosen so
  region B's arc share stays small (measured ~9%) while the piece still
  ends in true darkness. Governs: TERMINUS_TEFF_K, COOLEST_WD_OBSERVED_K.
  [decided v0.3]

FORK 9 — Beyond-data cooling law (decided v0.3). CHOSEN: continue past the
  horizon under one named law — Debye-regime exponential, Teff(t) =
  T_h exp(-(t-t_h)/tau), tau anchored to the last tabulated dTeff/dt
  (value and derivative continuous by construction), R frozen at the
  horizon value, L from Stefan-Boltzmann. Region B is declared here,
  single-law, anchored, bounded by the terminus, and labelled on screen
  for its entire duration — all five properties that distinguish it from
  a fallback. [decided v0.3]

FORK 5 — Planetary nebula treatment (decided v0.3). CHOSEN — SOLVED: thin-shell
  interacting-winds dynamics (energy-driven bubble in the superwind's r^-2
  medium, ODE-integrated), the time-dependent ionisation balance
  (photoionisation vs case-B recombination), and the emission-line spectrum
  (H case-B + [OIII] + [NII] two-level atoms with published atomic
  constants and the track's own surface O/N abundances) through the one
  CIE chain. ASSERTED, not solved: spherical symmetry, T_e = 1e4 K,
  thin-shell thickness 0.1 R_s, O++/N+ ionic fractions (0.8/0.2), wind
  speeds via the escape-velocity relation from the track's M and R
  (v_slow = 0.5 v_esc at AGB end; v_fast = v_esc of the core) because the
  track's v_wind column is unpopulated on the AGB. Instabilities, clumping
  and filamentary structure are OUTSIDE the declared boundary.
  [decided v0.3]

FORK 24 — Granulation on the cooling track (decided v0.3). CHOSEN: the
  derived H_p scale is computed for every spine node (single formula, fork
  4), but the RENDERED granulation contrast is gated by the convective
  regime: DA atmospheres are radiative above ~15000 K, so cooling-track
  nodes hotter than the convective boundary draw zero granule contrast; the
  derived count is still reported (derived-vs-rendered divergence is
  exactly what the panel's two numbers exist for). AMENDED after the first
  v0.3 gate captures: the gate keys on Teff, not phase — surface convection
  dies above ~8-10 kK everywhere (the observed granulation-flicker
  boundary), so the post-AGB sprint fades its granules exactly as a hot DA
  does; contrast ramps 10000 -> 8000 K. Governs: WD_CONVECTION_ONSET_K.
  [decided v0.3]

FORK 23 — Cooling-tail chromaticity pathways (decided v0.3). CHOSEN:
  Koester (2010) DA spectra through the standard chain above 5000 K; below,
  no public cool-DA spectra exist, so a coarse SED is REBUILT from the
  Montreal tables' SDSS ugriz AB magnitudes (published cool-WD atmospheres
  incl. CIA) at their published effective wavelengths and fed through the
  IDENTICAL CIE function — same chain, coarser sampling, nothing invented,
  no Planck anywhere. Below the tables' own 1500 K floor (region B),
  chromaticity holds the 1500 K table edge with the excursion recorded;
  the fade to black is luminance-driven and labelled. The 5000 K pathway
  seam is measured by the suite. [decided v0.3]

FORK 6 — Background stars (decided v0.4). CHOSEN: positions and orbits are
  computed physics (Gaia DR3 astrometry, leapfrog in the fork-27 potential);
  existence, mass and luminosity are FROZEN at the present epoch. Ten
  billion years hence many rendered stars will not exist — predicting which
  would require population synthesis, which is deliberately outside the
  boundary so the Sun remains the only thing in the frame with a life.
  Stars with non-positive parallax (346) are EXCLUDED and counted, never
  placed at an assumed distance. [decided v0.4]

FORK 26 — Star and band chromaticity from broadband fluxes (decided v0.4).
  CHOSEN: each Gaia star's G/BP/RP fluxes (Hipparcos B/V for the ~132
  bright stars Gaia saturates on — without them the sky is missing Sirius)
  form a coarse SED at the SVO-published pivot wavelengths, through the
  IDENTICAL CIE chain (fork 23's precedent). Scotopic weights come from the
  same SEDs against CIE 1951 V'(lambda) — the Purkinje shift is carried by
  data. Stars lacking DR3 radial velocity (~23%) evolve with their measured
  transverse motion and RV=0, counted in the meta (their unknown radial
  drift is second-order for sky appearance). Upgrade path: DR3 XP spectra.
  [decided v0.4]

FORK 27 — Galactic dynamics and the Milky Way band (decided v0.4). CHOSEN:
  MWPotential2014-class potential (Miyamoto-Nagai disk + Hernquist bulge +
  NFW halo, halo amplitude solved so v_c(R0)=220 km/s); leapfrog, all stars
  vectorised; energy and L_z are suite invariants. MEASURED: circular
  period at R0 = 223 Myr (the brief's 220-240 band); the Sun's own
  azimuthal period in this potential is 244 Myr (eccentric orbit — both
  numbers asserted for what they are). The BAND is the catalogue's own
  unresolved integrated light (healpix aggregate, 6.5<G<12) whose dark
  rifts are the real dust already imprinted in the observed fluxes —
  nothing painted, and no separate dust cube: a 3-D dust map would matter
  only for kpc-scale viewpoint shifts that are outside the declared
  boundary (the band is frozen in shape, re-azimuthed rigidly with the
  solar orbit). Named upgrade path: Edenhofer 2023 / Lallement 2022 cubes.
  [decided v0.4]

FORK 28 — The eye's transient (decided v0.4). CHOSEN: adaptation STATE
  physics is honest (equilibrium visibility follows field luminance; rod
  vision is achromatic with data-derived scotopic weights; the galaxy
  emerges only below deep-mesopic adaptation), but the TRANSIENT is
  compressed — real dark adaptation takes tens of minutes; here
  tau_dark = 12 s so a hand on the slider can feel it. A deep link or
  waypoint jump is a CUT, not continuous viewing: the eye arrives at the
  new scene's equilibrium; continuous slider motion pays the transient.
  Also fork 20/25 live here: the v0.1 tone curve (Stevens-compressed
  bolometric luminance) and the nebula's interim (Sigma/Sigma_sun)^0.1
  mapping are presentation, superseded progressively by this eye model.
  [decided v0.4]

============================== END FORK BLOCK ==============================

Remaining forks (2, 4, 5, 6, 8, 9, 10, 11, …) are declared here in the pass
that decides them; an undeclared fork is failure state 53.
"""

# fork 1
GAMUT_MAP_METHOD = "oklab-chroma-compression-constant-L-h"

# fork 3
TABLE_FLOAT_DECIMALS = 9  # round-trips exactly through IEEE-754 binary32

# forks 15, 16
SPECTRA_LOGG_FLOOR = -0.5
SPECTRA_SEAM_COOL_K = 7000.0   # BT-Settl | ATLAS9
SPECTRA_SEAM_HOT_K = 40000.0   # ATLAS9 | TMAP2 (track logg crosses tmap2's
                               # floor 4.0 at T~40kK; measured, see fork 16)
SPECTRA_TMAP_LOGG_TAKEOVER = 5.0  # above ATLAS9's ceiling, TMAP2 owns T>20000
SPECTRA_BAND_ANGSTROM = (2500.0, 11000.0)  # stored subset; CMF support + margin

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

# fork 2 — the data horizon is where Bedard et al. 2020 end (~1470 K, the
# coolest tabulated model at these masses); the terminus is a factor ~6
# below the coolest OBSERVED white dwarf, deep in the black-dwarf regime,
# keeping region B's arc share finite and small. Governs: TERMINUS_TEFF_K.
TERMINUS_TEFF_K = 500.0
# coolest observed white dwarf: WD J2147-4035, Teff ~ 3050 K (Elms et al.
# 2022, MNRAS 517, 4557) — rounded declared constant for marker two.
COOLEST_WD_OBSERVED_K = 3000.0

# fork 24
WD_CONVECTION_ONSET_K = 15000.0
