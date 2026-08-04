"""Grid ownership of the (Teff, log g) plane — fork 16 — and node selection
against what the SVO theory service actually serves. Single-ownership: every
point the track traverses belongs to exactly one grid; seams are declared
constants and their chromaticity discontinuity is measured, never blended.
"""
import json
import re
import urllib.request
from pathlib import Path

import numpy as np

from .constants import (SPECTRA_LOGG_FLOOR, SPECTRA_SEAM_COOL_K,
                        SPECTRA_SEAM_HOT_K, SPECTRA_TMAP_LOGG_TAKEOVER)

SVO = "http://svo2.cab.inta-csic.es/theory/newov2/ssap.php"
GRIDS = {"btsettl": "bt-settl", "atlas9": "Kurucz2003", "tmap2": "tmap2"}


def grid_owner(teff, logg):
    """fork 16 assignment. Returns the grid key owning this (Teff, logg)."""
    if teff <= SPECTRA_SEAM_COOL_K:
        return "btsettl"
    if teff <= SPECTRA_SEAM_HOT_K and logg <= SPECTRA_TMAP_LOGG_TAKEOVER:
        return "atlas9"
    return "tmap2"


def ssap_enumerate(model, teff_lo, teff_hi, logg_lo, logg_hi, meta0=True):
    """List available nodes (teff, logg, fid) of an SVO grid inside a box."""
    url = (f"{SVO}?model={model}&teff_min={teff_lo}&teff_max={teff_hi}"
           f"&logg_min={logg_lo}&logg_max={logg_hi}")
    if meta0:
        url += "&meta_min=0&meta_max=0"
    with urllib.request.urlopen(url, timeout=180) as r:
        x = r.read().decode()
    fields = re.findall(r'<FIELD ID="([^"]+)"', x)
    nodes = []
    for tr in re.findall(r"<TR>(.*?)</TR>", x, re.S):
        tds = re.findall(r"<TD>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</TD>", tr, re.S)
        row = dict(zip(fields, tds))
        acc = row.get("Access.Reference", "")
        fid = re.search(r"fid=(\d+)", acc)
        alpha = row.get("alpha", "0") or "0"
        if fid and float(alpha) == 0.0:
            nodes.append({"teff": float(row["teff"]), "logg": float(row["logg"]),
                          "fid": int(fid.group(1)), "url": acc})
    return nodes


def bracket(values, x):
    """Adjacent available grid values around x. x outside range -> edge pair
    flagged (caller decides whether that is fork-15 edge evaluation or a
    hard hole)."""
    v = np.unique(np.asarray(values, float))
    if x <= v[0]:
        return (v[0], v[0], x - v[0])       # below support
    if x >= v[-1]:
        return (v[-1], v[-1], x - v[-1])    # above support
    i = int(np.searchsorted(v, x, side="right")) - 1
    hi = v[i + 1] if v[i] != x else v[i]
    return (v[i], hi, 0.0)


def select(track, pad=1):
    """Per-EEP grid assignment + union of needed nodes. Returns (per_eep,
    needed, holes). A hole is a bracketing node that the service does not
    serve — holes stop the pipeline by name."""
    T = 10 ** track.col("log_Teff")
    G = track.col("log_g")
    boxes = {
        "btsettl": (max(2000, T[T <= SPECTRA_SEAM_COOL_K].min() - 200), SPECTRA_SEAM_COOL_K + 300,
                    -0.5, min(5.5, G[T <= SPECTRA_SEAM_COOL_K].max() + 0.6)),
        "atlas9": (SPECTRA_SEAM_COOL_K - 300, SPECTRA_SEAM_HOT_K + 1000, 0.0, 5.0),
        "tmap2": (20000, 150000, 4.0, 9.0),
    }
    avail = {}
    for key, (tlo, thi, glo, ghi) in boxes.items():
        avail[key] = ssap_enumerate(GRIDS[key], tlo, thi, glo, ghi,
                                    meta0=(key != "tmap2"))
    per_eep, needed, holes = [], {}, []
    for i in range(track.n):
        key = grid_owner(T[i], G[i])
        nodes = avail[key]
        teffs = sorted({n["teff"] for n in nodes})
        t_lo, t_hi, t_exc = bracket(teffs, T[i])
        cell_nodes, g_exc = {}, 0.0
        for tv in {t_lo, t_hi}:
            loggs = sorted({n["logg"] for n in nodes if n["teff"] == tv})
            if not loggs:
                holes.append((key, tv, G[i], i + 1, "no logg nodes at teff"))
                continue
            g_lo, g_hi, ge = bracket(loggs, G[i])
            g_exc = max(g_exc, abs(ge), key=abs) if ge else g_exc
            for gv in {g_lo, g_hi}:
                n = next(n for n in nodes if n["teff"] == tv and n["logg"] == gv)
                cell_nodes[(tv, gv)] = n
        if t_exc:
            holes.append((key, T[i], G[i], i + 1, f"teff outside grid by {t_exc:.0f}K"))
        for (tv, gv), n in cell_nodes.items():
            needed[(key, tv, gv)] = n | {"grid": key}
        per_eep.append({"eep": i + 1, "grid": key, "teff": T[i], "logg": G[i],
                        "cell": sorted(cell_nodes), "dlogg_edge": round(float(g_exc), 4)})
    return per_eep, needed, holes, avail
