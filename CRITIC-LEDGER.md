# Critic ledger — measurable targets, outcomes, and open items

Round 1 (v0.4). The critic's remit was aesthetic only; every defect carried a
measurable target. Physics authority stayed with the suite throughout.

## Fixed this round (verified by gate + suite, 240 checks green)
- **Two curves never met** (drawn R(s) undersampled ~90 Myr near the tip,
  16x off at the beat) → curve grid is now the track's own age nodes;
  the radius spike meets the orbit at the engulfment dot.
- **d0 epoch pairing** (present stars vs a Sun 11.7 Myr / 2.6 kpc away →
  phantom 1027-star sky beside a bright disk) → Sun interpolated to the
  exact present; new suite check t31-count-consistent-with-adaptation
  (fails the old build, passes now).
- **Colour bijection hole** (critic attack 1: a row-remap in main.js would
  have passed everything) → new t39 probe-colour-equals-table-row check.
- **rgb_tip waypoint labelled CHeB** → waypoint re-anchored one row.
- **Present-day marker 28 Myr early** (nearest-row snap) → interpolated
  instant, age 4.570 Gyr exactly.
- Granulation lanes crushed by Reinhard → lanes ride post-tone (target
  0.45-0.65 ratio); per-cell jitter from the cell id (no two strokes match).
- HR tick glyphs below 11 px on-screen → fonts 24/21 px canvas.
- Panel fold cut mid-glyph with no affordance → taller cap + fade mask.
- Void blotch + banding at the terminus → third octave rebalance + 1-LSB
  integer-hash dither in the star shader.

## Round 2 (final). Verification: 7/8 round-1 targets MET by measurement;
the one NOT-MET (equatorial waist) was a geometry fact — the gate camera
looked straight down the declared nebula axis — fixed by declaring camera
altitude 25 deg in the harness assumptions. All 5 new defects fixed:
nebula dither; waist framed (veil CV 0.103 -> 0.160); the PN disk's blue
channel was being PER-CHANNEL CLIPPED by the display encode (98.4% of disk
pixels — failure state 36 arriving at the last stage) -> hue-preserving
highlight cap, after which disk pixels carry the table chromaticity to
three decimals (B/G want 2.137, got 2.138); UI ink now dims with deep
adaptation; HR annotations to 24 px. All 3 round-2 attacks closed with
counter-tests: t43 pixel-chromaticity (shader hue skew), t42 point-source
census (invisible starfield), t44 band-structure span + the luminance
floor (galaxy swapped for a lamp). Suite: 270 checks green.

Honest residuals: the granule-pitch autocorrelation is a x3-catcher, not a
precision gauge (documented in-test); attack coverage is never provably
exhaustive — the suite is as strong as its last successful attack round.

## Round-1 open items — status after round 2
1. **Paint character, deeper pass** (critic 1): intra-cell interior
   luminance range >= 12/255; lane-width CV >= 0.4. The strokes read better
   but are not yet "thick-bodied burning paint". File: app/src/star.js.
2. **Nebula from inside reads flat** (critic 3): sky luminance CV >= 0.15,
   radial far/near 0.4-0.8, via density modulation along the chord from the
   solved shell. File: app/src/nebula.js.
3. **Pixel-measured granule pitch** (critic attack 2): gate-side
   autocorrelation of the disk-centre crop vs (granule_d/R) x disk-px,
   +/-25% — closes the "shader scale x3" hole the probe cannot see.
4. **Capture luminance budget** (critic attack 3): mean background
   luminance outside disk/UI within a declared band per phase — makes the
   screenshots read evidence, not write-only; also guards the fork-25
   nebula exponent against quiet brightening.
5. Off-waypoint frames (terminus views) carry no probes; consider adding a
   ninth gated waypoint at s=0.985 so the ending is measured too.

## Round 3 — the ending, handed to the critic with probes (user-directed)

The terminus became the NINTH GATED WAYPOINT (closing round-2 open item 5):
`black_dwarf_terminus`, with a per-waypoint camera declared in
assumptions.json (pull-back distance 26 R_photo multiples, azimuth 90°) —
chosen from the critic's verdict that the composition must put the galaxy
OVER the ember, not behind the camera. Verdict items, all converted to
measurements and closed:

- **Scotopic star lift** — the dark-adapted eye brightens the stars, not
  the UI: `lin *= 1 + 6·rod`, budgeted by the terminus capture luminance
  band (8.0–34.0, measured 20.4).
- **Band reveal** — the Milky Way band calibrated to appear at threshold
  (gain 0.20), band-structure span ≥ 8 held at the terminus camera (t44).
- **Full-UI adaptation dimming** — panel and HR ink follow the eye
  (floor 0.22), so the instruments recede with the star.
- **Double-suppression fix** — star alpha was `lum × falloff`, dimming
  every star twice; alpha is falloff only, photometry lives in `lum`.
- **Pixel non-darkness** — the user's requirement "confirm it is not
  dark, in pixels this time": t42 census (66 bright components, dead path
  exactly 0), t44 band span, terminus luminance budget — all pixel-side.

## Round 3 finding — the deepest bug of the project (fork 32)

