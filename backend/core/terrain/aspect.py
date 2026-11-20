"""Aspect: the compass direction the slope faces (0 = north, 90 = east, clockwise)."""
from __future__ import annotations

import numpy as np

from .slope import METHODS, gradients, plane_fit_gradients


def compute_aspect(dem: np.ndarray, dx: float | np.ndarray, dy: float | np.ndarray,
                   flat_value: float | None = None, method: str = "planar") -> np.ndarray:
    """method: planar = Horn (weights 1,2,1); geodesic = plane fit (weights 1,1,1) for projected DEMs."""
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    gx, gn = (gradients if method == "planar" else plane_fit_gradients)(dem, dx, dy)
    return aspect_from_gradients(gx, gn, flat_value)


def aspect_from_gradients(gx: np.ndarray, gn: np.ndarray, flat_value: float | None = None,
                          north_offset: float = 0.0) -> np.ndarray:
    """north_offset: degrees from true north to grid north (see crs.grid_north_offset); 0 = measure from grid north."""
    # downhill direction = -gradient; bearing measured clockwise from north
    aspect = (np.degrees(np.arctan2(-gx, -gn)) - north_offset + 360.0) % 360.0
    # flat cells have no aspect: NaN by default, or a chosen value such as -1
    aspect[np.hypot(gx, gn) < 1e-12] = np.nan if flat_value is None else flat_value
    return aspect.astype(np.float32)
