// @render-path — the planetary nebula shell. Colour arrives ONLY from the
// Stage 0 nebula table (line-emission spectrum through the shared CIE
// chain); geometry is the solved thin shell. Emission is proportional to
// the chord length through the shell — which is the physical reason
// planetary nebulae read as rings — and the whole thing stays honestly
// faint: the published images are long exposures, and this is an eye.
import * as THREE from "three";

const frag = /* glsl */ `
  precision highp float;
  varying vec2 vNdc;
  uniform vec3 uRgb;         // nebula table chromaticity (linear)
  uniform float uRIn;        // shell inner radius, scene units
  uniform float uROut;       // shell outer radius
  uniform float uRStar;      // occluding stellar radius
  uniform float uBright;
  uniform vec3 uCamPos;
  uniform mat3 uCamRot;
  uniform float uTanHalfFov;
  uniform float uAspect;

  // chord of the ray [t in (t0,t1)] through the sphere of radius r; returns
  // (tNear, tFar) or (0,0)
  vec2 sphereChord(vec3 ro, vec3 rd, float r) {
    float b = dot(ro, rd);
    float d = b * b - (dot(ro, ro) - r * r);
    if (d < 0.0) return vec2(0.0);
    float s = sqrt(d);
    return vec2(-b - s, -b + s);
  }

  void main() {
    if (uROut <= 0.0 || uBright <= 0.0) discard;
    vec3 rd = normalize(uCamRot * vec3(vNdc.x * uTanHalfFov * uAspect,
                                       vNdc.y * uTanHalfFov, -1.0));
    vec2 outer = sphereChord(uCamPos, rd, uROut);
    if (outer.y <= 0.0) discard;
    vec2 inner = sphereChord(uCamPos, rd, uRIn);
    // chord through the shell = outer chord minus inner chord
    float chord = max(outer.y - max(outer.x, 0.0), 0.0)
                - max(inner.y - max(inner.x, 0.0), 0.0);
    // occlusion: the star blocks the far half behind it
    vec2 star = sphereChord(uCamPos, rd, uRStar);
    if (star.x > 0.0) {
      chord -= max(outer.y - star.x, 0.0) - max(inner.y - star.x, 0.0);
    }
    if (chord <= 0.0) discard;
    float thick = uROut - uRIn;
    // declared asphericity (fork 5 amendment): the superwind is denser at
    // the equator by the DECLARED contrast C — the brief's own preferred
    // upgrade over pure sphericity. Emission goes as density squared, so
    // the ring-waist appears from inside and outside alike. The axis is
    // the system's orbital axis (scene z); C is a parameter, not a shape.
    const float C_EQ = 3.0;
    float s2 = 1.0 - rd.z * rd.z;
    float dens = (1.0 + C_EQ * s2) / (1.0 + C_EQ * 0.6667);
    float e = uBright * (chord / max(thick, 1e-9)) * dens * dens;
    vec3 lin = uRgb * e;
    float y = dot(lin, vec3(0.2126, 0.7152, 0.0722));
    float yT = y / (1.0 + y);
    lin *= (y > 0.0) ? yT / y : 1.0;
    vec3 enc = mix(lin * 12.92, 1.055 * pow(lin, vec3(1.0 / 2.4)) - 0.055,
                   step(0.0031308, lin));
    gl_FragColor = vec4(enc, 1.0);
  }
`;

export class NebulaShell {
  constructor(scene) {
    this.uniforms = {
      uRgb: { value: new THREE.Vector3(0, 0, 0) },
      uRIn: { value: 0 }, uROut: { value: 0 }, uRStar: { value: 1 },
      uBright: { value: 0 },
      uCamPos: { value: new THREE.Vector3() },
      uCamRot: { value: new THREE.Matrix3() },
      uTanHalfFov: { value: 0.36 }, uAspect: { value: 1 },
    };
    const mat = new THREE.ShaderMaterial({
      vertexShader: /* glsl */ `
        varying vec2 vNdc;
        void main() { vNdc = position.xy; gl_Position = vec4(position.xy, 0.5, 1.0); }`,
      fragmentShader: frag,
      uniforms: this.uniforms,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat);
    mesh.frustumCulled = false;
    mesh.renderOrder = 2;
    scene.add(mesh);
  }

  // step: an entry of nebula.json interpolated at s (or null when no nebula)
  apply(step, rStarScene) {
    const u = this.uniforms;
    if (!step || step.l_lines_w <= 0) {
      u.uBright.value = 0;
      return;
    }
    const rOut = step.r_s_au * 1.495978707e11 / 6.957e8; // AU -> Rsun scene units
    u.uROut.value = rOut;
    u.uRIn.value = rOut * 0.9;
    u.uRStar.value = rStarScene;
    u.uRgb.value.fromArray(step.rgb_lin);
    // honest faintness: the shell's physical surface brightness relative to
    // the solar photosphere is ~1e-17 — invisible beside any stellar disk.
    // Until the v0.4 eye model (adaptation) takes over, the same
    // compressive tone family the star uses is applied with a declared
    // exponent (presentation, fork 25): (Σ/Σ☉)^0.1 keeps the veil faint,
    // brief, and far below the saturation of the published long exposures.
    const SIGMA_SUN = 3.828e26 / (4 * Math.PI * 6.957e8 * 6.957e8);
    const sb = step.l_lines_w / (4 * Math.PI * Math.pow(step.r_s_au * 1.495978707e11, 2));
    u.uBright.value = 0.6 * Math.pow(sb / SIGMA_SUN, 0.1);
  }

  frame(camera) {
    const u = this.uniforms;
    u.uCamPos.value.copy(camera.position);
    u.uCamRot.value.setFromMatrix4(camera.matrixWorld);
    u.uTanHalfFov.value = Math.tan(0.5 * camera.fov * Math.PI / 180);
    u.uAspect.value = camera.aspect;
  }
}
