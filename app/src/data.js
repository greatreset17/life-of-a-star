// Data loading. The app fetches ONLY its local Stage 0 tables; a missing or
// malformed table is a visible refusal (panel reads unavailable, the region
// goes undrawn), never a substituted value.
export class Unavailable extends Error {
  constructor(what, why) {
    super(`unavailable: ${what} — ${why}`);
    this.what = what;
  }
}

export async function loadTables() {
  const [track, colour] = await Promise.all([
    fetchJson("./data/track.json", "track table"),
    fetchJson("./data/colour.json", "colour table"),
  ]);
  const n = track.meta?.n;
  for (const key of ["s", "age_yr", "log_L", "log_Teff", "log_R", "log_g",
                     "star_mass", "phase", "granule_d_m", "granule_n_disk",
                     "ld_a", "ld_flux_ratio"]) {
    if (!Array.isArray(track[key]) || track[key].length !== n) {
      throw new Unavailable("track table", `column ${key} absent or wrong length`);
    }
  }
  if (!Array.isArray(colour.rows) || colour.rows.length !== n) {
    throw new Unavailable("colour table", "row count does not match track");
  }
  return { track, colour };
}

async function fetchJson(url, what) {
  let r;
  try {
    r = await fetch(url);
  } catch (e) {
    throw new Unavailable(what, String(e));
  }
  if (!r.ok) throw new Unavailable(what, `HTTP ${r.status}`);
  return r.json();
}

// Fractional-EEP interpolation on a named column (linear in EEP index —
// the same rule Stage 0 uses; never linear in age).
export function colAt(track, key, eepFrac) {
  const a = track[key];
  const x = Math.min(Math.max(eepFrac - 1, 0), a.length - 1);
  const i = Math.min(Math.floor(x), a.length - 2);
  const f = x - i;
  return a[i] * (1 - f) + a[i + 1] * f;
}

// Nearest-row lookup: colour and LD are taken from the nearest tabulated
// EEP so that every rendered value resolves to exactly one table entry
// (suite test 39 — bijection); 1710 rows are dense enough that adjacent
// steps sit below visible thresholds (measured in the colour suite).
export function rowAt(track, eepFrac) {
  return Math.min(Math.max(Math.round(eepFrac) - 1, 0), track.meta.n - 1);
}

export function eepOfS(track, s) {
  const sn = track.s;
  if (s <= sn[0]) return 1;
  if (s >= sn[sn.length - 1]) return sn.length;
  let lo = 0, hi = sn.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (sn[mid] <= s) lo = mid; else hi = mid;
  }
  const span = sn[hi] - sn[lo];
  return lo + 1 + (span > 0 ? (s - sn[lo]) / span : 0);
}

export function phaseName(code, teff) {
  if (code < 0) return "protostellar contraction";
  if (code === 0) return "main sequence";
  if (code === 2) return teff > 5000 ? "subgiant" : "red giant branch";
  if (code === 3) return "core helium burning";
  if (code === 4) return "early AGB";
  if (code === 5) return "thermally pulsing AGB";
  if (code === 6) return teff > 25000 ? "post-AGB / young white dwarf" : "post-AGB";
  return "white dwarf cooling";
}

export function formatAge(yr) {
  if (yr < 1e4) return [yr.toFixed(0), "years"];
  if (yr < 1e6) return [(yr / 1e3).toFixed(1), "thousand years"];
  if (yr < 1e9) return [(yr / 1e6).toFixed(2), "million years"];
  return [(yr / 1e9).toFixed(3), "billion years"];
}
