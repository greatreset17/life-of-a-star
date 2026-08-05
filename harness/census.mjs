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

// diagnostic print (harness copy only)
{
  const sf = join(SCRATCH, "src", "skyfield.js");
  let s2 = readFileSync(sf, "utf8");
  s2 = s2.replace("this.posAttr.needsUpdate = true;",
    `if (!this.dg) { this.dg = true;
      let front = 0, vis2 = 0;
      const fx=-camPos.x, fy=-camPos.y, fz=-camPos.z; const fl=Math.hypot(fx,fy,fz)||1;
      for (let q=0;q<n;q++){ if (MG[q]<=magLimit) vis2++;
        const dx=P[q*3]-camPos.x, dy=P[q*3+1]-camPos.y, dz=P[q*3+2]-camPos.z;
        if ((dx*fx+dy*fy+dz*fz)/(Math.hypot(dx,dy,dz)*fl) > 0.77) front++; }
      console.warn("CDIAG lo", lo, "f", f.toFixed(3), "visMG", vis2, "front", front,
        "P0", P[0].toFixed(0), P[1].toFixed(0), P[2].toFixed(0));
    }
    this.posAttr.needsUpdate = true;`);
  writeFileSync(sf, s2);
}

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
page.on("console", (m) => { if (/CDIAG/.test(m.text())) console.log(m.text()); });
await page.goto(`http://127.0.0.1:${srv.address().port}/index.html?wp=black_dwarf_terminus&cam_d=6&cam_alt=90&tier=high`,
  { waitUntil: "load" });
await page.waitForSelector('[data-q="ready"][data-value="1"]', { state: "attached", timeout: 30000 });
await page.waitForTimeout(800);
mkdirSync(join(HERE, "captures", "census"), { recursive: true });
await page.screenshot({ path: join(HERE, "captures", "census", "starfield.png") });
await browser.close();
srv.close();
console.log("census capture written");
