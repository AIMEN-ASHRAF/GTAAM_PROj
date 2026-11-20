"""Polygon area and perimeter.

Geographic coordinates: area on the WGS84 ellipsoid with edges that follow geodesics (the
shortest line over the surface), the same idea as ArcMap's GEODESIC area. Projected
coordinates: flat area in map units squared (metres), like ArcMap's PLANAR area.
"""
from __future__ import annotations

import math

from .distance import WGS84_A, WGS84_F, geodesic_direct, geodesic_inverse

SQUARE_METRES_PER_UNIT = {
    "square metres": 1.0,
    "hectares": 10_000.0,
    "square kilometres": 1_000_000.0,
    "acres": 4046.8564224,
    "square miles": 2_589_988.110336,
}
UNIT_SYMBOLS = {"square metres": "m\u00b2", "hectares": "ha", "square kilometres": "km\u00b2",
                "acres": "ac", "square miles": "mi\u00b2"}


def from_square_metres(value: float, unit: str) -> float:
    try:
        return value / SQUARE_METRES_PER_UNIT[unit.lower()]
    except KeyError:
        raise ValueError(f"Unknown area unit: {unit}") from None


def auto_unit(area_m2: float) -> str:
    """Square metres below one hectare, hectares below one square kilometre, otherwise km2."""
    if area_m2 < 10_000:
        return "square metres"
    return "hectares" if area_m2 < 1_000_000 else "square kilometres"


_E2 = WGS84_F * (2 - WGS84_F)          # eccentricity squared
_E = math.sqrt(_E2)


def _q(sin_phi: float) -> float:
    """Equal-area latitude function: the area between the equator and a latitude is
    proportional to q, so integrating q along the border gives the area exactly."""
    return (1 - _E2) * (sin_phi / (1 - _E2 * sin_phi ** 2)
                        - math.log((1 - _E * sin_phi) / (1 + _E * sin_phi)) / (2 * _E))


def _ring(polygon) -> list[tuple[float, float]]:
    pts = [(float(p[0]), float(p[1])) for p in polygon]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()                                   # a closed ring repeats its first point
    if len(pts) < 3:
        raise ValueError("A polygon needs at least three points.")
    return pts


def _shoelace(pts) -> float:
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def geodesic_polygon(polygon, max_step: float = 500.0) -> tuple[float, float]:
    """(area in m2, perimeter in m) of a lon/lat polygon on the WGS84 ellipsoid.

    Each edge is split into steps of at most max_step metres along the geodesic, and the
    equal-area function q is added up along the border. Polygons that contain a pole
    are not supported.
    """
    pts = _ring(polygon)
    perimeter = 0.0
    total = 0.0
    for i in range(len(pts)):
        lon1, lat1 = pts[i]
        lon2, lat2 = pts[(i + 1) % len(pts)]
        dist, az = geodesic_inverse(lon1, lat1, lon2, lat2)
        perimeter += dist
        steps = max(1, math.ceil(dist / max_step))
        prev_lon, prev_q = lon1, _q(math.sin(math.radians(lat1)))
        for j in range(1, steps + 1):
            lon, lat = (lon2, lat2) if j == steps else geodesic_direct(lon1, lat1, az, dist * j / steps)
            q = _q(math.sin(math.radians(lat)))
            d_lon = math.radians((lon - prev_lon + 180.0) % 360.0 - 180.0)   # shortest way round
            total += d_lon * (prev_q + q)
            prev_lon, prev_q = lon, q
    return WGS84_A ** 2 / 4 * abs(total), perimeter


def polygon_area(polygon, geographic: bool) -> dict:
    pts = _ring(polygon)
    if geographic:
        m2, perimeter = geodesic_polygon(pts)
    else:
        m2 = _shoelace(pts)
        perimeter = sum(math.dist(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))
    return {"area_m2": m2, "area_km2": m2 / 1e6, "area_ha": m2 / 1e4,
            "perimeter_m": perimeter, "perimeter_km": perimeter / 1000.0,
            "method": "geodesic" if geographic else "planar"}
