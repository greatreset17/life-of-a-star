#!/usr/bin/env node
// Layer decomposition (the isolation-probe method, harness copies only):
// renders the same state with one layer disabled per run so a background
// artefact can be attributed by subtraction. Shipped source untouched.
import { createServer } from "node:http";
import { readFileSync, writeFileSync, mkdirSync, statSync, cpSync } from "node:fs";
import { join, resolve, dirname, extname } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = resolve(HERE, "..", "app");
const OUT = join(HERE, "captures", "layers");
mkdirSync(OUT, { recursive: true });
const URLQ = process.argv[2] ?? "s=0.93172&cam_d=21";

const MODS = {
  baseline: null,
  no_void: ["src/void.js", "uLevel: { value: 0.012 }", "uLevel: { value: 0.0 }"],
  no_band: ["src/band.js", "this.uniforms.uGain.value = Math.max(0, (0.20 - adaptation) / 0.20);",
    "this.uniforms.uGain.value = 0.0;"],
  no_starquad_miss: ["src/star.js", "bright = 0.6 * limbLaw(uMuFloor + 0.06 * (1.0 - uMuFloor))",
    "bright = 0.0 * limbLaw(uMuFloor + 0.06 * (1.0 - uMuFloor))"],
  no_points: ["src/skyfield.js", "gl_FragColor = vec4(enc, fall);",
    "gl_FragColor = vec4(enc, 0.0);"],
};

const MIME = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json",
  ".bin": "application/octet-stream", ".css": "text/css" };

for (const [name, mod] of Object.entries(MODS)) {
  const SCRATCH = join(tmpdir(), `star-layers-${process.pid}-${name}`);
  cpSync(APP, SCRATCH, { recursive: true });
  if (mod) {
    const p = join(SCRATCH, mod[0]);
    const src = readFileSync(p, "utf8");
    if (!src.includes(mod[1])) { console.error(`${name}: anchor drifted`); process.exit(2); }
    writeFileSync(p, src.replace(mod[1], mod[2]));
  }
  const srv = createServer((req, rsp) => {
    const p = join(SCRATCH, decodeURIComponent(new URL(req.url, "http://x").pathname).replace(/\/$/, "/index.html"));
    try {
      if (!statSync(p).isFile()) throw new Error();
      rsp.writeHead(200, { "content-type": MIME[extname(p)] ?? "application/octet-stream" });
      rsp.end(readFileSync(p));
    } catch { rsp.writeHead(404); rsp.end(); }
  });
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto(`http://127.0.0.1:${srv.address().port}/index.html?${URLQ}`, { waitUntil: "load" });
  await page.waitForSelector('[data-q="ready"][data-value="1"]', { state: "attached", timeout: 30000 });
  await page.waitForTimeout(20000); // partial adaptation, like a slider user
  await page.screenshot({ path: join(OUT, `${name}.png`) });
  await browser.close();
  srv.close();
  console.log(`${name} captured`);
}
