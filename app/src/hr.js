// The Hertzsprung–Russell diagram — validator and artwork at once. The full
// track is drawn with temperature increasing to the LEFT; a marker rides it
// in lockstep with the slider. Axis/ink colours are instrument UI (CSS
// variables); the marker's fill is the star's own table chromaticity —
// the diagram literally carries the derived colour.
export class HrDiagram {
  constructor(canvas, track, colour) {
    this.cv = canvas;
    this.ctx = canvas.getContext("2d");
    this.track = track;
    this.colour = colour;
    const lt = track.log_Teff, ll = track.log_L;
    this.tMin = Math.min(...lt) - 0.08;
    this.tMax = Math.max(...lt) + 0.08;
    this.lMin = Math.min(...ll) - 0.3;
    this.lMax = Math.max(...ll) + 0.3;
    const css = getComputedStyle(document.documentElement);
    this.ink = css.getPropertyValue("--ink").trim();
    this.inkDim = css.getPropertyValue("--ink-dim").trim();
    this.inkFaint = css.getPropertyValue("--ink-faint").trim();
    this.drawBase();
  }

  // logTeff increases leftward
  px(lt, ll) {
    const w = this.cv.width, h = this.cv.height;
    const x = (this.tMax - lt) / (this.tMax - this.tMin) * (w - 76) + 56;
    const y = (this.lMax - ll) / (this.lMax - this.lMin) * (h - 64) + 20;
    return [x, y];
  }

  drawBase() {
    const { ctx, cv } = this;
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.save();
    ctx.font = "24px Georgia, serif";
    ctx.fillStyle = this.inkDim;
    ctx.strokeStyle = this.inkFaint;
    ctx.lineWidth = 1;
    // axes grid: decades of log L, 0.2 steps of log Teff labels sparse
    for (let l = Math.ceil(this.lMin); l <= Math.floor(this.lMax); l++) {
      const [, y] = this.px(this.tMin, l);
      ctx.beginPath(); ctx.moveTo(56, y); ctx.lineTo(cv.width - 20, y); ctx.stroke();
      ctx.fillText(l === 0 ? "1" : `10${sup(l)}`, 8, y + 5);
    }
    for (let t = 3.4; t <= this.tMax; t += 0.4) {
      const [x] = this.px(t, this.lMin);
      ctx.beginPath(); ctx.moveTo(x, 20); ctx.lineTo(x, cv.height - 44); ctx.stroke();
      const kk = Math.round(Math.pow(10, t) / 100) / 10;
      ctx.fillText(`${kk}k`, x - 14, cv.height - 26);
    }
    ctx.fillStyle = this.inkDim;
    ctx.fillText("L / L☉", 64, 20);
    ctx.fillText("Teff (K) →  cooler", cv.width - 210, cv.height - 4);
    // the track — region B (beyond the data horizon) in a visibly lighter
    // weight; the join and the horizon are both marked
    const lt = this.track.log_Teff, ll = this.track.log_L;
    const state = this.track.data_state;
    const seg = (from, to, alpha, width) => {
      ctx.strokeStyle = this.ink;
      ctx.lineWidth = width;
      ctx.globalAlpha = alpha;
      ctx.beginPath();
      for (let i = from; i < to; i++) {
        const [x, y] = this.px(lt[i], ll[i]);
        if (i === from) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    };
    const hIdx = state ? state.lastIndexOf("tabulated") : lt.length - 1;
    seg(0, hIdx + 1, 0.75, 1.4);
    if (hIdx < lt.length - 1) seg(hIdx, lt.length, 0.28, 1.0);
    // marks: join (two codes meet) and horizon (data ends)
    const mark = (i, label) => {
      if (i === undefined || i === null) return;
      const [x, y] = this.px(lt[i], ll[i]);
      ctx.globalAlpha = 0.8;
      ctx.strokeStyle = this.inkDim;
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x - 5, y - 5); ctx.lineTo(x + 5, y + 5); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(x - 5, y + 5); ctx.lineTo(x + 5, y - 5); ctx.stroke();
      ctx.font = "24px Georgia, serif";
      ctx.fillStyle = this.inkFaint;
      ctx.fillText(label, x + 7, y - 4);
    };
    if (this.track.meta.join_index) mark(this.track.meta.join_index, "join");
    if (this.track.meta.horizon_index) mark(this.track.meta.horizon_index, "data horizon");
    ctx.restore();
    this.base = ctx.getImageData(0, 0, cv.width, cv.height);
  }

  draw(eepFrac, rgbDisplay) {
    const { ctx } = this;
    ctx.putImageData(this.base, 0, 0);
    const i = Math.min(Math.max(Math.round(eepFrac) - 1, 0), this.track.meta.n - 1);
    const [x, y] = this.px(this.track.log_Teff[i], this.track.log_L[i]);
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, 2 * Math.PI);
    ctx.fillStyle = rgbDisplay;
    ctx.fill();
    ctx.strokeStyle = this.ink;
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.restore();
  }
}

function sup(n) {
  const map = { "-": "⁻", 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹" };
  return String(n).split("").map((c) => map[c] ?? c).join("");
}
