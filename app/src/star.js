// @render-path — the star's photosphere. Every colour uniform entering this
// module comes from the Stage 0 chromaticity table; nothing here invents,
// adapts or white-balances a colour. Numeric constants below are geometry,
// Rec.709 luminance weights and band-limit thresholds — never chromaticities.
//
// The photosphere is a raytraced sphere on a camera-facing quad:
//  - granulation: per-fragment cellular field on the sphere direction, cell
//    angular size = D/R from the track (fork 4: scale derived, texture
//    procedural). One field, one size input, every regime — the derived
//    cell size cannot differ between regimes by construction, and cells
//    below the pixel band-limit fade analytically (no instances, no cull).
//  - limb darkening: Claret 4-parameter I(mu) with per-EEP coefficients.
//  - soft limb: brightness beyond the photospheric radius decays over
//    LIMB_SOFT_SCALE pressure scale heights (H_p/R from the track), so the
//    giant's edge is genuinely fuzzy and the dwarf's is genuinely crisp.
//  - hashes are integer PCG — no sin anywhere in any hash (failure 47).
import * as THREE from "three";

const LIMB_SOFT_SCALE = 5.0;   // e-folding span of the extended photosphere, in H_p
export const CELL_PX_BANDLIMIT = 3.0; // cells narrower than this many pixels fade out

const vert = /* glsl */ `
  varying vec2 vNdc;
  void main() {
    vNdc = position.xy;
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`;

const frag = /* glsl */ `
  precision highp float;
  varying vec2 vNdc;
  uniform vec3 uRgb;          // table chromaticity (linear sRGB direction)
  uniform vec4 uLdA;          // Claret a1..a4
  uniform float uR;           // photospheric radius, scene units
  uniform float uHpR;         // H_p / R
  uniform float uCellAng;     // granule angular size D/R (radians on surface)
  uniform float uExposure;
  uniform float uContrast;    // granulation brightness contrast
  uniform float uCellPx;      // apparent granule size in screen pixels
  uniform vec3 uCamPos;
  uniform mat3 uCamRot;       // camera basis (columns: right, up, -forward)
  uniform float uTanHalfFov;
  uniform float uAspect;
  uniform float uTime;

  // ---- integer hash (PCG3D, Jarzynski & Olano) — sinless by construction
  uvec3 pcg3d(uvec3 v) {
    v = v * 1664525u + 1013904223u;
    v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y;
    v ^= v >> 16u;
    v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y;
    return v;
  }
  vec3 hash3(ivec3 p, uint seed) {
    uvec3 h = pcg3d(uvec3(p) * 3u + seed);
    return vec3(h) * (1.0 / 4294967295.0);
  }

  // ---- cellular (Worley) field on lattice; returns (F1, F2-F1, cellId01)
  vec3 cellular(vec3 q, uint seed) {
    ivec3 base = ivec3(floor(q));
    float f1 = 1e9, f2 = 1e9; float id = 0.0;
    for (int dz = -1; dz <= 1; dz++)
    for (int dy = -1; dy <= 1; dy++)
    for (int dx = -1; dx <= 1; dx++) {
      ivec3 cell = base + ivec3(dx, dy, dz);
      vec3 r = hash3(cell, seed);
      vec3 p = vec3(cell) + r;
      float d = length(p - q);
      if (d < f1) { f2 = f1; f1 = d; id = r.x; }
      else if (d < f2) { f2 = d; }
    }
    return vec3(f1, f2 - f1, id);
  }

  float limbLaw(float mu) {
    float m = max(mu, 0.0);
    // clamped at zero: the spherical fits legitimately droop through zero
    // near the limb (fit undershoot of a profile that reaches zero) and
    // negative intensity is unphysical
    return max(1.0
      - uLdA.x * (1.0 - sqrt(m))
      - uLdA.y * (1.0 - m)
      - uLdA.z * (1.0 - m * sqrt(m))
      - uLdA.w * (1.0 - m * m), 0.0);
  }

  void main() {
    // ray through this fragment
    vec3 dir = normalize(uCamRot * vec3(vNdc.x * uTanHalfFov * uAspect,
                                        vNdc.y * uTanHalfFov, -1.0));
    // sphere at origin, radius uR; soft shell extends a few H_p beyond
    float soft = ${LIMB_SOFT_SCALE.toFixed(1)} * uHpR * uR;
    float rOuter = uR + 4.0 * soft;
    float b = dot(uCamPos, dir);
    float c0 = dot(uCamPos, uCamPos);
    float discOuter = b * b - (c0 - rOuter * rOuter);
    if (discOuter < 0.0) discard;

    float disc = b * b - (c0 - uR * uR);
    vec3 colour;
    float bright;
    float lanePost = 1.0;
    if (disc >= 0.0) {
      float t = -b - sqrt(disc);
      vec3 pos = uCamPos + t * dir;
      vec3 nrm = pos / uR;
      float mu = max(dot(nrm, -dir), 0.0);
      // granulation lattice: |q| moves 1 per radian of surface arc scaled by
      // 1/cellAngle, so limb-to-limb (pi radians) shows pi/cellAngle cells —
      // i.e. cell size D on a star of radius R, exactly as derived
      vec3 q = nrm / max(uCellAng, 1.0e-6);
      // slow domain drift: cells migrate and reform
      float tt = uTime * 0.03;
      vec3 w1 = cellular(q + vec3(0.0, 0.0, tt), 7u);
      vec3 w2 = cellular(q * 2.03 + vec3(tt, 0.0, 0.0), 13u);
      // thick-bodied stroke per cell: hot upwelling core falling toward a
      // genuinely dark intergranular lane. Lane WIDTH varies per region
      // (second-octave field), per-cell brightness jitters from the cell id
      // so no two strokes match, and the painterly modulation rides
      // POST-tone so seven decades of exposure cannot iron it flat.
      // analytic band-limit: fade cell contrast as cells shrink below
      // pixels (uCellPx = apparent granule size in screen pixels, computed
      // CPU-side from the same derived D the panel reports)
      float vis = smoothstep(${CELL_PX_BANDLIMIT.toFixed(1)}, ${(CELL_PX_BANDLIMIT * 3).toFixed(1)}, uCellPx);
      float m = vis * uContrast;
      float laneW = 0.30 * (0.55 + 0.9 * w2.x);
      float lane = smoothstep(0.0, laneW, w1.y);
      float core = 1.0 - smoothstep(0.0, 0.75, w1.x + 0.35 * w2.x);
      float fine = 1.0 - smoothstep(0.05, 0.45, w2.y);
      float jitter = 0.88 + 0.24 * w1.z;
      float gran = mix(1.0, (1.0 + 0.35 * core) * jitter * (1.0 - 0.10 * fine), m);
      lanePost = mix(1.0, mix(0.40, 1.0, lane), m)
               * (1.0 + 0.22 * core * m)
               * (1.0 - 0.07 * fine * m)
               * (1.0 + 0.12 * (w1.z - 0.5) * m);
      bright = limbLaw(mu) * gran;
      colour = uRgb;
    } else {
      // the fuzzy limb: emission beyond the photospheric radius decays over
      // ~LIMB_SOFT_SCALE * H_p; its strength follows the near-limb intensity
      float dmin = sqrt(max(c0 - b * b, 0.0)); // closest approach to centre
      float h = dmin - uR;
      bright = 0.6 * limbLaw(0.06) * exp(-h / max(soft, 1.0e-9));
      colour = uRgb;
    }
    vec3 lin = colour * bright * uExposure;
    // tone: Reinhard on luminance only — chromaticity is never clipped
    float y = dot(lin, vec3(0.2126, 0.7152, 0.0722));
    float yT = y / (1.0 + y);
    lin *= (y > 0.0) ? yT / y : 1.0;
    // intergranular lanes ride post-tone so they survive high exposure
    lin *= lanePost;
    // ~1 LSB dither (integer hash) so the deep fades never band
    float dth = (float(pcg3d(uvec3(uvec2(gl_FragCoord.xy), 7u)).x)
                 * (1.0 / 4294967295.0) - 0.5) / 255.0;
    lin = max(lin + vec3(dth), 0.0);
    // sRGB encode
    vec3 enc = mix(lin * 12.92, 1.055 * pow(lin, vec3(1.0 / 2.4)) - 0.055,
                   step(0.0031308, lin));
    gl_FragColor = vec4(enc, 1.0);
  }
`;

