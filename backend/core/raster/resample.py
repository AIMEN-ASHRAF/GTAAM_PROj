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


def _overlap_weights(n_in: int, size_in: float, n_out: int, size_out: float) -> "sparse.csr_matrix":
    """Row i = share of output cell i covered by each input cell (all cells measured from the same edge)."""
    from scipy import sparse
    rows, cols, vals = [], [], []
    for i in range(n_out):
        lo, hi = i * size_out, min((i + 1) * size_out, n_in * size_in)
        j0, j1 = int(np.floor(lo / size_in + 1e-9)), int(np.ceil(hi / size_in - 1e-9))
        for j in range(j0, min(j1, n_in)):
            ov = min(hi, (j + 1) * size_in) - max(lo, j * size_in)
            if ov > 1e-12 * size_out:
                rows.append(i), cols.append(j), vals.append(ov)
    m = sparse.csr_matrix((vals, (rows, cols)), shape=(n_out, n_in))
    return sparse.diags(1.0 / np.asarray(m.sum(axis=1)).ravel()) @ m


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
        data = _overlap_weights(raster.height, h, nrows, big) @ data
    if abs(w - big) > 1e-9 * big:                       # columns are finer: average them
        data = (_overlap_weights(raster.width, w, ncols, big) @ data.T).T
    transform = (big, 0.0, raster.origin_x, 0.0, -big, raster.origin_y)
    return Raster(data.astype(np.float32), transform, raster.crs, raster.nodata)
