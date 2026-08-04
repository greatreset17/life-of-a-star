// @render-path — the sky as seen. Stars sit at their catalogued 3D
// positions (scene units = Rsun), so camera translation produces real
// parallax; colours are the table's chain-derived chromaticities; there is
// no lens, so there is no flare, no bloom, no twinkle. Visibility passes
// through the eye: each point is entirely present or entirely absent
// (whole-instance culling, failure state 43), rod vision drains colour to
// achromatic luminance via per-star scotopic weights.
import * as THREE from "three";

const PC_TO_RSUN = 3.0856775814913673e16 / 6.957e8;

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
    float lum = pow(10.0, -0.4 * (vMag - uMagLimit)) ;
    lum = min(lum, 1.0);
    vec3 cone = vRgb * lum;
    vec3 rod = vec3(lum * vScot * 0.8);
    vec3 lin = mix(cone, rod, uRod);
    // soft round point
    vec2 d = gl_PointCoord - vec2(0.5);
    float fall = smoothstep(0.5, 0.15, length(d));
    lin *= fall;
    vec3 enc = mix(lin * 12.92, 1.055 * pow(lin, vec3(1.0 / 2.4)) - 0.055,
                   step(0.0031308, lin));
    gl_FragColor = vec4(enc, lum * fall);
  }
`;

export class SkyField {
  constructor(scene, skyMeta, positionsF32, sunOrbitF32, sunPresent) {
    this.meta = skyMeta;
    this.pos = positionsF32;   // [n_epoch][n_star][3] galactocentric pc
    this.sun = sunOrbitF32;    // [n_spine][3]
    const n = skyMeta.n_star;
    // present-epoch distances: star(epoch nearest 0) against the Sun AT THE
    // PRESENT EPOCH exactly (interpolated; a nearest-node Sun is megayears
    // — kiloparsecs — off, and pairing present stars with a displaced Sun
    // turns shared orbital motion into phantom magnitude changes; measured
    // twice before it stayed fixed)
    {
      const eps = skyMeta.epochs_myr;
      const k0 = eps.reduce((b, v, idx) => Math.abs(v) < Math.abs(eps[b]) ? idx : b, 0);
      const Z = positionsF32.subarray(k0 * n * 3, (k0 + 1) * n * 3);
      const [sx, sy, sz] = sunPresent;
      this.d0 = new Float32Array(n);
      for (let i = 0; i < n; i++) {
        const j = i * 3;
        this.d0[i] = Math.hypot(Z[j] - sx, Z[j + 1] - sy, Z[j + 2] - sz);
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

  // ageYr: current stellar age; spineIndex: current spine node for the
  // Sun's position; magLimit/rod from the eye
  update(ageYr, spineIndex, magLimit, rod) {
    const m = this.meta;
    const tMyr = (ageYr - m.present_age_yr) / 1e6;
    const eps = m.epochs_myr;
    let lo = 0, hi = eps.length - 1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (eps[mid] <= tMyr) lo = mid; else hi = mid; }
    const f = Math.max(0, Math.min(1, (tMyr - eps[lo]) / Math.max(eps[hi] - eps[lo], 1e-9)));
    const n = m.n_star;
    const A = this.pos.subarray(lo * n * 3, (lo + 1) * n * 3);
    const B = this.pos.subarray(hi * n * 3, (hi + 1) * n * 3);
    const sx = this.sun[spineIndex * 3], sy = this.sun[spineIndex * 3 + 1], sz = this.sun[spineIndex * 3 + 2];
    const P = this.posAttr.array;
    const MG = this.magAttr.array;
    let visible = 0;
    for (let i = 0; i < n; i++) {
      const j = i * 3;
      const x = (A[j] * (1 - f) + B[j] * f) - sx;
      const y = (A[j + 1] * (1 - f) + B[j + 1] * f) - sy;
      const z = (A[j + 2] * (1 - f) + B[j + 2] * f) - sz;
      const dPc = Math.sqrt(x * x + y * y + z * z);
      P[j] = x * PC_TO_RSUN; P[j + 1] = y * PC_TO_RSUN; P[j + 2] = z * PC_TO_RSUN;
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
