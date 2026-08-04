// Orchestration: tables -> state at slider position -> star + HR + panel.
// Deep-link URL parameters (?wp=, ?s=, ?cam_d=, ?cam_az=, ?cam_alt=, ?tier=)
// are shipped functionality: they let a moment of the star's life be linked,
// and they are how the harness states its assumptions explicitly (fork 12).
import * as THREE from "three";
import { loadTables, colAt, rowAt, eepOfS, phaseName, formatAge, Unavailable } from "./data.js";
import { Star, CELL_PX_BANDLIMIT } from "./star.js";
import { Void } from "./void.js";
import { HrDiagram } from "./hr.js";
import { Panel } from "./panel.js";
import { TwoCurves } from "./curves.js";
import { NebulaShell } from "./nebula.js";
import { Eye } from "./eye.js";
import { SkyField } from "./skyfield.js";
import { MilkyWay } from "./band.js";

const RSUN_M = 6.957e8;

async function boot() {
  const params = new URLSearchParams(location.search);
  const tier = params.get("tier") ?? "high";
  const dprClamp = tier === "low" ? 1 : 2;

  const { track, colour } = await loadTables();
  // earth table: absence is a visible refusal, never a substitute
  let earth = null;
  try {
    const r = await fetch("./data/earth.json");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    earth = await r.json();
  } catch (e) {
    console.error(`unavailable: earth table — ${e.message}`);
  }
  let nebulaTab = null;
  try {
    const r = await fetch("./data/nebula.json");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    nebulaTab = await r.json();
  } catch (e) {
    console.error(`unavailable: nebula table — ${e.message}`);
  }
  // the sky: catalogue tables + orbit positions; absence is visible refusal
  let skyMeta = null, skyPos = null, sunOrbit = null, bandTex = null;
  try {
    const [rm, rp, rs, rb] = await Promise.all([
      fetch("./data/sky.json"), fetch("./data/sky_positions.bin"),
      fetch("./data/sun_orbit.bin"), fetch("./data/band_tex.bin")]);
    if (!rm.ok || !rp.ok || !rs.ok || !rb.ok) throw new Error("HTTP failure");
    skyMeta = await rm.json();
    skyPos = new Float32Array(await rp.arrayBuffer());
    sunOrbit = new Float32Array(await rs.arrayBuffer());
    bandTex = new Float32Array(await rb.arrayBuffer());
  } catch (e) {
    console.error(`unavailable: sky tables — ${e.message}`);
  }

  // --- scene
  const holder = document.getElementById("scene");
  const renderer = new THREE.WebGLRenderer({ antialias: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, dprClamp));
  holder.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.01, 1e9);
  const star = new Star(scene);
  const voidBg = new Void(scene);
  const shell = new NebulaShell(scene);
  const eye = new Eye();
  // the Sun's position at EXACTLY the present epoch (interpolated between
  // spine nodes — the nearest row is 11.7 Myr off, ~2.6 kpc of orbit, and
  // pairing present stars with that Sun inflates every distance)
  const ages = track.age_yr;
  let sunPresent = null;
  if (sunOrbit && skyMeta) {
    const tP = skyMeta.present_age_yr;
    let k = 0;
    while (k < ages.length - 2 && ages[k + 1] < tP) k++;
    const f = Math.max(0, Math.min(1, (tP - ages[k]) / Math.max(ages[k + 1] - ages[k], 1e-9)));
    sunPresent = [0, 1, 2].map((c) => sunOrbit[k * 3 + c] * (1 - f) + sunOrbit[(k + 1) * 3 + c] * f);
  }
  const skyField = skyMeta ? new SkyField(scene, skyMeta, skyPos, sunOrbit, sunPresent) : null;
  const milkyWay = bandTex ? new MilkyWay(scene, bandTex) : null;
  let eyeJump = true; // initial load is a cut: arrive adapted (fork 28)

  // --- instruments
  const hr = new HrDiagram(document.getElementById("hr"), track, colour);
  const panel = new Panel(document.getElementById("panel"));
  const curves = new TwoCurves(document.getElementById("curves"), earth);
  const ageBig = document.getElementById("age-big");
  const ageSub = document.getElementById("age-sub");
  const ageNote = document.getElementById("age-note");
  let dragOn = true;

  // --- control state
  const cam = {
    d: parseFloat(params.get("cam_d") ?? "4"),
    az: (parseFloat(params.get("cam_az") ?? "0") * Math.PI) / 180,
    alt: (parseFloat(params.get("cam_alt") ?? "0") * Math.PI) / 180,
    vAz: 0, vAlt: 0,
  };
  let s = 0;
  const wp = params.get("wp");
  if (wp && track.events_s[wp] !== undefined) s = track.events_s[wp];
  if (params.get("s") !== null) s = parseFloat(params.get("s"));

  const slider = document.getElementById("timeline");
  slider.value = String(s);
  slider.addEventListener("input", () => { s = parseFloat(slider.value); });

  const wpBox = document.getElementById("waypoints");
  for (const [name, sv] of Object.entries(track.events_s)) {
    const b = document.createElement("button");
    b.textContent = name.replaceAll("_", " ");
    b.addEventListener("click", () => { s = sv; slider.value = String(sv); eyeJump = true; });
    wpBox.appendChild(b);
  }
  const tog = document.createElement("button");
  tog.id = "dragtoggle";
  tog.textContent = "drag physics: on";
  tog.addEventListener("click", () => {
    dragOn = !dragOn;
    tog.textContent = `drag physics: ${dragOn ? "on" : "off"}`;
  });
  wpBox.appendChild(tog);

  // camera drag with inertial drift; wheel = framing distance
  let dragging = false, lastX = 0, lastY = 0;
  holder.addEventListener("pointerdown", (e) => { dragging = true; lastX = e.clientX; lastY = e.clientY; });
  window.addEventListener("pointerup", () => { dragging = false; });
  window.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    cam.vAz = (e.clientX - lastX) * 0.004;
    cam.vAlt = (e.clientY - lastY) * 0.004;
    lastX = e.clientX; lastY = e.clientY;
  });
  holder.addEventListener("wheel", (e) => {
    e.preventDefault();
    cam.d = Math.min(Math.max(cam.d * Math.exp(e.deltaY * 0.001), 1.15), 60);
  }, { passive: false });

  function resize() {
    const w = holder.clientWidth, h = holder.clientHeight;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);
  resize();

  let announcedReady = false;
  let lastT = null;
  const frameTimes = [];
  function frame(tMs) {
    if (lastT !== null) {
      frameTimes.push(tMs - lastT);
      if (frameTimes.length > 120) frameTimes.shift();
    }
    const time = tMs / 1000;
    // state at slider position — everything from the tables
    const eep = eepOfS(track, s);
    const i = rowAt(track, eep);
    const teff = Math.pow(10, colAt(track, "log_Teff", eep));
    const logL = colAt(track, "log_L", eep);
    const rR = Math.pow(10, colAt(track, "log_R", eep));
    const logg = colAt(track, "log_g", eep);
    const crow = colour.rows[i];
    const hpR = track.granule_hp_m[i] / (rR * RSUN_M);
    const cellAngle = track.granule_d_m[i] / (rR * RSUN_M);

    // camera: inertial drift, framed distance in current radii
    cam.az += cam.vAz; cam.alt += cam.vAlt;
    cam.vAz *= 0.94; cam.vAlt *= 0.94;
    cam.alt = Math.min(Math.max(cam.alt, -1.45), 1.45);
    const dist = cam.d * rR;
    camera.position.set(
      dist * Math.cos(cam.alt) * Math.sin(cam.az),
      dist * Math.sin(cam.alt),
      dist * Math.cos(cam.alt) * Math.cos(cam.az));
    camera.lookAt(0, 0, 0);
    camera.updateMatrixWorld();

    // tone (fork 20, presentational until the eye model): Stevens-compressed
    // bolometric luminance; Reinhard-on-luminance in-shader never clips hue
    const exposure = Math.pow(Math.pow(10, logL), 0.25);

    // granulation contrast is gated by the convective regime (fork 24):
    // surface convection dies above ~8-10 kK (the observed granulation
    // boundary) — post-AGB sprint and hot white dwarfs are radiative
    const convective = Math.max(0, Math.min(1, (10000 - teff) / 2000));
    star.apply({
      rgbLin: crow.rgb_lin,
      ldA: track.ld_a[i],
      rRsun: rR,
      hpOverR: hpR,
      cellAngle,
      exposure,
      contrast: convective,
    });
    const cellPx = star.frame(camera, { x: holder.clientWidth, y: holder.clientHeight }, time);
    voidBg.frame(time);
    // the nebula: nearest solved step at this s (transient — outside its
    // ten-thousand-year window the interpolation reads nothing)
    let nstep = null;
    if (nebulaTab) {
      const steps = nebulaTab.steps;
      if (s >= steps[0].s && s <= steps[steps.length - 1].s) {
        let lo = 0, hi = steps.length - 1;
        while (hi - lo > 1) { const m = (lo + hi) >> 1; if (steps[m].s <= s) lo = m; else hi = m; }
        nstep = steps[lo];
      }
    }
    shell.apply(nstep, rR);
    shell.frame(camera);
    const ageYr = colAt(track, "age_yr", eep);
    // the eye: field luminance from the star's tone-domain brightness times
    // the fraction of the view its disc fills — the same numbers the panel
    // shows; sky visibility is computed, never chosen
    const yStar = Math.min(exposure / (1 + exposure), 1);
    const diskFrac = Math.min(1, Math.pow(rR / Math.max(dist - rR, 1e-9), 2)
      / Math.pow(Math.tan(0.5 * camera.fov * Math.PI / 180), 2));
    const dtS = Math.min((tMs - (lastT ?? tMs)) / 1000, 0.1);
    lastT = tMs;
    const fieldLum = yStar * diskFrac + (nstep ? 0.02 : 0);
    if (eyeJump) { eye.jumpTo(fieldLum); eyeJump = false; }
    const adaptation = eye.step(fieldLum, dtS);
    const magLimit = eye.magLimit();
    const rod = eye.rodFraction();
    if (skyField) skyField.update(ageYr, i, magLimit, rod);
    // the chrome yields to the dark: at deep adaptation the instrument ink
    // dims so the interface cannot outshine the sky it reports on
    const uiDim = 0.45 + 0.55 * Math.min(adaptation / 0.2, 1);
    document.getElementById("agepane").style.opacity = String(uiDim);
    document.getElementById("controls").style.opacity = String(Math.max(uiDim, 0.6));
    if (milkyWay && sunOrbit) {
      const az = Math.atan2(sunOrbit[i * 3 + 1], sunOrbit[i * 3]) - Math.atan2(0, -1);
      milkyWay.update(adaptation, rod, az);
    }
    renderer.render(scene, camera);

    // derived vs rendered counts: the panel reports both, honestly
    const granDerived = track.granule_n_disk[i];
    const diskPx = 2 * rR / Math.max(dist - rR, 1e-9) * (holder.clientHeight / (camera.fov * Math.PI / 180));
    const resolvable = (Math.PI / 4) * Math.pow(diskPx / CELL_PX_BANDLIMIT, 2);
    const granRendered = cellPx < CELL_PX_BANDLIMIT ? Math.min(granDerived, resolvable) : granDerived;

    const aEarthAu = curves.aAt(s, dragOn);
    const dataState = track.data_state ? track.data_state[i] : "tabulated";
    panel.update({
      s, ageYr,
      phase: phaseName(track.phase[i], teff, dataState),
      teff, logL, rRsun: rR, logg,
      mass: colAt(track, "star_mass", eep),
      rgbLin: crow.rgb_lin,
      excursion: crow.excursion,
      granDerived, granRendered,
      granD: track.granule_d_m[i],
      drawCalls: renderer.info.render.calls,
      ldSource: track.ld_source[i],
      aEarthAu,
      mdot: earth ? (i < earth.mdot_track.length ? earth.mdot_track[i] : 0) : 0,
      mdotSc: earth ? (i < earth.mdot_sc05.length ? earth.mdot_sc05[i] : 0) : 0,
      dragOn,
      dataState,
      crystalFrac: track.crystal_frac ? track.crystal_frac[i] : 0,
      nebula: nstep,
      adaptation,
      skyVisible: skyField ? skyField.visibleCount : -1,
      frameMs: frameTimes.length > 20
        ? [...frameTimes].sort((a, b) => a - b)[Math.floor(frameTimes.length * 0.95)]
        : undefined,
    });
    const [av, au] = formatAge(ageYr);
    ageBig.textContent = `${av} ${au}`;
    ageSub.textContent = phaseName(track.phase[i], teff, dataState);
    // quiet beats, each at its solved crossing — never a frame-boundary guess
    const ev = earth ? (dragOn ? earth.engulf_drag : earth.engulf_nodrag) : null;
    const mk = track.markers ?? {};
    const notes = [];
    if (mk.present_day && Math.abs(s - mk.present_day.s) < 0.0015) notes.push("here — the only frame that exists right now");
    if (ev && s >= ev.s) {
      notes.push(dragOn ? "the Earth is gone — drawn in at the tip of the red giant branch"
                        : "the Earth is gone — overrun on the asymptotic giant branch");
    }
    if (mk.existence && s >= mk.existence.s) {
      notes.push("beyond here the object being rendered exists nowhere, and will not for a very long time");
    }
    ageNote.textContent = notes[notes.length - 1] ?? "";
    hr.draw(eep, cssColour(crow.rgb_lin));
    curves.draw(s, dragOn);

    if (!announcedReady) { panel.ready(); announcedReady = true; }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

// display form of a table chromaticity for the HR marker (sRGB encode of the
// table's linear value — an encoding, not a new colour)
function cssColour(rgbLin) {
  const enc = rgbLin.map((v) =>
    Math.round(255 * (v <= 0.0031308 ? v * 12.92 : 1.055 * Math.pow(v, 1 / 2.4) - 0.055)));
  return `rgb(${enc[0]}, ${enc[1]}, ${enc[2]})`;
}

boot().catch((e) => {
  const el = document.getElementById("err");
  el.style.display = "block";
  el.textContent = e instanceof Unavailable
    ? `${e.message}\n\nThe affected region is not drawn. A blank is information; a substitute would be a lie shaped like data.`
    : `boot failure: ${e.message}`;
  // the harness treats this console line as a hard gate failure
  console.error(String(e));
});
