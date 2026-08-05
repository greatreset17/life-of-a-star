// @render-path — the sky as seen. Star DIRECTIONS and distances are
// computed every frame in float64 from the catalogued 3D positions
// relative to the moving camera — the change of direction under camera
// translation IS parallax, exact by construction — and the GPU receives
// only well-conditioned coordinates (a camera-anchored shell at R_DRAW):
// raw parsec-scale vertex coordinates die in the f32 vertex stage of this
// render path (established empirically: in-app points render at radius
// 1e2 and vanish at 2e8 with identical pipeline state). Colours are the
// table's chain-derived chromaticities; no lens, no flare, no twinkle.
// Each point is entirely present or entirely absent (whole-instance
// culling); rod vision drains colour via per-star scotopic weights.
import * as THREE from "three";

const PC_TO_RSUN = 3.0856775814913673e16 / 6.957e8;
const R_DRAW = 1.0e4; // camera-anchored shell radius, scene units

const vert = /* glsl */ `
  attribute vec3 rgb;
  attribute float mag;      // apparent magnitude at the current epoch
  attribute float scot;     // scotopic/photopic luminance factor
  varying vec3 vRgb;
  varying float vMag;
  varying float vScot;
  void main() {
    vRgb = rgb;
    vMag = mag;
    vScot = scot;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = 2.5;
  }
`;

const frag = /* glsl */ `
  precision highp float;
  varying vec3 vRgb;
  varying float vMag;
  varying float vScot;
  uniform float uMagLimit;
  uniform float uRod;

  void main() {
    // whole-point visibility: a star is present or absent, never partial
    if (vMag > uMagLimit) discard;
    // brightness scales with magnitude ABOVE threshold: full at 5 mag
    // (x100) over the limit, fading to 1% AT the limit. The previous form
    // clamped every visible star to identical full brightness — magnitude
    // was a binary gate, caught by the pixel-photometry test (t26).
    float lum = pow(10.0, -0.4 * (vMag - (uMagLimit - 5.0)));
    lum = min(lum, 1.0);
    vec3 cone = vRgb * lum;
    vec3 rod = vec3(lum * vScot * 0.8);
    vec3 lin = mix(cone, rod, uRod);
    // scotopic display lift: a dark-adapted eye sees stars PLAINLY; the
    // un-lifted mapping left all 21 visible stars ~3/255 over the sky —
    // mechanically present, visually absent (critic's final verdict)
    lin *= 1.0 + 6.0 * uRod;
    // soft round point
    vec2 d = gl_PointCoord - vec2(0.5);
    float fall = smoothstep(0.5, 0.15, length(d));
    lin *= fall;
    vec3 enc = mix(lin * 12.92, 1.055 * pow(lin, vec3(1.0 / 2.4)) - 0.055,
                   step(0.0031308, lin));
    // alpha carries only the point PROFILE: with additive blending the
    // brightness lives in the colour — an alpha that also scales with lum
    // squares the suppression (stars fell to ~1 count; measured)
    gl_FragColor = vec4(enc, fall);
  }
`;

