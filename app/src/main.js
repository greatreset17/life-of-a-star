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

  // --- scene
  const holder = document.getElementById("scene");
  const renderer = new THREE.WebGLRenderer({ antialias: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, dprClamp));
  holder.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.01, 1e9);
  const star = new Star(scene);
  const voidBg = new Void(scene);

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
    b.addEventListener("click", () => { s = sv; slider.value = String(sv); });
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
  function frame(tMs) {
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

    star.apply({
      rgbLin: crow.rgb_lin,
      ldA: track.ld_a[i],
      rRsun: rR,
      hpOverR: hpR,
      cellAngle,
      exposure,
      contrast: 1.0,
    });
    const cellPx = star.frame(camera, { x: holder.clientWidth, y: holder.clientHeight }, time);
    voidBg.frame(time);
    renderer.render(scene, camera);

    // derived vs rendered counts: the panel reports both, honestly
    const granDerived = track.granule_n_disk[i];
    const diskPx = 2 * rR / Math.max(dist - rR, 1e-9) * (holder.clientHeight / (camera.fov * Math.PI / 180));
    const resolvable = (Math.PI / 4) * Math.pow(diskPx / CELL_PX_BANDLIMIT, 2);
    const granRendered = cellPx < CELL_PX_BANDLIMIT ? Math.min(granDerived, resolvable) : granDerived;

    const ageYr = colAt(track, "age_yr", eep);
    const aEarthAu = curves.aAt(s, dragOn);
    panel.update({
      s, ageYr,
      phase: phaseName(track.phase[i], teff),
      teff, logL, rRsun: rR, logg,
      mass: colAt(track, "star_mass", eep),
      rgbLin: crow.rgb_lin,
      excursion: crow.excursion,
      granDerived, granRendered,
      granD: track.granule_d_m[i],
      drawCalls: renderer.info.render.calls,
      ldSource: track.ld_source[i],
      aEarthAu,
      mdot: earth ? earth.mdot_track[i] : 0,
      mdotSc: earth ? earth.mdot_sc05[i] : 0,
      dragOn,
      dataState: "tabulated",
    });
    const [av, au] = formatAge(ageYr);
    ageBig.textContent = `${av} ${au}`;
    ageSub.textContent = phaseName(track.phase[i], teff);
    // the ending, announced quietly at the solved crossing — the event's s
    // is the integrator's interpolated value, not a frame boundary
    const ev = earth ? (dragOn ? earth.engulf_drag : earth.engulf_nodrag) : null;
    ageNote.textContent = ev && s >= ev.s
      ? (dragOn ? "the Earth is gone — drawn in at the tip of the red giant branch"
                : "the Earth is gone — overrun on the asymptotic giant branch")
      : "";
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
