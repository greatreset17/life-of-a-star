#!/usr/bin/env node
// Tier 2 — the visual gate.
//
// Headless capture at the named waypoints of assumptions.json, at fixed
// viewport, camera and quality tier, so successive builds differ only where
// the code differs. A screenshot alone is not a gate: every capture is
// accompanied by a state probe read from the live application at the same
// instant, and a capture whose probe is missing or incomplete is a gate
// failure — the screenshot is not even written in that case (structural
// enforcement of suite test 48).
//
// The probe READS. It reads the instrument panel's [data-q] elements — the
// panel is shipped functionality, displaying exactly the quantities the probe
// needs; there is no test hook in the shipping source and no verification
// path writes to physical state. Waypoints and camera arrive via the app's
// public deep-link URL parameters, so harness assumptions are passed
// explicitly on every run rather than relying on application defaults.
//
// usage: node gate.mjs <appdir> <label>
import { createServer } from "node:http";
import { readFileSync, writeFileSync, mkdirSync, existsSync, statSync } from "node:fs";
import { join, resolve, dirname, extname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const HERE = dirname(fileURLToPath(import.meta.url));
const A = JSON.parse(readFileSync(join(HERE, "assumptions.json"), "utf8"));

const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
  ".json": "application/json", ".css": "text/css", ".png": "image/png",
  ".bin": "application/octet-stream", ".csv": "text/plain", ".glsl": "text/plain" };

function serve(root) {
  return new Promise((res) => {
    const srv = createServer((req, rsp) => {
      const p = join(root, decodeURIComponent(new URL(req.url, "http://x").pathname).replace(/\/$/, "/index.html"));
      try {
        if (!resolve(p).startsWith(resolve(root)) || !statSync(p).isFile()) throw new Error();
        rsp.writeHead(200, { "content-type": MIME[extname(p)] ?? "application/octet-stream" });
        rsp.end(readFileSync(p));
      } catch { rsp.writeHead(404); rsp.end(); }
    });
    srv.listen(0, "127.0.0.1", () => res(srv));
  });
}

const [appdir, label] = process.argv.slice(2);
if (!appdir || !label) { console.error("usage: gate.mjs <appdir> <label>"); process.exit(2); }
const outdir = join(HERE, "captures", label);
mkdirSync(outdir, { recursive: true });

const srv = await serve(resolve(appdir));
const port = srv.address().port;
const browser = await chromium.launch();
const failPatterns = A.gate_console_fail_patterns.map((s) => new RegExp(s, "i"));
const summary = { label, utc: new Date().toISOString(), assumptions: A, captures: [], failures: [] };

for (const wp of A.waypoints) {
  const page = await browser.newPage({
    viewport: { width: A.viewport.width, height: A.viewport.height },
    deviceScaleFactor: A.viewport.deviceScaleFactor,
  });
  const consoleLog = [];
  page.on("console", (m) => consoleLog.push(`[${m.type()}] ${m.text()}`));
  page.on("pageerror", (e) => consoleLog.push(`[pageerror] ${e.message}`));
  const url = `http://127.0.0.1:${port}/index.html?wp=${wp}` +
    `&cam_d=${A.camera.distance_rphoto_multiples}&cam_az=${A.camera.azimuth_deg}` +
    `&cam_alt=${A.camera.altitude_deg}&tier=${A.quality_tier}`;
  const entry = { waypoint: wp, url, ok: false, console: consoleLog };
  try {
    await page.goto(url, { waitUntil: "load", timeout: 30000 });
    await page.waitForSelector(A.app_ready_selector, { state: "attached", timeout: 30000 });
    // probe first — no probe, no capture
    const probe = await page.evaluate(() =>
      Object.fromEntries([...document.querySelectorAll("[data-q]")].map((e) =>
        [e.dataset.q, e.dataset.value ?? e.textContent.trim()])));
    const missing = A.probe_required_keys.filter((k) => !(k in probe) || probe[k] === "");
    const badConsole = consoleLog.filter((l) => failPatterns.some((r) => r.test(l)));
    if (missing.length) throw new Error(`probe incomplete, missing: ${missing.join(", ")}`);
    if (badConsole.length) throw new Error(`console failure: ${badConsole.join(" | ")}`);
    entry.probe = probe;
    writeFileSync(join(outdir, `${wp}.probe.json`), JSON.stringify({ waypoint: wp, probe, console: consoleLog }, null, 1));
    await page.screenshot({ path: join(outdir, `${wp}.png`) });
    entry.ok = true;
  } catch (e) {
    entry.error = String(e.message ?? e);
    summary.failures.push(`${wp}: ${entry.error}`);
  }
  summary.captures.push(entry);
  await page.close();
}

await browser.close();
srv.close();
writeFileSync(join(outdir, "summary.json"), JSON.stringify(summary, null, 1));
for (const c of summary.captures) console.log(`${c.ok ? "PASS " : "FAIL "} gate/${c.waypoint}${c.error ? "  [" + c.error + "]" : ""}`);
console.log(summary.failures.length ? `gate: ${summary.failures.length} FAILURE(S)` : "gate: ALL GREEN");
process.exit(summary.failures.length ? 1 : 0);
