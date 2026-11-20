"""Slope from the 3x3 neighbourhood, with the same two choices ArcMap offers.

planar   : Horn's method (nearer neighbours count double), same as GDAL/QGIS and ArcMap PLANAR.
geodesic : all 9 cells count the same (least-squares plane). This file holds that plane fit, which
           is what `geodesic` uses on a projected DEM (cells already in metres). On a degree DEM the
           service uses `slope_ellipsoid.py` instead: the same idea measured in 3D on the WGS84
           ellipsoid, which matches ArcMap GEODESIC (Islamabad DEM: mean 12.9856 vs 12.9857)."""
from __future__ import annotations

import numpy as np

from core.raster.windows import shifted


def gradients(dem: np.ndarray, dx: float | np.ndarray, dy: float | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(gx, gn): rise per metre going east, and going north. dx, dy = cell size in metres: a number, or one value per row as an array of shape (rows, 1)."""
    n = shifted(dem.astype(np.float64))
    gx = ((n["ne"] + 2 * n["e"] + n["se"]) - (n["nw"] + 2 * n["w"] + n["sw"])) / (8 * dx)
    gn = ((n["nw"] + 2 * n["n"] + n["ne"]) - (n["sw"] + 2 * n["s"] + n["se"])) / (8 * dy)
    return gx, gn


METHODS = ("planar", "geodesic")


def plane_fit_gradients(dem: np.ndarray, dx: float | np.ndarray, dy: float | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(gx, gn) of the best-fit plane through the 3x3 cells: three cells per side, all weight 1, divided by 6 (3 rows x 2 cells apart)."""
    n = shifted(dem.astype(np.float64))
    gx = ((n["ne"] + n["e"] + n["se"]) - (n["nw"] + n["w"] + n["sw"])) / (6 * dx)
    gn = ((n["nw"] + n["n"] + n["ne"]) - (n["sw"] + n["s"] + n["se"])) / (6 * dy)
    return gx, gn


def compute_slope(dem: np.ndarray, dx: float | np.ndarray, dy: float | np.ndarray,
                  units: str = "degrees", method: str = "planar") -> np.ndarray:
    if units not in ("degrees", "percent"):
        raise ValueError("units must be 'degrees' or 'percent'")
    if method not in METHODS:
        raise ValueError("method must be 'planar' or 'geodesic'")
    gx, gn = (gradients if method == "planar" else plane_fit_gradients)(dem, dx, dy)
    rise = np.hypot(gx, gn)
    out = np.degrees(np.arctan(rise)) if units == "degrees" else rise * 100.0
    return out.astype(np.float32)
