"""Read raster values at arbitrary coordinates."""
from __future__ import annotations

import numpy as np

from .model import Raster


def sample_nearest(raster: Raster, xs, ys) -> np.ndarray:
    xs, ys = np.atleast_1d(np.asarray(xs, float)), np.atleast_1d(np.asarray(ys, float))
    row, col = raster.xy_to_rowcol(xs, ys)
    inside = (row >= 0) & (row < raster.height) & (col >= 0) & (col < raster.width)
    out = np.full(xs.shape, np.nan, dtype=np.float64)
    out[inside] = raster.data[row[inside], col[inside]]
    return out


def _square_cell_bilinear(raster: Raster, xs, ys) -> np.ndarray:
    """Bilinear reading the way ArcMap does it on cells that are not square.

    ArcMap treats the raster as if every cell had the size of the smaller side
    (a 2 x 1 arc-second cell becomes two 1 x 1 cells with the same height), then
    interpolates. Verified against Stack Profile on the 65N tile (0.00002 m).
    """
    pw, ph = abs(raster.pixel_w), abs(raster.pixel_h)
    h = min(pw, ph)
    fc = (xs - raster.origin_x) / h - 0.5
    fr = (raster.origin_y - ys) / h - 0.5
    c0, r0 = np.floor(fc).astype(int), np.floor(fr).astype(int)
    tc, tr = fc - c0, fr - r0
    nc, nr = int(round(raster.width * pw / h)), int(round(raster.height * ph / h))
    inside = (r0 >= 0) & (r0 < nr - 1) & (c0 >= 0) & (c0 < nc - 1)
    out = np.full(xs.shape, np.nan, dtype=np.float64)
    r, c = r0[inside], c0[inside]
    def src(v, size):                      # virtual cell -> real cell
        return np.minimum(((v + 0.5) * h / size).astype(int), (raster.width if size == pw else raster.height) - 1)
    d = raster.data
    r_a, r_b, c_a, c_b = src(r, ph), src(r + 1, ph), src(c, pw), src(c + 1, pw)
    top = d[r_a, c_a] * (1 - tc[inside]) + d[r_a, c_b] * tc[inside]
    bot = d[r_b, c_a] * (1 - tc[inside]) + d[r_b, c_b] * tc[inside]
    out[inside] = top * (1 - tr[inside]) + bot * tr[inside]
    return out


def sample_bilinear(raster: Raster, xs, ys, square_cells: bool = False) -> np.ndarray:
    xs, ys = np.atleast_1d(np.asarray(xs, float)), np.atleast_1d(np.asarray(ys, float))
    if square_cells and not np.isclose(abs(raster.pixel_w), abs(raster.pixel_h)):
        return _square_cell_bilinear(raster, xs, ys)
    # continuous pixel coordinates where pixel centres sit on whole numbers
    fc = (xs - raster.origin_x) / raster.pixel_w - 0.5
    fr = (raster.origin_y - ys) / raster.pixel_h - 0.5
    r0, c0 = np.floor(fr).astype(int), np.floor(fc).astype(int)
    tr, tc = fr - r0, fc - c0
    inside = (r0 >= 0) & (r0 < raster.height - 1) & (c0 >= 0) & (c0 < raster.width - 1)
    out = np.full(xs.shape, np.nan, dtype=np.float64)
    r, c = r0[inside], c0[inside]
    d = raster.data
    top = d[r, c] * (1 - tc[inside]) + d[r, c + 1] * tc[inside]
    bot = d[r + 1, c] * (1 - tc[inside]) + d[r + 1, c + 1] * tc[inside]
    out[inside] = top * (1 - tr[inside]) + bot * tr[inside]
    return out
