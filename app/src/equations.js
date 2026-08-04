// Hand-typeset equations on canvas — real glyphs, fraction bars, subscripts,
// the way a physicist's notes render them. No external typesetting library;
// a small recursive layout over a token tree.
//
// Node forms:  "L"  {sub:[base,sub]}  {sup:[base,sup]}  {frac:[num,den]}
//              {row:[...]}  {it:"x"} (italic)  {sp:w}
const SIZE = 15;

export function typeset(canvas, tree, inkColour) {
  const ctx = canvas.getContext("2d");
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const m = measure(ctx, tree, SIZE);
  canvas.width = Math.ceil((m.w + 8) * dpr);
  canvas.height = Math.ceil((m.asc + m.desc + 8) * dpr);
  canvas.style.width = `${Math.ceil(m.w + 8)}px`;
  canvas.style.height = `${Math.ceil(m.asc + m.desc + 8)}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = inkColour;
  ctx.strokeStyle = inkColour;
  ctx.textBaseline = "alphabetic";
  render(ctx, tree, 4, 4 + m.asc, SIZE);
}

function font(px, italic) {
  return `${italic ? "italic " : ""}${px}px "Iowan Old Style", Palatino, Georgia, serif`;
}

function measure(ctx, node, px) {
  if (typeof node === "string") {
    ctx.font = font(px, false);
    return { w: ctx.measureText(node).width, asc: px * 0.78, desc: px * 0.22 };
  }
  if (node.it !== undefined) {
    ctx.font = font(px, true);
    return { w: ctx.measureText(node.it).width, asc: px * 0.78, desc: px * 0.22 };
  }
  if (node.sp !== undefined) return { w: node.sp, asc: 0, desc: 0 };
  if (node.row) {
    let w = 0, asc = 0, desc = 0;
    for (const ch of node.row) {
      const m = measure(ctx, ch, px);
      w += m.w; asc = Math.max(asc, m.asc); desc = Math.max(desc, m.desc);
    }
    return { w, asc, desc };
  }
  if (node.sub || node.sup) {
    const [base, mod] = node.sub ?? node.sup;
    const mb = measure(ctx, base, px);
    const mm = measure(ctx, mod, px * 0.68);
    const shift = px * 0.34;
    return node.sub
      ? { w: mb.w + mm.w + 1, asc: mb.asc, desc: Math.max(mb.desc, mm.desc + shift * 0.6) }
      : { w: mb.w + mm.w + 1, asc: Math.max(mb.asc, mm.asc + shift), desc: mb.desc };
  }
  if (node.frac) {
    const mn = measure(ctx, node.frac[0], px * 0.92);
    const md = measure(ctx, node.frac[1], px * 0.92);
    const w = Math.max(mn.w, md.w) + 8;
    return { w, asc: mn.asc + mn.desc + px * 0.32, desc: md.asc + md.desc + px * 0.1 };
  }
  return { w: 0, asc: 0, desc: 0 };
}

function render(ctx, node, x, y, px) {
  if (typeof node === "string") {
    ctx.font = font(px, false);
    ctx.fillText(node, x, y);
    return measure(ctx, node, px).w;
  }
  if (node.it !== undefined) {
    ctx.font = font(px, true);
    ctx.fillText(node.it, x, y);
    return measure(ctx, node, px).w;
  }
  if (node.sp !== undefined) return node.sp;
  if (node.row) {
    let dx = 0;
    for (const ch of node.row) dx += render(ctx, ch, x + dx, y, px);
    return dx;
  }
  if (node.sub || node.sup) {
    const [base, mod] = node.sub ?? node.sup;
    const wb = render(ctx, base, x, y, px);
    const shift = px * 0.34;
    const wm = render(ctx, mod, x + wb + 1, y + (node.sub ? shift * 0.9 : -shift), px * 0.68);
    return wb + wm + 1;
  }
  if (node.frac) {
    const m = measure(ctx, node, px);
    const mn = measure(ctx, node.frac[0], px * 0.92);
    const md = measure(ctx, node.frac[1], px * 0.92);
    const barY = y - px * 0.28;
    render(ctx, node.frac[0], x + (m.w - mn.w) / 2, barY - px * 0.18 - mn.desc, px * 0.92);
    render(ctx, node.frac[1], x + (m.w - md.w) / 2, barY + px * 0.16 + md.asc, px * 0.92);
    ctx.beginPath();
    ctx.moveTo(x + 1, barY);
    ctx.lineTo(x + m.w - 1, barY);
    ctx.lineWidth = 1;
    ctx.stroke();
    return m.w;
  }
  return 0;
}

// The governing relations, as token trees
export const EQ = {
  luminosity: { row: [{ it: "L" }, " = 4π", { sup: [{ it: "R" }, "2"] }, "σ",
                      { sup: [{ sub: [{ it: "T" }, "eff"] }, "4"] }] },
  scaleHeight: { row: [{ sub: [{ it: "H" }, "p"] }, " = ",
                       { frac: [{ row: [{ it: "k" }, { it: "T" }] },
                                { row: ["μ", { sp: 2 }, { sub: [{ it: "m" }, "H"] }, { sp: 2 }, { it: "g" }] }] }] },
  colourChain: { row: ["F(λ) → x̄ȳz̄ → XYZ → sRGB"] },
  granuleCount: { row: [{ it: "N" }, " = ",
                        { frac: [{ row: ["4", { sup: [{ it: "R" }, "2"] }] },
                                 { row: [{ sup: [{ it: "D" }, "2"] }] }] }] },
  orbit: { row: [{ it: "a" }, " ∝ ",
                 { frac: ["1", { row: [{ it: "M" }, "(", { it: "t" }, ")"] }] },
                 { sp: 10 }, "−",
                 { frac: [{ row: [{ it: "a" }] },
                          { row: [{ sub: ["τ", "f"] }] }] },
                 { sp: 3 },
                 { frac: [{ row: ["12", { sp: 2 }, { sub: [{ it: "M" }, "env"] },
                                  { it: "q" }, "(1+", { it: "q" }, ")"] },
                          { row: ["21", { sp: 2 }, { it: "M" }] }] },
                 { sp: 3 }, "(", { frac: [{ it: "R" }, { it: "a" }] }, { sup: [")", "8"] }] },
};
