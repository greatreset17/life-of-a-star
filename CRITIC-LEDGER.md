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

## Open items (targets stand; not yet implemented)
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
