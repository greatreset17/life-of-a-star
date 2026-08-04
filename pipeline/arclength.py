"""Arc-length parameterisation of the track in (log Teff, log L) space —
the slider's axis. Constant slider speed is constant visible change; age is a
readout, never the axis. Normalised to unit total length over whatever spine
it is built from (MIST alone in v0.1; MIST + cooling + region B from v0.3,
integrated only to the declared terminus)."""
import numpy as np


class ArcLength:
    def __init__(self, s_nodes):
        # s_nodes: cumulative normalised arc length at each spine node (len n)
        self.s_nodes = s_nodes
        self._idx = np.arange(1, len(s_nodes) + 1, dtype=float)

    @classmethod
    def from_xy(cls, x, y):
        xy = np.stack([np.asarray(x, float), np.asarray(y, float)], axis=1)
        seg = np.linalg.norm(np.diff(xy, axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(seg)])
        total = s[-1]
        if not (np.isfinite(total) and total > 0):
            raise ValueError("arc length not finite and positive")
        return cls(s / total)

    @classmethod
    def from_track(cls, track):
        return cls.from_xy(track.col("log_Teff"), track.col("log_L"))

    def s_of_eep(self, eep_1based):
        return np.interp(np.asarray(eep_1based, float), self._idx, self.s_nodes)

    def eep_of_s(self, s):
        # flat spots (zero-length segments) invert to their first node;
        # np.interp on the swapped axes requires strict monotonicity only
        # where it matters — ties produce a non-decreasing inverse.
        return np.interp(np.asarray(s, float), self.s_nodes, self._idx)
