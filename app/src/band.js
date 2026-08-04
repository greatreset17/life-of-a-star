// @render-path — the Milky Way band: the catalogue's own unresolved
// integrated light (healpix aggregate of 6.5 < G < 12), whose dark rifts
// are the real dust imprinted in the observed fluxes — nothing painted.
// Colours per cell come through the same chain as every star. The band is
// frozen in shape (existence frozen at the present epoch — the declared
// boundary) and rigidly re-azimuthed as the Sun rounds the galaxy
// (fork 27). It appears only to the dark-adapted eye, colourless first —
// the vastness arrives at the end.
import * as THREE from "three";

const R_FAR = 4.0e9; // scene units (Rsun); direction-only geometry

const vert = /* glsl */ `
  attribute vec3 rgb;
  attribute float lum;
  attribute float scot;
  varying vec3 vRgb;
  varying float vLum;
  varying float vScot;
  uniform float uAz;
  void main() {
    vRgb = rgb; vLum = lum; vScot = scot;
    float c = cos(uAz), s = sin(uAz);
    vec3 p = vec3(c * position.x - s * position.y,
                  s * position.x + c * position.y, position.z);
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = 26.0;
  }
`;

const frag = /* glsl */ `
  precision highp float;
  varying vec3 vRgb;
  varying float vLum;
  varying float vScot;
  uniform float uGain;   // eye-driven: zero unless dark-adapted
  uniform float uRod;
  void main() {
    vec2 d = gl_PointCoord - vec2(0.5);
    float fall = smoothstep(0.5, 0.0, length(d));
    float lum = vLum * uGain * fall;
    vec3 lin = mix(vRgb * lum, vec3(lum * vScot), uRod);
    vec3 enc = mix(lin * 12.92, 1.055 * pow(lin, vec3(1.0 / 2.4)) - 0.055,
                   step(0.0031308, lin));
    gl_FragColor = vec4(enc, min(lum * 3.0, 0.85));
  }
`;

export class MilkyWay {
  constructor(scene, band) {
    const n = band.cells.length;
    const pos = new Float32Array(n * 3);
    const rgb = new Float32Array(n * 3);
    const lum = new Float32Array(n);
    const scot = new Float32Array(n);
    let fmax = 0;
    for (const c of band.cells) fmax = Math.max(fmax, c.gflux);
    band.cells.forEach((c, i) => {
      pos.set(c.dir.map((v) => v * R_FAR), i * 3);
      rgb.set(c.rgb, i * 3);
      lum[i] = Math.pow(c.gflux / fmax, 0.5) * 0.35;
      scot[i] = c.scot;
    });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("rgb", new THREE.BufferAttribute(rgb, 3));
    geo.setAttribute("lum", new THREE.BufferAttribute(lum, 1));
    geo.setAttribute("scot", new THREE.BufferAttribute(scot, 1));
    this.uniforms = { uGain: { value: 0 }, uRod: { value: 0 }, uAz: { value: 0 } };
    const mat = new THREE.ShaderMaterial({
      vertexShader: vert, fragmentShader: frag, uniforms: this.uniforms,
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const pts = new THREE.Points(geo, mat);
    pts.frustumCulled = false;
    pts.renderOrder = 0;
    scene.add(pts);
  }

  update(adaptation, rod, sunAzimuthRad) {
    // the galaxy is invisible until the eye is deeply dark-adapted
    this.uniforms.uGain.value = Math.max(0, (0.12 - adaptation) / 0.12);
    this.uniforms.uRod.value = rod;
    this.uniforms.uAz.value = sunAzimuthRad;
  }
}
