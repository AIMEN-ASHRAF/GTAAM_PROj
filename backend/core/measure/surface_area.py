"""Surface (3D) area of a DEM inside a polygon.

A flat polygon area ignores hills. Here every square of four neighbouring cell centres is split
into two triangles, each triangle is given its real tilted size from the cell heights, and the
triangles whose middle lies inside the polygon are added up. Steeper ground gives a bigger number.
The edge follows whole cells, so for a very small polygon the result is only approximate.
"""
from __future__ import annotations

import numpy as np

from core.raster.crs import is_geographic, metres_per_degree
from core.raster.model import Raster

MAX_CELLS = 40_000_000          # safety cap on how many cells one request may touch


def _inside(px, py, ring) -> np.ndarray:
    """Even-odd test: which of the points (px, py) lie inside the polygon ring."""
    inside = np.zeros(px.shape, bool)
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if y1 == y2:
            continue
        crosses = (py < y1) != (py < y2)
        x_at = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
        inside ^= crosses & (px < x_at)
    return inside


def surface_area(raster: Raster, polygon) -> dict:
    ring = [(float(x), float(y)) for x, y in polygon]
    if len(ring) < 3:
        raise ValueError("The polygon needs at least three corners.")
    xs, ys = zip(*ring)
    r_a, c_a = raster.xy_to_rowcol(min(xs), max(ys))
    r_b, c_b = raster.xy_to_rowcol(max(xs), min(ys))
    r0, r1 = max(int(r_a), 0), min(int(r_b), raster.height - 2)
    c0, c1 = max(int(c_a), 0), min(int(c_b), raster.width - 2)
    if r1 < r0 or c1 < c0:
        raise ValueError("The polygon is outside the DEM.")
    if (r1 - r0 + 1) * (c1 - c0 + 1) > MAX_CELLS:
        raise ValueError("The polygon covers too many cells for a surface area. Draw a smaller one.")

    z = raster.data[r0:r1 + 2, c0:c1 + 2].astype(np.float64)
    z00, z01, z10, z11 = z[:-1, :-1], z[:-1, 1:], z[1:, :-1], z[1:, 1:]
    ok = np.isfinite(z00) & np.isfinite(z01) & np.isfinite(z10) & np.isfinite(z11)

    rows = np.arange(r0, r1 + 1)
    cols = np.arange(c0, c1 + 1)
    cx = raster.origin_x + (cols + 1.0) * raster.pixel_w            # middle of each square of 4 centres
    cy = raster.origin_y - (rows + 1.0) * raster.pixel_h
    mask = _inside(*np.meshgrid(cx, cy), ring) & ok

    if is_geographic(raster):                                      # metres per cell shrink towards the poles
        dx = np.array([metres_per_degree(float(lat))[0] for lat in cy]) * raster.pixel_w
        dy = np.array([metres_per_degree(float(lat))[1] for lat in cy]) * raster.pixel_h
    else:
        dx = np.full(cy.shape, raster.pixel_w)
        dy = np.full(cy.shape, raster.pixel_h)
    dx, dy = dx[:, None], dy[:, None]

    def tri(ax, ay, az, bx, by, bz, cx_, cy_, cz):
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx_ - ax, cy_ - ay, cz - az
        return 0.5 * np.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2)

    zero = np.zeros_like(z00)
    t1 = tri(0, 0, z00, dx + zero, zero, z01, zero, dy + zero, z10)      # corners A, B, C
    t2 = tri(dx + zero, zero, z01, dx + zero, dy + zero, z11, zero, dy + zero, z10)   # B, D, C
    surface = float(np.where(mask, t1 + t2, 0.0).sum())
    flat = float((mask * (dx * dy)).sum())
    return {
        "surface_area_m2": surface,
        "flat_cell_area_m2": flat,
        "surface_to_flat_ratio": (surface / flat) if flat > 0 else None,
        "cells_used": int(mask.sum()),
    }
