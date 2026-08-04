// The two curves — Earth's semi-major axis and the Sun's radius against the
// same slider parameter, both in AU. The gap narrows, nearly holds, and
// closes; the toggle shows what the drag physics changes about the ending
// (fork 21: on this track it changes WHEN and WHERE, not WHETHER).
export class TwoCurves {
  constructor(canvas, earth) {
    this.cv = canvas;
    this.ctx = canvas.getContext("2d");
    this.e = earth;
    const css = getComputedStyle(document.documentElement);
    this.ink = css.getPropertyValue("--ink").trim();
    this.inkDim = css.getPropertyValue("--ink-dim").trim();
    this.inkFaint = css.getPropertyValue("--ink-faint").trim();
    this.yMax = 1.9; // AU
  }

  px(s, au) {
    const w = this.cv.width, h = this.cv.height;
    return [10 + s * (w - 20), h - 22 - (au / this.yMax) * (h - 34)];
  }

  draw(sNow, dragOn) {
    const { ctx, cv, e } = this;
    ctx.clearRect(0, 0, cv.width, cv.height);
    if (!e) {
      ctx.fillStyle = this.inkDim;
      ctx.font = "13px Georgia, serif";
      ctx.fillText("earth table unavailable — region undrawn", 12, 24);
      return;
    }
    ctx.font = "11px Georgia, serif";
    // gridlines at 0.5, 1.0, 1.5 AU
    for (const au of [0.5, 1.0, 1.5]) {
      const [, y] = this.px(0, au);
      ctx.strokeStyle = this.inkFaint;
      ctx.beginPath(); ctx.moveTo(10, y); ctx.lineTo(cv.width - 10, y); ctx.stroke();
      ctx.fillStyle = this.inkDim;
      ctx.fillText(`${au.toFixed(1)} AU`, 14, y - 3);
    }
    const line = (arr, style, width, dash) => {
      ctx.strokeStyle = style;
      ctx.lineWidth = width;
      ctx.setLineDash(dash ?? []);
      ctx.beginPath();
      let pen = false;
      for (let i = 0; i < e.s_grid.length; i++) {
        const v = arr[i];
        if (v === null || v === undefined) { pen = false; continue; }
        const [x, y] = this.px(e.s_grid[i], Math.min(v, this.yMax));
        if (!pen) { ctx.moveTo(x, y); pen = true; } else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    };
    // the star reaches outward…
    line(e.r_star_au, this.inkDim, 1.2);
    // …and the orbit widens: active physics solid, the other ghosted
    line(dragOn ? e.a_nodrag_au : e.a_drag_au, this.inkFaint, 1.0, [4, 4]);
    line(dragOn ? e.a_drag_au : e.a_nodrag_au, this.ink, 1.6);

    const ev = dragOn ? e.engulf_drag : e.engulf_nodrag;
    if (ev) {
      const [x, y] = this.px(ev.s, ev.a_au);
      ctx.beginPath(); ctx.arc(x, y, 4, 0, 2 * Math.PI);
      ctx.fillStyle = this.ink; ctx.fill();
    }
    // cursor at current s
    const [cx] = this.px(sNow, 0);
    ctx.strokeStyle = this.inkDim;
    ctx.beginPath(); ctx.moveTo(cx, 8); ctx.lineTo(cx, cv.height - 22); ctx.stroke();
    ctx.fillStyle = this.inkDim;
    ctx.fillText("R☉(s)  ·  a⊕(s)", cv.width - 110, 14);
  }

  // current Earth orbit radius (AU) at slider s, active physics; null if gone
  aAt(s, dragOn) {
    const e = this.e;
    if (!e) return null;
    const ev = dragOn ? e.engulf_drag : e.engulf_nodrag;
    if (ev && s >= ev.s) return null;
    const arr = dragOn ? e.a_drag_au : e.a_nodrag_au;
    const g = e.s_grid;
    let lo = 0, hi = g.length - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (g[m] <= s) lo = m; else hi = m; }
    const a0 = arr[lo], a1 = arr[hi];
    if (a0 === null || a1 === null) return a0 ?? a1;
    const f = (s - g[lo]) / Math.max(g[hi] - g[lo], 1e-12);
    return a0 * (1 - f) + a1 * f;
  }
}
