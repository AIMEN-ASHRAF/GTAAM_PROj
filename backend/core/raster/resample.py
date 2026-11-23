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


def _area_average(data: np.ndarray, size_in: float, size_out: float, n_out: int, axis: int) -> np.ndarray:
    """Average cells of width size_in into cells of width size_out along one axis, weighting by overlap.

    Works for any ratio (2:1, 3:1, 1.5:1 ...). A new cell that touches a NaN cell is NaN. Only numpy is used.
    """
    a = np.moveaxis(data, axis, 0)
    n_in = a.shape[0]
    r = size_out / size_in                              # input cells per output cell
    lo = np.arange(n_out) * r
    hi = np.minimum((np.arange(n_out) + 1) * r, n_in)
    bad = np.isnan(a)
    csum = np.vstack([np.zeros((1,) + a.shape[1:]), np.cumsum(np.where(bad, 0.0, a), axis=0)])
    cbad = np.vstack([np.zeros((1,) + a.shape[1:]), np.cumsum(bad, axis=0)])

    def integral(c, x):                                 # running total up to position x (in input cells)
        k = np.minimum(np.floor(x + 1e-9).astype(int), n_in)
        frac = np.clip(x - k, 0.0, None)
        nxt = np.minimum(k, n_in - 1)
        shape = (-1,) + (1,) * (c.ndim - 1)
        step = c[nxt + 1] - c[nxt]                      # the value (or NaN flag) of the partly covered cell
        return c[k] + frac.reshape(shape) * step

    total = integral(csum, hi) - integral(csum, lo)
    bad_cover = (integral(cbad, hi) - integral(cbad, lo)) > 1e-9
    out = total / (hi - lo).reshape((-1,) + (1,) * (a.ndim - 1))
    out[bad_cover] = np.nan
    return np.moveaxis(out, 0, axis)


def square_cells(raster: Raster) -> Raster | None:
    """The same raster on square cells, the way ArcMap prepares a non-square raster for GEODESIC slope.

    ArcMap's output cell is the LARGER of the two sides (JAXA/ALOS tiles above 60N have cells 2" wide
    and 1" tall, so the output is 2" x 2"). Each new cell is the area-weighted average of the input
    cells it covers, whatever the ratio (2:1, 3:1, 1.5:1 ...). Returns None when already square.
    Measured on the 65N tile: slopes from this agree with ArcMap's to 0.17 degrees on average
    (0.001 on square tiles); ArcMap's exact resampling inside the Slope tool is not known.
    """
    w, h = abs(raster.pixel_w), abs(raster.pixel_h)
    big = max(w, h)
    if abs(w - h) <= 1e-9 * big:
        return None
    ncols = max(int(round(raster.width * w / big)), 1)
    nrows = max(int(round(raster.height * h / big)), 1)
    data = raster.data.astype(np.float64)
    if abs(h - big) > 1e-9 * big:                       # rows are finer: average them
        data = _area_average(data, h, big, nrows, axis=0)
    if abs(w - big) > 1e-9 * big:                       # columns are finer: average them
        data = _area_average(data, w, big, ncols, axis=1)
    transform = (big, 0.0, raster.origin_x, 0.0, -big, raster.origin_y)
    return Raster(data.astype(np.float32), transform, raster.crs, raster.nodata)