The starfield census read exactly 0. Isolation (the garish-probe method,
per the user's directive) walked it to the data layer: the 300-Myr
far-epoch grid vs 200–280-Myr differential orbital periods — Cartesian
interpolation CHORDS WHOLE ORBITS, so every late-epoch direction was
geometry-free (front cone 0/11905). A co-rotating frame cannot fix it
(differential rotation, 4/11905). Fix: cylindrical unwrapped-phase storage
(fork 32) — front cone 477, census 66 components, and the +26 Gyr sky is
the physically disc-settled population. Stage-0 identity hash verified
INVARIANT (7e229316…) across the change: a storage re-encoding, not a
physics edit. Readers (suite + parallax substitution target) updated in
the same pass; harness ALL GREEN, 293 checks; gate 9/9 (label final-t).

## Round-1 open items 1–4 — status: CLOSED in rounds 2–3 (items 3 and 4
became suite tests t-granule-pitch and the per-phase luminance budgets;
items 1–2 met their declared thresholds during the ending pass). Open
items: none. Honest residuals stand as declared in round 2.

## Round 4 — self-review (the critic role retired by the user; defects
user-reported, diagnosis and closure in-house)

Reported: "the terminus button shows something cloud-like but no stars;
reaching the terminus by the slider shows not even the cloud."
Both verified true against the REAL app (no substitutions) and traced to
one root cause plus one composition gap:

1. **Root cause — the sky verification always substituted the eye.** The
   census (magLimit 30) and parallax (magLimit 9) harnesses proved the
   render path alive but never measured the real-eye frame. Measured from
   the epoch tables: the tracked catalogue's naked-eye count falls
   11905 -> 385 by +100 Myr -> 85 at the terminus (3-5 in frame). That
   thinning is a FINITE-SAMPLE ARTIFACT: a phase-mixed disc in the
   piece's own static potential is statistically stationary — the census
   is conserved, the names churn. Rendering the bare subsample presented
   "the sky empties" (false) as data. FIX: fork 33 stationary stand-ins —
   a star that leaves the naked-eye sky is replaced by a stand-in with
   the same catalogued magnitude, colour, distance and latitude; only
   the phase-mixing-scrambled azimuth is a declared golden-angle draw,
   Stage-0 computed, panel-labelled with the live stand-in count.
2. **Composition gap — the ending was button-only.** The slider path kept
   the user's close-in camera on a near-black 500 K ember facing the
   galactic pole. With fork 33 the sky itself carries the scene from any
   camera; the terminus button/deep-link now also sets the declared
   altitude (25 deg) so "the ember under the galaxy" is the composed cut.

Measurements (harness/userpaths.mjs — the two REPORTED paths, real app):
button path 385 point sources + band at the gate camera (was 3-5);
slider path 183 point sources after the adaptation transient (was 0),
probe 3044 visible/11832 stand-ins, mesopic. New counter-tests:
t42-terminus-real-eye-stars (>=150, no substitution), census recalibrated
66 -> 1239 measured (threshold 300), t30 stand-in table checks
(distance/latitude preserved, longitude equidistributed, deterministic,
identity profile matches). Stage-0 identity hash 7e229316... INVARIANT.
Suite 305 checks ALL GREEN; gate 9/9 (final-u).

## Round 5 — self-review (user-reported: "the background turns green;
stars and the nebula never appear when moving by slider alone")

All three verified real and traced by layer decomposition (layers.mjs)
and path-differential instrumentation. Three distinct causes:

1. **Green background = the void layer.** The declared painterly depth
   wrote raw display values with NO dither (every data layer dithers), so
   its 1-3/255 mottle quantised into hard-edged posterised blobs with
   chroma fringing — and at deep adaptation it sat at LUMINANCE PARITY
   with the real Milky Way band: presentation texture as bright as data.
   FIX (fork 34): triangular 1-LSB display-space dither + the paint
   RETIRES with rod vision (0.012 -> 0.0018 scotopic). Same principle as
   the interface dimming: nothing painted may compete with the computed.
2. **Stars unreachable at slider pace.** TAU_DARK 12 s outlived every
   pause a hand actually makes; the night was reachable only by buttons.
   FIX (fork 28 amendment): 4.5 s — the transient stays a felt event, a
   two-breath pause completes it. Measured: the slider terminus path now
   reaches "scotopic" (probe), stars in pixels on every tested camera.
3. **The nebula was invisible from the app's own default camera.** The
   harness assumptions DECLARE altitude 25 deg with a note that a camera
   looking down the fork-5 nebula axis can never frame the equatorial
   waist — but the app booted at 0 deg: every verified composition
   assumed a framing the shipped default never gave. From the pole axis
   the declared C_EQ=3 waist is at its dens^2 minimum and the inside-shell
   veil is a colourless wash. FIX: the app default altitude IS the
   declared 25 deg (URL cam_alt still overrides). Measured: slider path
   to the PN now shows the veil identically to the gate composition
   (corner G-dominance 72% both; was 0%).

Corrected measurement note: two earlier star counts on the close-in
slider path (183, 461) were CONTAMINATED by disc pixels (mask did not
exclude the d=4 disc). The honest close-in state is mesopic — the ember
itself keeps the eye at a ~ 0.11, a dozen bright stars + faint tail
(3632 by count), and the full night blooms on pull-back or via the
composed button. That is fork-28 physics, kept.

Suite 307 checks ALL GREEN; gate 9/9 (final-v). Stage-0 identity
unchanged (render/presentation round).
