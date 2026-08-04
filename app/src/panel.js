// The instrument panel — understated, numbers and equations live. It is also
// the harness's probe surface (fork 12): every [data-q] element is shipped,
// user-facing functionality; the gate reads them and writes nothing.
import { typeset, EQ } from "./equations.js";
import { formatAge } from "./data.js";

const ROWS = [
  ["s", "slider s (arc length)"],
  ["age_yr", "age"],
  ["phase", "phase"],
  ["teff_k", "Tₑᶠᶠ (K)"],
  ["log_l", "log L / L☉"],
  ["r_rsun", "R / R☉"],
  ["r_au", "R (AU)"],
  ["log_g", "log g"],
  ["mass", "M / M☉"],
  ["chromaticity_srgb", "linear sRGB in use"],
  ["gamut_excursion", "gamut excursion (Oklab C)"],
  ["granules_derived", "granule count — derived"],
  ["granules_rendered", "granule count — rendered"],
  ["granule_d", "granule diameter"],
  ["instances_drawn", "draw calls"],
  ["ld_source", "limb-darkening source"],
  ["data_state", "data state"],
];

export class Panel {
  constructor(root) {
    this.el = {};
    const frag = document.createDocumentFragment();
    const ink = getComputedStyle(document.documentElement).getPropertyValue("--ink").trim();

    const addEq = (tree, note) => {
      const cv = document.createElement("canvas");
      typeset(cv, tree, ink);
      frag.appendChild(cv);
      if (note) {
        const d = document.createElement("div");
        d.className = "note";
        d.textContent = note;
        frag.appendChild(d);
      }
    };
    const addRows = (keys) => {
      for (const [q, label] of ROWS.filter(([k]) => keys.includes(k))) {
        const row = document.createElement("div");
        row.className = "row";
        const k = document.createElement("span");
        k.className = "k";
        k.textContent = label;
        const v = document.createElement("span");
        v.className = "v";
        v.dataset.q = q;
        row.append(k, v);
        frag.appendChild(row);
        this.el[q] = v;
      }
    };
    const sect = () => {
      const d = document.createElement("div");
      d.className = "sect";
      frag.appendChild(d);
    };

    addRows(["s", "age_yr", "phase", "data_state"]);
    sect();
    addEq(EQ.luminosity);
    addRows(["teff_k", "log_l", "r_rsun", "r_au", "log_g", "mass"]);
    sect();
    addEq(EQ.colourChain);
    addRows(["chromaticity_srgb", "gamut_excursion"]);
    sect();
    addEq(EQ.scaleHeight, "scale derived from the track; cell texture procedural (fork 4)");
    addEq(EQ.granuleCount);
    addRows(["granules_derived", "granules_rendered", "granule_d", "instances_drawn", "ld_source"]);
    sect();
    const bd = document.createElement("div");
    bd.className = "note";
    bd.textContent = "Declared boundary: the star carries full rigour; background sky "
      + "arrives in a later pass with positions computed and existence frozen at the "
      + "present epoch; granule texture is procedural over a derived scale; the MIST "
      + "grid track runs +76 K / +10.6% L of the observed Sun at 4.57 Gyr (fork 14).";
    frag.appendChild(bd);

    // the harness-visible ready flag (set by main.js after first frame)
    const ready = document.createElement("span");
    ready.dataset.q = "ready";
    ready.dataset.value = "0";
    frag.appendChild(ready);
    this.readyEl = ready;
    root.appendChild(frag);
  }

  update(p) {
    const set = (q, text, value) => {
      const e = this.el[q];
      if (!e) return;
      e.textContent = text;
      e.dataset.value = value ?? text;
    };
    set("s", p.s.toFixed(5));
    const [av, au] = formatAge(p.ageYr);
    set("age_yr", `${av} ${au}`, p.ageYr.toExponential(4));
    set("phase", p.phase);
    set("teff_k", p.teff.toFixed(0));
    set("log_l", p.logL.toFixed(3));
    set("r_rsun", p.rRsun >= 100 ? p.rRsun.toFixed(1) : p.rRsun.toPrecision(4));
    set("r_au", (p.rRsun * 6.957e8 / 1.495978707e11).toPrecision(3));
    set("log_g", p.logg.toFixed(3));
    set("mass", p.mass.toFixed(4));
    set("chromaticity_srgb", p.rgbLin.map((v) => v.toFixed(3)).join(", "));
    set("gamut_excursion", p.excursion.toFixed(4));
    set("granules_derived", Math.round(p.granDerived).toExponential(2));
    set("granules_rendered", Math.round(p.granRendered).toExponential(2));
    set("granule_d", p.granD > 7e8 ? `${(p.granD / 6.957e8).toFixed(1)} R☉` : `${(p.granD / 1e3).toFixed(0)} km`);
    set("instances_drawn", String(p.drawCalls));
    set("ld_source", p.ldSource.replace("neilson2013-spherical", "N&L13 spherical")
      .replace("claret2011-planar", "Claret11 planar"));
    set("data_state", p.dataState);
  }

  ready() {
    this.readyEl.dataset.value = "1";
  }
}
