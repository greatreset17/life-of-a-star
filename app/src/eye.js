// The observer — the eye is the instrument (fork 28). Photopic/scotopic
// state and dark adaptation. The STATE physics is honest: what is visible
// at a given adaptation follows the luminance in the field, sky visibility
// is computed from the star's own brightness, and rod vision is rendered
// achromatic with per-star scotopic weights derived offline from V'(lambda)
// (the Purkinje shift lives in those weights — data, not taste). The
// TRANSIENT is compressed: real dark adaptation takes tens of minutes; the
// declared time constants below compress that to seconds so a hand on the
// slider can feel it.
// fork 28 amendment (user-measured twice): at 12 s the slider's natural
// pace never reached the dark sky at all — the transient outlived every
// pause a hand actually makes, so the piece's own night was unreachable
// except by the waypoint buttons. 4.5 s keeps the transient a felt event
// (the sky still ARRIVES) while a two-breath pause completes it.
const TAU_DARK_S = 4.5;    // compressed from ~20 min (declared)
const TAU_LIGHT_S = 0.4;   // light adaptation is genuinely fast

export class Eye {
  constructor() {
    this.a = 1.0; // adaptation level: 1 photopic (bright field) .. 0 scotopic
  }

  // fieldLum: tone-domain luminance of the stellar disk weighted by the
  // fraction of the visual field it fills (computed by main.js from the
  // same quantities the panel reports)
  step(fieldLum, dtS) {
    const target = Eye.equilibrium(fieldLum);
    const tau = target > this.a ? TAU_LIGHT_S : TAU_DARK_S;
    this.a += (target - this.a) * (1 - Math.exp(-dtS / tau));
    return this.a;
  }

  static equilibrium(fieldLum) {
    return Math.max(0, Math.min(1, Math.log10(1 + 80 * fieldLum) / 2));
  }

  // a deep link or waypoint jump is a CUT, not continuous viewing: the eye
  // arrives already adapted to the new scene (fork 28); continuous slider
  // motion still pays the adaptation transient
  jumpTo(fieldLum) {
    this.a = Eye.equilibrium(fieldLum);
  }

  // limiting magnitude: +6.5 fully dark-adapted, hopeless when the
  // photosphere floods the field — no frame shows both a saturated disk
  // and a populated star field (suite test 31)
  magLimit() {
    return 6.5 - 9.5 * this.a;
  }

  // rod/cone blend: 0 = pure cone colour, 1 = pure rod grey
  rodFraction() {
    return Math.max(0, Math.min(1, (0.25 - this.a) / 0.25));
  }
}
