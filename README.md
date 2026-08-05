# The Life of a Star

The Sun's entire life — protostellar contraction to the cold black dwarf —
in which every photon of colour is derived from published data, never chosen.
Drag one slider and the star becomes, in sequence, four different objects; at
the end, the galaxy no one could see at the beginning stands over the ember.

The canonical record of every decision is the **fork block** at the head of
`pipeline/constants.py` (29 declared forks). Four of the brief's own premises
were falsified by the mandated data and are recorded there, not hidden:
the MIST grid Sun runs +76 K / +10.6% L of the observed Sun (fork 14); the
AGB outgrows the RGB tip under MIST's own mass loss (fork 14); the no-drag
Earth dies anyway, overrun on the AGB — drag decides *when and where*, not
*whether* (fork 21); and the ember dies **blue**, not red — collision-induced
H₂ absorption in the published cool-DA models (fork 29).

## Running

```
# the experience (serve app/ statically; it fetches nothing remote)
cd app && python3 -m http.server 8080     # open http://localhost:8080

# the verdict
./.venv/bin/python harness/run.py all     # mirror + static + full suite
node harness/gate.mjs app <label>         # visual gate: 9 waypoints,
                                          # screenshot + mandatory state probe
```

Deep links are shipped functionality: `?wp=rgb_tip`, `?s=0.985`,
`&cam_d=6&cam_az=40&cam_alt=15&tier=high|low`.

## Layout

- `harness/` — Stage −1, built first. Physics mirror (independent float64
  numerics), visual gate (a capture without a complete probe is refused
  before the screenshot is written), identity hashing, static checks
  (identifier purity, colour literals, sinless shader hashes), and the
  suite (`harness/suite/`, 295 checks): track fidelity, colour chain,
  granulation, limb darkening, Earth, cooling, nebula, sky, gate probes,
  pixel-measured visual metrics, acquisition integrity, fork completeness.
- `pipeline/` — Stage 0 (Python, float64). Acquisition against a
  checksummed manifest (`manifest.json`; `sources.require()` is the single
  chokepoint — no fallback can exist because there is nowhere to get one).
  MIST spine → colour chain (spectrum → CIE 1931 2° → XYZ → linear sRGB →
  Oklab gamut map) → limb darkening → granulation → Earth integration →
  Bédard cooling + region B → interacting-winds nebula → Gaia sky.
- `app/` — Stage 1 (browser, f32 in-shader only). Fetches only its local
  Stage 0 tables; a missing table is a visible refusal. Three.js vendored;
  import map pins `three` and `three/addons/`.
- `CRITIC-LEDGER.md` — judge two's measurable targets and outcomes across
  rounds; open items live there, never silently.

## Data (all pinned in pipeline/manifest.json)

MIST v1.2 EEP track (1.0 M☉, [Fe/H]=0) · 567 BT-Settl/ATLAS9/TMAP2 spectra
+ 160 Koester DA + 215 full-range EUV SEDs (SVO) · Neilson & Lester 2013
spherical + Claret & Bloemen 2011 limb darkening (VizieR) · Bédard et al.
2020 cooling sequences + photometry tables (Montreal) · Gaia DR3 naked-eye
catalogue + HEALPix integrated-light band + Hipparcos bright end · CIE 1931
2° CMFs + CIE 1951 scotopic V′ (CVRL).

## Honesty rules, enforced structurally

No blackbody anywhere in any colour path (the divergence is tested in-SPD:
TiO carves 83% where Planck carves 9%). No white balance. No fallbacks —
absence renders as absence, by name. Region B (beyond the ~1470 K data
horizon) is declared, single-law, anchored, bounded, and labelled on screen
for its whole duration. The panel is the probe surface; no test hook exists
in shipping source, and no verification path writes to physical state.
Manual slider only — autoplay is deliberately absent from version one.
