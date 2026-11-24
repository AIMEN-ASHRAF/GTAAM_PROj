"""Plain-words description of a raster's coordinate system for the Properties table.

Gives the kind (Geographic / Projected / UTM), the units, the datum and the
EPSG code, so the panel shows more than just "EPSG:4326".
Uses pyproj when it is installed; otherwise falls back to a small built-in rule
that covers WGS 84 and the UTM zones (the cases this app produces itself).
"""
from __future__ import annotations

DASH = "—"


def _epsg_number(crs_text: str | None) -> int | None:
    if not crs_text:
        return None
    text = crs_text.strip()
    if text.upper().startswith("EPSG:"):
        text = text.split(":", 1)[1]
    return int(text) if text.isdigit() else None


def _utm_zone(epsg: int | None) -> str | None:
    if epsg is None:
        return None
    if 32601 <= epsg <= 32660:
        return f"{epsg - 32600}N"
    if 32701 <= epsg <= 32760:
        return f"{epsg - 32700}S"
    return None


def describe_crs(crs_text: str | None) -> list[tuple[str, str]]:
    """Rows for the Properties table, in display order."""
    epsg = _epsg_number(crs_text)
    if not crs_text:
        return [("Coordinate system", DASH), ("Type", DASH), ("EPSG", DASH)]

    name = datum = units = kind = projection = None
    try:  # richest answer when pyproj is available
        from pyproj import CRS

        crs = CRS.from_user_input(crs_text)
        name = crs.name
        datum = crs.datum.name if crs.datum else None
        axis = crs.axis_info[0].unit_name if crs.axis_info else None
        units = {"metre": "metres", "degree": "degrees"}.get(axis, axis)
        if crs.is_geographic:
            kind = "Geographic"
        elif crs.is_projected:
            kind = "Projected"
            projection = crs.coordinate_operation.method_name if crs.coordinate_operation else None
    except Exception:
        pass

    zone = _utm_zone(epsg)
    if kind is None:  # built-in fallback
        if epsg == 4326:
            name, datum, units, kind = "WGS 84", "World Geodetic System 1984", "degrees", "Geographic"
        elif epsg == 3857:
            name, datum, units, kind = "WGS 84 / Pseudo-Mercator", "World Geodetic System 1984", "metres", "Projected"
            projection = "Popular Visualisation Pseudo-Mercator"
        elif zone:
            name = f"WGS 84 / UTM zone {zone}"
            datum, units, kind = "World Geodetic System 1984", "metres", "Projected"
        else:
            name, kind = crs_text, "Unknown"

    if zone:
        kind = f"Projected (UTM zone {zone})"
        projection = "Transverse Mercator"
    elif kind == "Geographic":
        kind = "Geographic (latitude / longitude)"

    rows = [("Coordinate system", name or crs_text), ("Type", kind)]
    if projection:
        rows.append(("Projection", projection))
    rows += [("Datum", datum or DASH), ("Units", units or DASH),
             ("EPSG", str(epsg) if epsg is not None else DASH)]
    return rows


def pixel_unit(crs_text: str | None) -> str:
    """' °' for degree rasters, ' m' otherwise."""
    kind = dict(describe_crs(crs_text)).get("Type", "")
    return " °" if kind.startswith("Geographic") else " m"
