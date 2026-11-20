"""Change a raster's cell size."""
from __future__ import annotations

import numpy as np

from .model import Raster
from .sampling import sample_bilinear, sample_nearest

METHODS = ("nearest", "bilinear")


def resample(raster: Raster, cell_size: float, method: str = "bilinear") -> Raster:
    """cell_size is in the raster's own units (degrees for EPSG:4326, metres for UTM)."""
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    if cell_size <= 0:
        raise ValueError("cell_size must be positive.")
    minx, miny, maxx, maxy = raster.bounds
    width = max(int(round((maxx - minx) / cell_size)), 1)
    height = max(int(round((maxy - miny) / cell_size)), 1)
    if width * height > 100_000_000:
        raise ValueError("That cell size would create a raster larger than 100 million cells.")
    xs = minx + (np.arange(width) + 0.5) * cell_size
    ys = maxy - (np.arange(height) + 0.5) * cell_size
    gx, gy = np.meshgrid(xs, ys)
    sampler = sample_bilinear if method == "bilinear" else sample_nearest
    data = sampler(raster, gx.ravel(), gy.ravel()).reshape(height, width).astype(np.float32)
    transform = (cell_size, 0.0, minx, 0.0, -cell_size, maxy)
    return Raster(data, transform, raster.crs, raster.nodata)


def square_cells(raster: Raster) -> Raster | None:
    """The same raster on square cells, the way ArcMap's GEODESIC slope prepares a degree DEM.

    JAXA/ALOS tiles above 60N have cells 2" wide and 1" tall. ArcMap first makes them square at the
    larger size (2" x 2"), by averaging the finer direction in blocks, then measures slope. This does
    the same. Returns None when the cells are already square, or the sizes are not a whole-number
    multiple of each other (then the raster is used as it is).
    """
    w, h = raster.pixel_w, raster.pixel_h
    big, small = max(w, h), min(w, h)
    if big - small <= 1e-9 * big:
        return None
    k = int(round(big / small))
    if k < 2 or k > 16 or abs(big / small - k) > 0.02:
        return None
    data = raster.data
    if h < w:                                   # rows are finer: average k rows into one
        n = (data.shape[0] // k) * k
        new = data[:n].reshape(n // k, k, data.shape[1]).mean(axis=1)
    else:                                       # columns are finer: average k columns into one
        n = (data.shape[1] // k) * k
        new = data[:, :n].reshape(data.shape[0], n // k, k).mean(axis=2)
    transform = (big, 0.0, raster.origin_x, 0.0, -big, raster.origin_y)
    return Raster(new.astype(np.float32), transform, raster.crs, raster.nodata)
