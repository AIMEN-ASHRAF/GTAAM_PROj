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


def flat_window_mask(dem: np.ndarray) -> np.ndarray:
    """True where the cell and all 8 neighbours have exactly the same height (a flat cell, as ArcMap sees it)."""
    h, w = dem.shape
    p = np.pad(dem.astype(np.float64), 1, mode="edge")
    win = np.stack([p[i:i + h, j:j + w] for i in range(3) for j in range(3)])
    return (win.max(axis=0) == win.min(axis=0))


def aspect_from_gradients(gx: np.ndarray, gn: np.ndarray, flat_value: float | None = None,
                          north_offset: float = 0.0, flat_mask: np.ndarray | None = None,
                          drop_border: bool = False) -> np.ndarray:
    """north_offset: degrees from true north to grid north (see crs.grid_north_offset); 0 = measure from grid north.
    flat_mask: extra cells to treat as flat (ArcMap's GEODESIC aspect calls a cell flat when its whole 3x3 window
    has one height; the ellipsoid gradient of such a cell is only rounding noise).
    drop_border: leave the outermost ring empty, as ArcMap's GEODESIC aspect does."""
    # downhill direction = -gradient; bearing measured clockwise from north
    aspect = (np.degrees(np.arctan2(-gx, -gn)) - north_offset + 360.0) % 360.0
    # flat cells have no aspect: NaN by default, or a chosen value such as -1
    flat = np.hypot(gx, gn) < 1e-12
    if flat_mask is not None:
        flat |= flat_mask
    aspect[flat] = np.nan if flat_value is None else flat_value
    aspect = aspect.astype(np.float32)
    if drop_border:
        aspect[0, :] = aspect[-1, :] = np.nan
        aspect[:, 0] = aspect[:, -1] = np.nan
    return aspect
