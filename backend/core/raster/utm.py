"""Pick the UTM zone for a raster and move a degree raster into it."""
from __future__ import annotations

import re

from .crs import is_geographic
from .model import Raster
from .reproject import METHODS, reproject

ZONE_TEXT = re.compile(r"^([1-9]|[1-5][0-9]|60)[NS]$")
SOUTH_LIMIT, NORTH_LIMIT = -80.0, 84.0           # UTM is only defined between 80 S and 84 N


def utm_epsg(lon: float, lat: float) -> int:
    """EPSG code of the WGS 84 / UTM zone that contains a point (Norway and Svalbard exceptions are ignored)."""
    zone = min(60, max(1, int((lon + 180.0) // 6) + 1))
    return (32600 if lat >= 0 else 32700) + zone


def zone_label(epsg: int) -> str:
    """32643 -> '43N', 32743 -> '43S'."""
    return f"{epsg % 100}{'N' if epsg < 32700 else 'S'}"


def centre(raster: Raster) -> tuple[float, float]:
    x0, y0, x1, y1 = raster.bounds
    return (x0 + x1) / 2.0, (y0 + y1) / 2.0


def choose_zone(raster: Raster, zone_text: str = "auto") -> int:
    """The EPSG code to use: the zone the user typed ('43N'), or the one under the raster's centre."""
    zone_text = (zone_text or "auto").strip().upper()
    if zone_text == "AUTO":
        lon, lat = centre(raster)
        if not SOUTH_LIMIT <= lat <= NORTH_LIMIT:
            raise ValueError("UTM is only defined between 80 S and 84 N, so this raster cannot be analysed "
                             "in UTM. Turn off 'Analyze in UTM' for it.")
        return utm_epsg(lon, lat)
    if not ZONE_TEXT.match(zone_text):
        raise ValueError("The UTM zone must be 'auto' or a number from 1 to 60 followed by N or S, e.g. '43N'.")
    return (32600 if zone_text[-1] == "N" else 32700) + int(zone_text[:-1])


def to_utm(raster: Raster, zone_text: str = "auto", method: str = "bilinear") -> tuple[Raster, int]:
    """The raster moved into UTM (a metre grid). A raster that is already projected is returned as it is."""
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    if not is_geographic(raster):
        return raster, 0
    epsg = choose_zone(raster, zone_text)
    return reproject(raster, epsg, method), epsg
