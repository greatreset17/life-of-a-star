#!/usr/bin/env node
// Starfield-aliveness census (the definitive counter-test to "delete the
// render and every test still passes"). The shipped source is untouched:
// per the project's own substitution rule, a SCRATCH COPY gets one declared
// constant replaced — the eye's magnitude-limit intercept (6.5 -> 30), so
// every catalogue star is nominally visible. If the render path is alive
// the frame contains thousands of point sources; if it is dead, zero.
// Deterministic either way. Writes captures/census/starfield.png.
import { createServer } from "node:http";
import { readFileSync, writeFileSync, mkdirSync, statSync, cpSync } from "node:fs";
import { join, resolve, dirname, extname } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = resolve(HERE, "..", "app");
const SCRATCH = join(tmpdir(), `star-census-${process.pid}`);
cpSync(APP, SCRATCH, { recursive: true });

// the one substituted constant, from outside the shipped source
const eyePath = join(SCRATCH, "src", "eye.js");
const eye = readFileSync(eyePath, "utf8");
if (!eye.includes("return 6.5 - 9.5 * this.a;")) {
  console.error("census: expected magnitude-limit expression not found — the harness assumption drifted");
  process.exit(2);
}
writeFileSync(eyePath, eye.replace("return 6.5 - 9.5 * this.a;",
  "return 30.0 - 0.0 * this.a; // CENSUS SUBSTITUTION (harness/census.mjs)"));

const MIME = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json",
  ".bin": "application/octet-stream", ".css": "text/css" };
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
await page.goto(`http://127.0.0.1:${srv.address().port}/index.html?wp=black_dwarf_terminus&cam_d=6&tier=high`,
  { waitUntil: "load" });
await page.waitForSelector('[data-q="ready"][data-value="1"]', { state: "attached", timeout: 30000 });
await page.waitForTimeout(800);
mkdirSync(join(HERE, "captures", "census"), { recursive: true });
await page.screenshot({ path: join(HERE, "captures", "census", "starfield.png") });
await browser.close();
srv.close();
console.log("census capture written");
