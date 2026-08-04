// @render-path — the Milky Way band: the catalogue's own unresolved
// integrated light (healpix aggregate of 6.5 < G < 12) baked to an
// equirectangular data texture in Stage 0. The dark rifts are the real
// dust already imprinted in the observed fluxes — nothing painted; colours
// come through the same chain as every star. Frozen in shape (existence
// frozen at the present epoch), rigidly re-azimuthed with the solar orbit
// (fork 27); visible only to the dark-adapted eye, colourless first.
import * as THREE from "three";

const R_FAR = 4.0e9; // scene units (Rsun)

const frag = /* glsl */ `
  precision highp float;
  varying vec2 vUv;
  uniform sampler2D uMap;   // rgb = chain colour * lum, a = scotopic lum
  uniform float uGain;
  uniform float uRod;
  void main() {
    vec4 t = texture2D(uMap, vUv);
    float g = uGain * 0.8;
    vec3 lin = mix(t.rgb * g, vec3(t.a * g), uRod);
    vec3 enc = mix(lin * 12.92, 1.055 * pow(lin, vec3(1.0 / 2.4)) - 0.055,
                   step(0.0031308, lin));
    gl_FragColor = vec4(enc, clamp(g * 3.0 * max(max(t.r, t.g), t.b), 0.0, 0.9));
  }
`;

export class MilkyWay {
  constructor(scene, texF32, width = 512, height = 256) {
    const tex = new THREE.DataTexture(texF32, width, height, THREE.RGBAFormat, THREE.FloatType);
    tex.magFilter = THREE.LinearFilter;
    tex.minFilter = THREE.LinearFilter;
    tex.wrapS = THREE.RepeatWrapping;
    tex.needsUpdate = true;
    this.uniforms = { uMap: { value: tex }, uGain: { value: 0 }, uRod: { value: 0 } };
    const mat = new THREE.ShaderMaterial({
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        void main() {
          // equirect uv from the GALACTIC-frame direction
          vec3 d = normalize(position);
          vUv = vec2(atan(d.y, d.x) / 6.2831853 + 0.5, asin(clamp(d.z, -1.0, 1.0)) / 3.14159265 + 0.5);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: frag,
      uniforms: this.uniforms,
      side: THREE.BackSide,
      transparent: true,
      depthWrite: false,
    });
    this.mesh = new THREE.Mesh(new THREE.SphereGeometry(R_FAR, 48, 32), mat);
    this.mesh.renderOrder = 0;
    this.mesh.frustumCulled = false;
    scene.add(this.mesh);
  }

  update(adaptation, rod, sunAzimuthRad) {
    this.uniforms.uGain.value = Math.max(0, (0.12 - adaptation) / 0.12);
    this.uniforms.uRod.value = rod;
    this.mesh.rotation.z = sunAzimuthRad;
  }
}