export class Star {
  constructor(scene) {
    this.uniforms = {
      uRgb: { value: new THREE.Vector3(1, 1, 1) },
      uLdA: { value: new THREE.Vector4(0, 0, 0, 0) },
      uR: { value: 1 },
      uHpR: { value: 1e-4 },
      uCellAng: { value: 1e-3 },
      uExposure: { value: 1 },
      uContrast: { value: 1 },
      uCellPx: { value: 10 },
      uCamPos: { value: new THREE.Vector3(0, 0, 4) },
      uCamRot: { value: new THREE.Matrix3() },
      uTanHalfFov: { value: Math.tan(0.5 * 40 * Math.PI / 180) },
      uAspect: { value: 1 },
      uTime: { value: 0 },
    };
    const mat = new THREE.ShaderMaterial({
      vertexShader: vert, fragmentShader: frag, uniforms: this.uniforms,
    });
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat);
    this.mesh.frustumCulled = false;
    scene.add(this.mesh);
  }

  // state: everything below arrives from the Stage 0 tables via main.js
  apply(state) {
    const u = this.uniforms;
    u.uRgb.value.fromArray(state.rgbLin);
    u.uLdA.value.fromArray(state.ldA);
    u.uR.value = state.rRsun;
    u.uHpR.value = state.hpOverR;
    u.uCellAng.value = state.cellAngle;
    u.uExposure.value = state.exposure;
    u.uContrast.value = state.contrast;
  }

  frame(camera, sizePx, time) {
    const u = this.uniforms;
    u.uCamPos.value.copy(camera.position);
    u.uCamRot.value.setFromMatrix4(camera.matrixWorld);
    u.uTanHalfFov.value = Math.tan(0.5 * camera.fov * Math.PI / 180);
    u.uAspect.value = camera.aspect;
    u.uTime.value = time;
    // apparent granule size in pixels: same derived D the panel reports
    const dist = camera.position.length();
    const pxPerRad = sizePx.y / (camera.fov * Math.PI / 180);
    const apparent = (u.uCellAng.value * u.uR.value) / Math.max(dist - u.uR.value, 1e-9);
    u.uCellPx.value = apparent * pxPerRad;
    return u.uCellPx.value;
  }
}
