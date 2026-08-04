// The void — never empty black. A faint achromatic depth: large-scale
// gradient plus integer-hash grain, the way darkness has depth in an oil
// painting. Deliberately ACHROMATIC (declared presentation, fork 20): no
// chromaticity is invented here; the sky's real light arrives with the
// Gaia pass. Hashes are integer — no sin (failure 47).
import * as THREE from "three";

const frag = /* glsl */ `
  precision highp float;
  varying vec2 vNdc;
  uniform float uTime;
  uniform float uLevel;

  uvec3 pcg3d(uvec3 v) {
    v = v * 1664525u + 1013904223u;
    v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y;
    v ^= v >> 16u;
    v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y;
    return v;
  }
  float vnoise(vec2 p, uint seed) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = float(pcg3d(uvec3(ivec3(ivec2(i), 0)) * 3u + seed).x) / 4294967295.0;
    float b = float(pcg3d(uvec3(ivec3(ivec2(i) + ivec2(1, 0), 0)) * 3u + seed).x) / 4294967295.0;
    float c = float(pcg3d(uvec3(ivec3(ivec2(i) + ivec2(0, 1), 0)) * 3u + seed).x) / 4294967295.0;
    float d = float(pcg3d(uvec3(ivec3(ivec2(i) + ivec2(1, 1), 0)) * 3u + seed).x) / 4294967295.0;
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
  }

  void main() {
    float depth = vnoise(vNdc * 0.9 + vec2(0.0, uTime * 0.004), 31u) * 0.55
                + vnoise(vNdc * 2.3, 11u) * 0.30 + vnoise(vNdc * 7.1, 23u) * 0.15;
    float vign = 1.0 - 0.35 * dot(vNdc, vNdc);
    float g = uLevel * (0.55 + 0.45 * depth) * vign;
    gl_FragColor = vec4(vec3(g), 1.0);
  }
`;

export class Void {
  constructor(scene) {
    this.uniforms = { uTime: { value: 0 }, uLevel: { value: 0.012 } };
    const mat = new THREE.ShaderMaterial({
      vertexShader: /* glsl */ `
        varying vec2 vNdc;
        void main() { vNdc = position.xy; gl_Position = vec4(position.xy, 0.999, 1.0); }`,
      fragmentShader: frag,
      uniforms: this.uniforms,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat);
    mesh.frustumCulled = false;
    mesh.renderOrder = -1;
    scene.add(mesh);
  }

  frame(time) {
    this.uniforms.uTime.value = time;
  }
}
