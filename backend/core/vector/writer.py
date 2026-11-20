"""Save a GeoJSON FeatureCollection as GeoJSON, Shapefile, GeoPackage or CSV (points)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

FORMATS = {                     # name -> (file suffix, needs fiona)
    "geojson": (".geojson", False),
    "shapefile": (".shp", True),
    "gpkg": (".gpkg", True),
    "csv": (".csv", False),
}
_MULTI = {"Point": "MultiPoint", "LineString": "MultiLineString", "Polygon": "MultiPolygon"}


def _geom_types(features: list[dict]) -> set[str]:
    return {f["geometry"]["type"] for f in features if f.get("geometry")}


def _schema_type(values) -> str:
    kinds = {type(v) for v in values if v is not None}
    if kinds <= {bool}:
        return "bool" if kinds else "str"
    if kinds <= {int, bool}:
        return "int"
    if kinds <= {int, float, bool}:
        return "float"
    return "str"


def write_vector(data: dict, path: str | Path, fmt: str, crs: str | None = "EPSG:4326") -> str:
    if fmt not in FORMATS:
        raise ValueError(f"Unknown format '{fmt}'. Choose one of: {', '.join(FORMATS)}.")
    features = [f for f in data.get("features", []) if f.get("geometry")]
    if not features:
        raise ValueError("The layer has no features to export.")
    suffix, needs_fiona = FORMATS[fmt]
    p = Path(path)
    if p.suffix.lower() != suffix:
        p = p.with_suffix(suffix)
    p.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "geojson":
        p.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
        return str(p)
    if fmt == "csv":
        return _write_points_csv(features, p)

    try:
        import fiona
        from fiona.crs import CRS
    except ImportError as exc:                       # pragma: no cover
        raise ImportError("Saving Shapefile / GeoPackage needs fiona: pip install fiona") from exc

    types = _geom_types(features)
    families = {_MULTI.get(t, t) for t in types}
    promote = False
    if len(types) == 1:
        geom = next(iter(types))
    elif len(families) == 1:                         # e.g. Polygon + MultiPolygon -> all MultiPolygon
        geom, promote = next(iter(families)), True
    elif fmt == "gpkg":
        geom = "Unknown"
    else:
        raise ValueError("A Shapefile holds one geometry type, but this layer mixes "
                         f"{', '.join(sorted(types))}. Use GeoPackage instead.")
    names: list[str] = []
    for f in features:
        for k in (f.get("properties") or {}):
            if k not in names:
                names.append(k)
    schema_props = {}
    for k in names:
        short = k[:10] if fmt == "shapefile" else k
        schema_props[short] = _schema_type([(f.get("properties") or {}).get(k) for f in features])
    schema = {"geometry": geom, "properties": schema_props}
    driver = "ESRI Shapefile" if fmt == "shapefile" else "GPKG"

    def fix(g: dict) -> dict:
        if promote and g["type"] in _MULTI:
            return {"type": _MULTI[g["type"]], "coordinates": [g["coordinates"]]}
        return g

    with fiona.open(p, "w", driver=driver, schema=schema, crs=CRS.from_user_input(crs) if crs else None) as dst:
        for f in features:
            props = f.get("properties") or {}
            dst.write({"geometry": fix(f["geometry"]),
                       "properties": {(k[:10] if fmt == "shapefile" else k): props.get(k) for k in names}})
    return str(p)


def _write_points_csv(features: list[dict], p: Path) -> str:
    if _geom_types(features) != {"Point"}:
        raise ValueError("CSV export works for point layers only. Use GeoJSON, Shapefile or GeoPackage.")
    names: list[str] = []
    for f in features:
        for k in (f.get("properties") or {}):
            if k not in names:
                names.append(k)
    with open(p, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["longitude", "latitude", *names])
        for f in features:
            x, y = f["geometry"]["coordinates"][:2]
            props = f.get("properties") or {}
            w.writerow([x, y, *[props.get(k) for k in names]])
    return str(p)
