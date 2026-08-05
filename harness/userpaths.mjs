#!/usr/bin/env node
// Reproduce the USER'S two reported paths against the REAL app (no
// substitutions of any kind): (A) press the terminus button from the
// default view; (B) drag the slider to its end and wait out the dark
// adaptation. Screenshots + live probe values for pixel measurement.
import { createServer } from "node:http";
import { readFileSync, statSync, mkdirSync } from "node:fs";
import { writeFileSync } from "node:fs";
import { join, resolve, extname } from "node:path";
import { chromium } from "playwright";

const APP = resolve(process.argv[2] ?? "app");
const OUT = resolve(process.argv[3] ?? ".");
mkdirSync(OUT, { recursive: true });
const MIME = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json",
  ".bin": "application/octet-stream", ".css": "text/css" };
const srv = createServer((req, rsp) => {
  const p = join(APP, decodeURIComponent(new URL(req.url, "http://x").pathname).replace(/\/$/, "/index.html"));
  try {
    if (!statSync(p).isFile()) throw new Error();
    rsp.writeHead(200, { "content-type": MIME[extname(p)] ?? "application/octet-stream" });
    rsp.end(readFileSync(p));
  } catch { rsp.writeHead(404); rsp.end(); }
});
await new Promise((r) => srv.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${srv.address().port}/index.html`;
const browser = await chromium.launch();

async function probeOf(page) {
  return page.evaluate(() => Object.fromEntries(
    [...document.querySelectorAll("[data-q]")].map((e) => [e.dataset.q, e.textContent.trim() || e.dataset.value])));
}

const report = {};
{ // path A — the terminus BUTTON from the default view
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errs = [];
  page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
  await page.goto(base, { waitUntil: "load" });
  await page.waitForSelector('[data-q="ready"][data-value="1"]', { state: "attached", timeout: 30000 });
  await page.getByRole("button", { name: "black dwarf terminus" }).click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: join(OUT, "path_a_button.png") });
  report.path_a = { probe: await probeOf(page), errors: errs };
  await page.close();
}
{ // path B — the SLIDER dragged to its end, then the adaptation transient
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errs = [];
  page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
  await page.goto(base, { waitUntil: "load" });
  await page.waitForSelector('[data-q="ready"][data-value="1"]', { state: "attached", timeout: 30000 });
  await page.evaluate(() => {
    const sl = document.getElementById("timeline");
    sl.value = sl.max;
    sl.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await page.waitForTimeout(4000);
  await page.screenshot({ path: join(OUT, "path_b_slider_4s.png") });
  await page.waitForTimeout(41000); // dark adaptation: tau 12 s, ~4 tau total
  await page.screenshot({ path: join(OUT, "path_b_slider_45s.png") });
  report.path_b = { probe: await probeOf(page), errors: errs };
  await page.close();
}
{ // path C — the play button: the journey must advance at the declared
  // rate (PLAY_SPAN_S for the full span; measured over a six-second run)
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto(base, { waitUntil: "load" });
  await page.waitForSelector('[data-q="ready"][data-value="1"]', { state: "attached", timeout: 30000 });
  await page.click("#playbtn");
  const t0 = Date.now();
  await page.waitForTimeout(6000);
  const sNow = parseFloat(await page.inputValue("#timeline"));
  const elapsed = (Date.now() - t0) / 1000;
  const expected = elapsed / 120;
  report.path_c = { s_after: sNow, expected, ok: Math.abs(sNow / expected - 1) < 0.2 };
  await page.close();
}
await browser.close();
srv.close();
writeFileSync(join(OUT, "userpaths.json"), JSON.stringify(report, null, 1));
for (const [k, v] of Object.entries(report)) {
  if (v.probe) {
    console.log(`${k}: sky_visible=${v.probe.sky_visible} adaptation=${v.probe.adaptation} errors=${v.errors.length}`);
    for (const e of v.errors) console.log(`  ERR ${e}`);
  } else {
    console.log(`${k}: s=${v.s_after?.toFixed(4)} expected~${v.expected?.toFixed(4)} ${v.ok ? "OK" : "FAIL"}`);
  }
}
