"""Curvature (Zevenbergen & Thorne). Positive = convex (hilltops), negative = concave."""
from __future__ import annotations

import numpy as np

from core.raster.windows import shifted_filled


def compute_curvature(dem: np.ndarray, dx: float | np.ndarray, dy: float | np.ndarray) -> np.ndarray:
    n = shifted_filled(dem.astype(np.float64))     # like ArcMap: a missing neighbour takes the centre value
    c = n["c"]
    d2x = ((n["w"] + n["e"]) / 2 - c) / dx ** 2
    d2y = ((n["n"] + n["s"]) / 2 - c) / dy ** 2
    return (-2.0 * (d2x + d2y) * 100.0).astype(np.float32)