export class SkyField {
  constructor(scene, skyMeta, positionsF32, sunEpochsF32) {
    this.meta = skyMeta;
    this.pos = positionsF32;      // [n_epoch][n_star][3] galactocentric pc
    this.sunE = sunEpochsF32;     // [n_epoch][3] — the Sun ON THE SAME GRID
    const n = skyMeta.n_star;
    // heliocentric quantities always pair star(epoch) with Sun(SAME epoch,
    // same interpolation weights). Any other pairing turns shared orbital
    // motion into phantom structure — measured three times in three forms
    // (magnitudes, then marker epoch, then every direction at once).
    {
      const eps = skyMeta.epochs_myr;
      const k0 = eps.reduce((b, v, idx) => Math.abs(v) < Math.abs(eps[b]) ? idx : b, 0);
      const Z = positionsF32.subarray(k0 * n * 3, (k0 + 1) * n * 3);
      // cylindrical storage: reconstruct Cartesian before differencing
      const sR0 = sunEpochsF32[k0 * 3], sP0 = sunEpochsF32[k0 * 3 + 1], sz0 = sunEpochsF32[k0 * 3 + 2];
      const sx = sR0 * Math.cos(sP0), sy = sR0 * Math.sin(sP0);
      this.d0 = new Float32Array(n);
      for (let i = 0; i < n; i++) {
        const j = i * 3;
        const xx = Z[j] * Math.cos(Z[j + 1]), yy = Z[j] * Math.sin(Z[j + 1]);
        this.d0[i] = Math.hypot(xx - sx, yy - sy, Z[j + 2] - sz0);
      }
    }
    this.geo = new THREE.BufferGeometry();
    this.posAttr = new THREE.BufferAttribute(new Float32Array(n * 3), 3);
    this.magAttr = new THREE.BufferAttribute(new Float32Array(n), 1);
    const rgb = new Float32Array(n * 3);
    const scot = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      rgb.set(skyMeta.rgb_lin[i], i * 3);
      scot[i] = skyMeta.scotopic_factor[i];
    }
    this.geo.setAttribute("position", this.posAttr);
    this.geo.setAttribute("mag", this.magAttr);
    this.geo.setAttribute("rgb", new THREE.BufferAttribute(rgb, 3));
    this.geo.setAttribute("scot", new THREE.BufferAttribute(scot, 1));
    this.uniforms = { uMagLimit: { value: 6.5 }, uRod: { value: 0 } };
    const mat = new THREE.ShaderMaterial({
      vertexShader: vert, fragmentShader: frag, uniforms: this.uniforms,
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    });
    this.points = new THREE.Points(this.geo, mat);
    this.points.frustumCulled = false;
    this.points.renderOrder = 1;
    scene.add(this.points);
    this.visibleCount = 0;
  }

  // ageYr: current stellar age; magLimit/rod from the eye; camPos: the
  // camera position in scene units (the parallax baseline)
  update(ageYr, magLimit, rod, camPos) {
    const m = this.meta;
    const tMyr = (ageYr - m.present_age_yr) / 1e6;
    const eps = m.epochs_myr;
    let lo = 0, hi = eps.length - 1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (eps[mid] <= tMyr) lo = mid; else hi = mid; }
    const f = Math.max(0, Math.min(1, (tMyr - eps[lo]) / Math.max(eps[hi] - eps[lo], 1e-9)));
    const n = m.n_star;
    const A = this.pos.subarray(lo * n * 3, (lo + 1) * n * 3);
    const B = this.pos.subarray(hi * n * 3, (hi + 1) * n * 3);
    // the Sun with the SAME (lo, f) as the stars — the pairing invariant.
    // Storage is CYLINDRICAL with UNWRAPPED azimuth (build_sky: Cartesian
    // interpolation chords whole orbits at the far epoch spacing); the
    // reconstruction below makes steady rotation exactly linear per star.
    const sR = this.sunE[lo * 3] * (1 - f) + this.sunE[hi * 3] * f;
    const sPhi = this.sunE[lo * 3 + 1] * (1 - f) + this.sunE[hi * 3 + 1] * f;
    const sz = this.sunE[lo * 3 + 2] * (1 - f) + this.sunE[hi * 3 + 2] * f;
    const sx = sR * Math.cos(sPhi), sy = sR * Math.sin(sPhi);
    const P = this.posAttr.array;
    const MG = this.magAttr.array;
    let visible = 0;
    const cx = camPos.x, cy = camPos.y, cz = camPos.z;
    for (let i = 0; i < n; i++) {
      const j = i * 3;
      // heliocentric position in scene units, f64, then camera-relative:
      // the direction from the CAMERA carries the true parallax
      const Rj = A[j] * (1 - f) + B[j] * f;
      const Pj = A[j + 1] * (1 - f) + B[j + 1] * f;
      const x = (Rj * Math.cos(Pj) - sx) * PC_TO_RSUN - cx;
      const y = (Rj * Math.sin(Pj) - sy) * PC_TO_RSUN - cy;
      const z = ((A[j + 2] * (1 - f) + B[j + 2] * f) - sz) * PC_TO_RSUN - cz;
      const dScene = Math.sqrt(x * x + y * y + z * z);
      const k = R_DRAW / Math.max(dScene, 1e-3);
      P[j] = cx + x * k; P[j + 1] = cy + y * k; P[j + 2] = cz + z * k;
      const dPc = dScene / PC_TO_RSUN;
      // apparent magnitude at this epoch: catalogue magnitude shifted by the
      // changed distance (luminosity FROZEN at the present epoch — declared)
      MG[i] = m.gmag[i] + 5 * Math.log10(Math.max(dPc, 1e-3) / Math.max(this.d0[i], 1e-3));
      if (MG[i] <= magLimit) visible++;
    }
    this.posAttr.needsUpdate = true;
    this.magAttr.needsUpdate = true;
    this.uniforms.uMagLimit.value = magLimit;
    this.uniforms.uRod.value = rod;
    this.visibleCount = visible;
  }
}
