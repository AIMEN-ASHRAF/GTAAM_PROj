"""Just enough coordinate-system knowledge to get real-world (metre) cell sizes.

Slope, aspect, hillshade and curvature need cell size in metres. AW3D30 tiles are in
degrees (EPSG:4326), so a pixel is ~30 m tall but narrower than 30 m east-west.
"""
from __future__ import annotations

import math

import numpy as np

from .model import Raster

_GEOGRAPHIC_EPSG = {4326, 4269, 4258, 4283, 4167, 4612, 4979, 4617, 4019, 4030}
M_PER_DEG_LAT = 110_574.0       # equator value, kept for the (small-polygon) area tool
M_PER_DEG_LON_EQ = 111_320.0


def metres_per_degree(lat_deg: float) -> tuple[float, float]:
    """(metres per degree of longitude, metres per degree of latitude) at a latitude.

    Standard WGS84 series. The earth is slightly squashed, so a degree of latitude is
    ~110.6 km at the equator and ~111.7 km at the poles; a degree of longitude shrinks
    with cos(latitude). Using one fixed number would tilt every slope a little.
    """
    p = math.radians(lat_deg)
    lon = 111_412.84 * math.cos(p) - 93.5 * math.cos(3 * p) + 0.118 * math.cos(5 * p)
    lat = 111_132.954 - 559.822 * math.cos(2 * p) + 1.175 * math.cos(4 * p)
    return lon, lat


def metres_per_degree_array(lat_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """metres_per_degree for many latitudes at once (same series, numpy arrays)."""
    p = np.radians(np.asarray(lat_deg, dtype=np.float64))
    lon = 111_412.84 * np.cos(p) - 93.5 * np.cos(3 * p) + 0.118 * np.cos(5 * p)
    lat = 111_132.954 - 559.822 * np.cos(2 * p) + 1.175 * np.cos(4 * p)
    return lon, lat


def is_geographic(raster: Raster) -> bool:
    crs = (raster.crs or "").strip()
    up = crs.upper()
    if up.startswith("EPSG:"):
        try:
            return int(up.split(":")[1]) in _GEOGRAPHIC_EPSG
        except ValueError:
            pass
    if "PROJCS" in up or "PROJCRS" in up:
        return False
    if "GEOGCS" in up or "GEOGCRS" in up:
        return True
    # unknown: guess from the extent
    minx, miny, maxx, maxy = raster.bounds
    return max(abs(minx), abs(maxx)) <= 180 and max(abs(miny), abs(maxy)) <= 90


def epsg_code(raster: Raster) -> int | None:
    up = (raster.crs or "").upper()
    if up.startswith("EPSG:"):
        try:
            return int(up.split(":")[1])
        except ValueError:
            return None
    return None


def grid_north_offset(raster: Raster) -> float:
    """Angle (degrees, clockwise) from true north to the map grid's north at the raster's centre.

    On a projected map (UTM ...) 'up' on the screen is grid north, which is not exactly true north:
    the meridians lean a little, by up to a few degrees away from the zone's centre line. A direction
    measured from true north = the same direction measured from grid north minus this angle.
    Degree rasters have no such offset (north is up), so 0 is returned; so it is if it cannot be worked out.
    """
    if is_geographic(raster) or not raster.crs:
        return 0.0
    try:
        from rasterio.warp import transform
        minx, miny, maxx, maxy = raster.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        lon, lat = transform(raster.crs, "EPSG:4326", [cx], [cy])
        # walk 0.001 deg due north along the meridian and see which way that is on the grid
        x, y = transform("EPSG:4326", raster.crs, [lon[0], lon[0]], [lat[0], lat[0] + 0.001])
        return math.degrees(math.atan2(x[1] - x[0], y[1] - y[0]))
    except Exception:       # unknown CRS or no PROJ data: leave directions as they are
        return 0.0


def cell_size_meters(raster: Raster) -> tuple[float, float]:
    """(dx, dy) of one pixel in metres."""
    if is_geographic(raster):
        lat = (raster.bounds[1] + raster.bounds[3]) / 2
        m_lon, m_lat = metres_per_degree(lat)
        return raster.pixel_w * m_lon, raster.pixel_h * m_lat
    return raster.pixel_w, raster.pixel_h


def cell_size_by_row(raster: Raster) -> tuple[float | np.ndarray, float | np.ndarray]:
    """(dx, dy) of a pixel in metres, ready to use in slope, aspect, hillshade and curvature.

    A projected raster (UTM ...) has one size for the whole grid, returned as two floats.

    A degree raster does not: a degree of longitude gets shorter toward the pole, so a
    pixel is narrower in the top row than in the bottom row. Here dx and dy are returned
    per row, each an array of shape (rows, 1), worked out at that row's own latitude, so
    they line up with the (rows, columns) elevation grid. A single value taken at the
    middle of the tile (cell_size_meters) is still used where one number is enough.
    """
    if not is_geographic(raster):
        return raster.pixel_w, raster.pixel_h
    lat = raster.origin_y - (np.arange(raster.height) + 0.5) * raster.pixel_h
    m_lon, m_lat = metres_per_degree_array(lat)
    return (raster.pixel_w * m_lon)[:, None], (raster.pixel_h * m_lat)[:, None]
