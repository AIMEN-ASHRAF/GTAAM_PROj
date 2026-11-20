"""Distances along a line. Geographic coordinates use the WGS84 ellipsoid (Vincenty)."""
from __future__ import annotations

import math

from core.raster.model import Raster
from core.raster.sampling import sample_bilinear

EARTH_RADIUS_M = 6_371_008.8


METRES_PER_UNIT = {
    "metres": 1.0,
    "kilometres": 1000.0,
    "feet": 0.3048,
    "miles": 1609.344,
}

UNIT_SYMBOLS = {"metres": "m", "kilometres": "km", "feet": "ft", "miles": "mi"}

def from_metres(value: float, unit: str) -> float:
    """Convert a length in metres to the chosen unit."""
    try:
        return value / METRES_PER_UNIT[unit.lower()]
    except KeyError:
        raise ValueError(f"Unknown unit: {unit}") from None

def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


WGS84_A = 6_378_137.0               # equator radius (m)
WGS84_F = 1 / 298.257223563         # how squashed the Earth is
WGS84_B = (1 - WGS84_F) * WGS84_A   # pole radius (m)


def geodesic_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Shortest distance in metres over the WGS84 ellipsoid (Vincenty inverse).

    Matches ArcMap's GEODESIC length. Falls back to haversine for nearly
    opposite points, where the iteration does not settle.
    """
    return geodesic_inverse(lon1, lat1, lon2, lat2)[0]


def geodesic_inverse(lon1: float, lat1: float, lon2: float, lat2: float) -> tuple[float, float]:
    """(distance in metres, starting direction in radians clockwise from north).

    The direction is what geodesic_direct needs to walk along the same line.
    """
    if lon1 == lon2 and lat1 == lat2:
        return 0.0, 0.0
    L = math.radians(lon2 - lon1)
    U1 = math.atan((1 - WGS84_F) * math.tan(math.radians(lat1)))
    U2 = math.atan((1 - WGS84_F) * math.tan(math.radians(lat2)))
    sinU1, cosU1 = math.sin(U1), math.cos(U1)
    sinU2, cosU2 = math.sin(U2), math.cos(U2)

    lam = L
    for _ in range(200):
        sin_lam, cos_lam = math.sin(lam), math.cos(lam)
        sin_sigma = math.sqrt((cosU2 * sin_lam) ** 2
                              + (cosU1 * sinU2 - sinU1 * cosU2 * cos_lam) ** 2)
        if sin_sigma == 0:
            return 0.0, 0.0
        cos_sigma = sinU1 * sinU2 + cosU1 * cosU2 * cos_lam
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alpha = cosU1 * cosU2 * sin_lam / sin_sigma
        cos2_alpha = 1 - sin_alpha ** 2
        cos_2sm = (cos_sigma - 2 * sinU1 * sinU2 / cos2_alpha) if cos2_alpha else 0.0
        C = WGS84_F / 16 * cos2_alpha * (4 + WGS84_F * (4 - 3 * cos2_alpha))
        lam_prev = lam
        lam = L + (1 - C) * WGS84_F * sin_alpha * (
            sigma + C * sin_sigma * (cos_2sm + C * cos_sigma * (-1 + 2 * cos_2sm ** 2)))
        if abs(lam - lam_prev) < 1e-12:
            break
    else:
        p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
        bearing = math.atan2(math.sin(dl) * math.cos(p2),
                             math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))
        return haversine(lon1, lat1, lon2, lat2), bearing

    u2 = cos2_alpha * (WGS84_A ** 2 - WGS84_B ** 2) / WGS84_B ** 2
    A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    d_sigma = B * sin_sigma * (cos_2sm + B / 4 * (
        cos_sigma * (-1 + 2 * cos_2sm ** 2)
        - B / 6 * cos_2sm * (-3 + 4 * sin_sigma ** 2) * (-3 + 4 * cos_2sm ** 2)))
    azimuth = math.atan2(cosU2 * sin_lam, cosU1 * sinU2 - sinU1 * cosU2 * cos_lam)
    return WGS84_B * A * (sigma - d_sigma), azimuth


def geodesic_direct(lon1: float, lat1: float, azimuth: float, distance: float) -> tuple[float, float]:
    """Walk `distance` metres from a point along a geodesic (Vincenty direct).

    azimuth is in radians clockwise from north. Returns (lon, lat) in degrees.
    """
    f, a, b = WGS84_F, WGS84_A, WGS84_B
    sin_a1, cos_a1 = math.sin(azimuth), math.cos(azimuth)
    tanU1 = (1 - f) * math.tan(math.radians(lat1))
    cosU1 = 1 / math.sqrt(1 + tanU1 ** 2)
    sinU1 = tanU1 * cosU1
    sigma1 = math.atan2(tanU1, cos_a1)
    sin_alpha = cosU1 * sin_a1
    cos2_alpha = 1 - sin_alpha ** 2
    u2 = cos2_alpha * (a ** 2 - b ** 2) / b ** 2
    A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    sigma = distance / (b * A)
    for _ in range(200):
        cos_2sm = math.cos(2 * sigma1 + sigma)
        sin_s, cos_s = math.sin(sigma), math.cos(sigma)
        d_sigma = B * sin_s * (cos_2sm + B / 4 * (
            cos_s * (-1 + 2 * cos_2sm ** 2)
            - B / 6 * cos_2sm * (-3 + 4 * sin_s ** 2) * (-3 + 4 * cos_2sm ** 2)))
        prev, sigma = sigma, distance / (b * A) + d_sigma
        if abs(sigma - prev) < 1e-12:
            break
    cos_2sm = math.cos(2 * sigma1 + sigma)
    sin_s, cos_s = math.sin(sigma), math.cos(sigma)
    tmp = sinU1 * sin_s - cosU1 * cos_s * cos_a1
    lat2 = math.atan2(sinU1 * cos_s + cosU1 * sin_s * cos_a1,
                      (1 - f) * math.sqrt(sin_alpha ** 2 + tmp ** 2))
    lam = math.atan2(sin_s * sin_a1, cosU1 * cos_s - sinU1 * sin_s * cos_a1)
    C = f / 16 * cos2_alpha * (4 + f * (4 - 3 * cos2_alpha))
    L = lam - (1 - C) * f * sin_alpha * (
        sigma + C * sin_s * (cos_2sm + C * cos_s * (-1 + 2 * cos_2sm ** 2)))
    return lon1 + math.degrees(L), math.degrees(lat2)


def flat_distance(p, q) -> float:
    """Straight-line distance between two points on a flat map (metres)."""
    dx = q[0] - p[0]      # how far east
    dy = q[1] - p[1]      # how far north
    return math.sqrt(dx ** 2 + dy ** 2)


def segment_length(p, q, geographic: bool) -> float:
    if geographic:
        return geodesic_distance(p[0], p[1], q[0], q[1])
    return flat_distance(p, q)


def path_length(points, geographic: bool, unit: str = "metres") -> dict:
    if len(points) < 2:
        raise ValueError("Need at least two points.")
    segs = [segment_length(points[i], points[i + 1], geographic) for i in range(len(points) - 1)]
    segs = [from_metres(s, unit) for s in segs]
    return {"total": sum(segs), "segments": segs, "unit": UNIT_SYMBOLS[unit.lower()]}


def snap_to_cell_centres(raster: Raster, points) -> list[tuple[float, float]]:
    """Move each point to the centre of the raster cell it falls in."""
    rows, cols = raster.xy_to_rowcol([p[0] for p in points], [p[1] for p in points])
    xs, ys = raster.rowcol_to_xy(rows, cols)
    return [(float(x), float(y)) for x, y in zip(xs, ys)]


def elevation_change(raster: Raster, points) -> dict | None:
    """Height of the last point minus the first, or None if either is off the DEM."""
    xs = [points[0][0], points[-1][0]]
    ys = [points[0][1], points[-1][1]]
    z0, z1 = (float(v) for v in sample_bilinear(raster, xs, ys))
    if math.isnan(z0) or math.isnan(z1):
        return None
    return {"start": z0, "end": z1, "difference": z1 - z0}