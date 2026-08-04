"""The MIST evolutionary spine. The track is the sole source of truth for
every physical quantity: nothing here is approximated, substituted, or
hardcoded. Interpolation is along the EEP index, never linearly in age
(ages span fourteen orders of magnitude; EEPs are the equal-footing axis).
"""
import re
from pathlib import Path

import numpy as np

from . import sources

# MIST v1.2 primary-EEP anchor names, in the order of the "# EEPs:" header
# line (Dotter 2016, Table 2 / MIST README for low-mass tracks).
ANCHOR_NAMES = ["pms_begin", "zams", "iams", "tams", "rgb_tip",
                "zachb", "tachb", "tp_agb_begin", "post_agb", "wdcs"]


class Track:
    def __init__(self, names, data, anchors):
        self._names = names
        self._data = data           # (n, ncol) float64
        self.anchors = anchors      # name -> 1-based EEP index
        self.n = data.shape[0]

    @classmethod
    def load(cls):
        path = sources.require("mist_track_1p0", extracted=True)
        return cls._parse(Path(path).read_text())

    @classmethod
    def _parse(cls, text):
        lines = text.splitlines()
        anchors = {}
        names = None
        rows = []
        for ln in lines:
            if ln.startswith("#"):
                m = re.match(r"#\s*EEPs:\s*(.*)", ln)
                if m:
                    idxs = [int(x) for x in m.group(1).split()]
                    anchors = dict(zip(ANCHOR_NAMES, idxs))
                if "star_age" in ln:
                    names = ln.lstrip("#").split()
                continue
            if ln.strip():
                rows.append(np.fromstring(ln, sep=" "))
        data = np.vstack(rows)
        if names is None or len(names) != data.shape[1]:
            raise ValueError("MIST header column names not found or count mismatch")
        return cls(names, data, anchors)

    def col(self, name):
        return self._data[:, self._names.index(name)]

    def at_eep(self, eep_1based, cols=("star_age", "star_mass", "log_L", "log_Teff",
                                       "log_R", "log_g", "center_h1", "center_he4", "phase")):
        """Linear interpolation in fractional (1-based) EEP index."""
        x = float(eep_1based) - 1.0
        i = int(np.clip(np.floor(x), 0, self.n - 2))
        f = x - i
        out = {}
        for c in cols:
            v = self.col(c)
            out[c] = float(v[i] * (1 - f) + v[i + 1] * f)
        return out

    def eep_at_age(self, age_yr):
        """Inverse lookup age -> fractional EEP via the tabulated (age, EEP)
        pairs; local linear inversion between adjacent EEPs, never a global
        fit in age."""
        ages = self.col("star_age")
        return 1.0 + float(np.interp(age_yr, ages, np.arange(self.n)))

    def at_age(self, age_yr, **kw):
        return self.at_eep(self.eep_at_age(age_yr), **kw)
