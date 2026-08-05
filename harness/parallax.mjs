#!/usr/bin/env node
// Pixel-parallax and pixel-photometry captures (reviewer round 5: the
// camera-anchored shell is structurally a skybox until the sliding of near
// stars against far ones is MEASURED at the pixels). Real in-app baselines
// (AU) against parsec distances are sub-pixel at this FOV — physically
// honest — so the measurement uses the project's substitution rule on a
// scratch copy: (a) the eye's magnitude limit pinned to naked-eye (6.5)
// so the full catalogue sky is up, and (b) a declared camera-position
// offset B added inside the star-direction computation. Two captures,
// offset 0 and B: the per-star pixel shift must match the catalogue
// depth field. Writes captures/parallax/para-{0,B}.png.
import { createServer } from "node:http";
import { readFileSync, writeFileSync, mkdirSync, statSync, cpSync } from "node:fs";
import { join, resolve, dirname, extname } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = resolve(HERE, "..", "app");
const B = 5.0e6; // scene units (Rsun) — the amplified, declared baseline

function makeCopy(offset) {
  const dir = join(tmpdir(), `star-parallax-${process.pid}-${offset}`);
  cpSync(APP, dir, { recursive: true });
  const eyePath = join(dir, "src", "eye.js");
  const eye = readFileSync(eyePath, "utf8");
  if (!eye.includes("return 6.5 - 9.5 * this.a;")) {
    console.error("parallax: magnitude-limit expression not found");
    process.exit(2);
  }
  writeFileSync(eyePath, eye.replace("return 6.5 - 9.5 * this.a;",
    "return 9.0 - 0.0 * this.a; // PARALLAX SUBSTITUTION (9: unclamped brightness spread for pixel photometry)"));
  const skyPath = join(dir, "src", "skyfield.js");
  const sky = readFileSync(skyPath, "utf8");
  const target = "const x = (Rj * Math.cos(Pj) - sx) * PC_TO_RSUN - cx;";
  if (!sky.includes(target)) {
    console.error("parallax: direction expression not found");
    process.exit(2);
  }
  // offset ONLY the direction-computation observer; the drawn shell stays
  // anchored on the real camera (offsetting both moves the shell itself
  // and collapses the sky toward the offset direction — measured)
  writeFileSync(skyPath, sky.replace(target,
    `const x = (Rj * Math.cos(Pj) - sx) * PC_TO_RSUN - cx - ${offset}; // PARALLAX SUBSTITUTION`));
  return dir;
}

const MIME = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json",
  ".bin": "application/octet-stream", ".css": "text/css" };

async function capture(dir, name, browser) {
  const srv = createServer((req, rsp) => {
    const p = join(dir, decodeURIComponent(new URL(req.url, "http://x").pathname).replace(/\/$/, "/index.html"));
    try {
      if (!statSync(p).isFile()) throw new Error();
      rsp.writeHead(200, { "content-type": MIME[extname(p)] ?? "application/octet-stream" });
      rsp.end(readFileSync(p));
    } catch { rsp.writeHead(404); rsp.end(); }
  });
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto(
    `http://127.0.0.1:${srv.address().port}/index.html?wp=present_day&cam_d=4&cam_az=0&cam_alt=25&tier=high`,
    { waitUntil: "load" });
  await page.waitForSelector('[data-q="ready"][data-value="1"]', { state: "attached", timeout: 30000 });
  await page.waitForTimeout(700);
  mkdirSync(join(HERE, "captures", "parallax"), { recursive: true });
  await page.screenshot({ path: join(HERE, "captures", "parallax", `${name}.png`) });
  await page.close();
  srv.close();
}

const browser = await chromium.launch();
await capture(makeCopy(0), "para-0", browser);
await capture(makeCopy(B), "para-B", browser);
await browser.close();
console.log(`parallax captures written (baseline ${B} Rsun)`);
