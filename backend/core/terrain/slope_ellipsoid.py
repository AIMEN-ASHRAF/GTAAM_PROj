"""Slope measured on the WGS84 ellipsoid in 3D, the way ArcMap's GEODESIC method does it.

Idea, step by step (same as the ArcGIS "How Slope works" page):
  1. Turn each cell (latitude, longitude, height) into a 3D point X, Y, Z (ECEF) on the ellipsoid.
  2. For each 3x3 window, express the 9 points in a local frame at the centre cell
     (east, north, up, where "up" is the ellipsoid's own vertical direction there).
  3. Fit a plane  up = a*east + b*north + c  through the 9 points by least squares.
  4. Slope = angle between that plane and the horizontal = arctan(sqrt(a^2 + b^2)).

Only latitude matters (longitude just rotates the whole picture), so every cell in a row
shares the same geometry; heights are the only thing that changes along a row.
Works on rasters in degrees (a geographic CRS). Edges use repeated border cells, like the other tools,
and a missing (NaN) neighbour takes the centre cell's height, like ArcMap. A cell with no data of its own stays NaN.
"""
from __future__ import annotations

import numpy as np

_A = 6_378_137.0                     # WGS84 semi-major axis (m)
_F = 1 / 298.257223563
_E2 = _F * (2 - _F)                  # first eccentricity squared
_OFFSETS = [(di, dj) for di in (-1, 0, 1) for dj in (-1, 0, 1)]


def ellipsoid_slope(dem: np.ndarray, top_lat: float, dlat: float, dlon: float,
                    units: str = "degrees", chunk_rows: int = 64, drop_border: bool = False) -> np.ndarray:
    """Slope of every cell. top_lat = latitude of the raster's top edge, dlat/dlon = cell height/width in degrees.

    drop_border=True leaves the outermost ring of cells empty, as ArcMap's GEODESIC slope does (checked on
    three tiles: ArcMap returns (rows-2) x (cols-2) valid cells)."""
    if units not in ("degrees", "percent"):
        raise ValueError("units must be 'degrees' or 'percent'")
    gx, gn = ellipsoid_gradients(dem, top_lat, dlat, dlon, chunk_rows)
    rise = np.hypot(gx, gn)
    out = (np.degrees(np.arctan(rise)) if units == "degrees" else rise * 100.0).astype(np.float32)
    if drop_border:
        out[0, :] = out[-1, :] = np.nan
        out[:, 0] = out[:, -1] = np.nan
    return out


def ellipsoid_gradients(dem: np.ndarray, top_lat: float, dlat: float, dlon: float,
                        chunk_rows: int = 64) -> tuple[np.ndarray, np.ndarray]:
    """East and north rise-per-metre (a, b of the fitted plane) for every cell, measured on the ellipsoid.
    Slope uses their length; aspect uses their direction."""
    rows, cols = dem.shape
    z = np.pad(dem.astype(np.float64), 1, mode="edge")
    lat = np.radians(top_lat - (np.arange(-1, rows + 1) + 0.5) * dlat)      # row i is index i + 1
    sin_p, cos_p = np.sin(lat), np.cos(lat)
    n_rad = _A / np.sqrt(1.0 - _E2 * sin_p ** 2)                            # east-west radius of curvature
    dl = np.radians(dlon)
    gx = np.empty((rows, cols), np.float64)
    gn = np.empty((rows, cols), np.float64)

    for r0 in range(0, rows, chunk_rows):
        r1 = min(rows, r0 + chunk_rows)
        n = r1 - r0
        c_idx = slice(r0 + 1, r1 + 1)
        sc, cc = sin_p[c_idx, None], cos_p[c_idx, None]                      # centre-row latitude terms, (n, 1)

        h0 = z[c_idx, 1: cols + 1]                                           # centre heights (NaN = no data)

        def point(di: int, dj: int):
            """ECEF position of the neighbour at (di, dj), centre cell at longitude 0."""
            rr = slice(r0 + 1 + di, r1 + 1 + di)
            h = z[rr, 1 + dj: cols + 1 + dj]
            h = np.where(np.isnan(h), h0, h)             # like ArcMap: a missing neighbour takes the centre height
            s, c, nr = sin_p[rr, None], cos_p[rr, None], n_rad[rr, None]
            lam = dj * dl
            x = (nr + h) * c * np.cos(lam)
            y = (nr + h) * c * np.sin(lam)
            zz = (nr * (1.0 - _E2) + h) * s
            return x, y, zz

        x0, y0, z0 = point(0, 0)
        e_list, n_list, u_list = [], [], []
        for di, dj in _OFFSETS:
            x, y, zz = point(di, dj)
            dx_, dy_, dz_ = x - x0, y - y0, zz - z0
            e_list.append(dy_)                                               # east  = (0, 1, 0)
            n_list.append(-sc * dx_ + cc * dz_)                              # north = (-sin p, 0, cos p)
            u_list.append(cc * dx_ + sc * dz_)                               # up    = ( cos p, 0, sin p)
        E, Nn, U = (np.stack(v, axis=-1) for v in (e_list, n_list, u_list))  # (n, cols, 9)

        # least squares for u = a e + b n + c  (normal equations, one 3x3 per cell)
        ones = np.ones_like(E)
        D = np.stack([E, Nn, ones], axis=-1)                                 # (n, cols, 9, 3)
        Dt = np.swapaxes(D, -1, -2)
        sol = np.linalg.solve(Dt @ D, Dt @ U[..., None])[..., 0]
        gx[r0:r1], gn[r0:r1] = sol[..., 0], sol[..., 1]
    return gx, gn
