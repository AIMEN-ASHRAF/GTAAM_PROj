"""Analysis tab logic. Finds the layer, calls core/, packages the answer."""
from __future__ import annotations

from typing import Callable

import numpy as np

from core.measure import area as core_area
from core.measure import distance as core_distance
from core.measure import profile as core_profile
from core.measure.surface_area import surface_area
from core.raster.crs import cell_size_by_row, grid_north_offset, is_geographic
from core.raster.resample import square_cells
from core.raster.utm import to_utm, zone_label
from core.stats import histogram, layer_stats, nodata_check, outliers
from core.terrain.aspect import aspect_from_gradients, compute_aspect, flat_window_mask
from core.terrain.contours import contour_lines
from core.terrain.curvature import compute_curvature
from core.terrain.hillshade import compute_hillshade
from core.terrain.roughness import compute_roughness
from core.terrain.ruggedness import compute_ruggedness
from core.terrain.slope import compute_slope, plane_fit_gradients
from core.terrain.slope_ellipsoid import ellipsoid_gradients, ellipsoid_slope
from core.terrain.tpi import compute_tpi
from config import get_settings
from shared.errors import BadRequest
from shared.layer_store import Layer, add_raster_layer, add_vector_layer, get_raster_layer
from shared.project_store import project


def _layer(layer_id: str) -> Layer:
    return get_raster_layer(layer_id)


_utm_cache: dict[tuple, tuple] = {}          # (layer id, zone, resampling) -> (the DEM data it was made from, UTM raster)


def _source(layer_id: str) -> Layer:
    """The layer a terrain tool works on. With Project Settings > 'Analyze in UTM' on, a degree DEM is first
    moved to UTM (metres) and the tool runs on that copy; otherwise it is the layer itself."""
    src = _layer(layer_id)
    s = project.settings
    if not s.get("analyze_in_utm") or not is_geographic(src.raster):
        return src
    key = (src.id, s["utm_zone"], s["resampling"])
    hit = _utm_cache.get(key)
    if hit is None or hit[0] is not src.raster.data:
        try:
            utm_raster, epsg = to_utm(src.raster, s["utm_zone"], s["resampling"])
        except ValueError as e:
            raise BadRequest(str(e), code="utm_not_possible")
        if len(_utm_cache) >= 3:
            _utm_cache.pop(next(iter(_utm_cache)))
        hit = _utm_cache[key] = (src.raster.data, utm_raster, epsg)
    label = zone_label(hit[2])
    return Layer(name=f"{src.name} (UTM {label})", kind="raster", id=src.id, raster=hit[1], source=src.source,
                 meta={"analysis_utm": {"zone": label, "epsg": hit[2], "resampling": s["resampling"]}})


def _derive(src: Layer, data: np.ndarray, tool: str, label: str) -> dict:
    out = add_raster_layer(src.raster.with_data(data), f"{src.name} - {label}",
                           derived_from=src.id, tool=tool)
    if src.meta.get("analysis_utm"):
        out.meta["analysis_utm"] = src.meta["analysis_utm"]       # remember it was computed in UTM
    return {"layer": out.info(), "statistics": layer_stats.compute(data)}


# ---- measure ----
def _pixels_to_xy(raster, pixels) -> list[tuple[float, float]]:
    """Clicked cells (row, col) to map coordinates. (0, 0) is the raster's top-left corner."""
    rows = np.array([p[0] for p in pixels], float) - 0.5     # rowcol_to_xy gives cell centres,
    cols = np.array([p[1] for p in pixels], float) - 0.5     # so shift by half a cell
    xs, ys = raster.rowcol_to_xy(rows, cols)
    return [(float(x), float(y)) for x, y in zip(xs, ys)]


def distance(layer_id: str, points=None, pixels=None, units: str = "metres",
             include_elevation: bool = True, snap: bool = False) -> dict:
    r = _layer(layer_id).raster
    if points is None:
        points = _pixels_to_xy(r, pixels)
    if snap:
        points = core_distance.snap_to_cell_centres(r, points)
    geographic = is_geographic(r)
    elevation_unit = units
    if units == "auto":              # a short line in metres, a long one in kilometres; heights stay in metres
        total_m = core_distance.path_length(points, geographic, "metres")["total"]
        units = "kilometres" if total_m >= 1000 else "metres"
        elevation_unit = "metres"
    result = core_distance.path_length(points, geographic, units)
    result["elevation"] = None
    result["elevation_unit"] = core_distance.UNIT_SYMBOLS[elevation_unit]
    if include_elevation:
        change = core_distance.elevation_change(r, points)
        if change is not None:
            result["elevation"] = {k: core_distance.from_metres(v, elevation_unit) for k, v in change.items()}
    return result


def area(layer_id: str, polygon=None, pixels=None, units: str = "square metres",
         include_surface: bool = False) -> dict:
    r = _layer(layer_id).raster
    if polygon is None:
        polygon = _pixels_to_xy(r, pixels)
    result = core_area.polygon_area(polygon, is_geographic(r))
    unit = core_area.auto_unit(result["area_m2"]) if units == "auto" else units
    result["area"] = core_area.from_square_metres(result["area_m2"], unit)
    result["unit"] = core_area.UNIT_SYMBOLS[unit]
    long_perimeter = result["perimeter_m"] >= 1000          # metres for a small border, kilometres for a long one
    result["perimeter"] = result["perimeter_m"] / 1000 if long_perimeter else result["perimeter_m"]
    result["perimeter_unit"] = "km" if long_perimeter else "m"
    if include_surface:
        try:
            s = surface_area(r, polygon)
        except ValueError as e:
            raise BadRequest(str(e), code="bad_surface_area")
        s["surface_area"] = core_area.from_square_metres(s["surface_area_m2"], unit)
        result["surface"] = s
    return result


def _profile_units(out: dict, units: str) -> dict:
    """Convert the distance axis (metres from the core) to the chosen unit; heights stay as they are."""
    total_m = out["total_distance"]
    if units == "auto":
        units = "kilometres" if total_m >= 1000 else "metres"
    out["distance"] = [None if d is None else core_distance.from_metres(d, units) for d in out["distance"]]
    out["total_distance_m"] = total_m
    out["total_distance"] = core_distance.from_metres(total_m, units)
    out["distance_units"] = core_distance.UNIT_SYMBOLS[units]
    return out


def elevation_profile(layer_id: str, line=None, samples: int = 200, pixels=None,
                      units: str = "metres") -> dict:
    r = _layer(layer_id).raster
    if line is None:
        line = _pixels_to_xy(r, pixels)
    out = core_profile.elevation_profile(r, line, is_geographic(r), samples)
    return _profile_units(out, units)


# ---- quality & statistics ----
def layer_statistics(layer_id: str) -> dict:
    return layer_stats.compute(_layer(layer_id).raster.data)


def get_histogram(layer_id: str, bins: int) -> dict:
    if not 1 <= bins <= get_settings().max_histogram_bins:
        raise BadRequest(f"bins must be between 1 and {get_settings().max_histogram_bins}.",
                         code="bad_bins")
    return histogram.compute(_layer(layer_id).raster.data, bins)


def nodata(layer_id: str) -> dict:
    return nodata_check.run(_layer(layer_id).raster.data)


def outlier_check(layer_id: str, method: str, threshold: float | None) -> dict:
    return outliers.run(_layer(layer_id).raster.data, method, threshold)


# ---- surface analysis & terrain derivatives (all create a new raster layer) ----
def _surface(layer_id: str, tool: str, label: str,
             fn: Callable[[np.ndarray, float | np.ndarray, float | np.ndarray], np.ndarray]) -> dict:
    src = _source(layer_id)
    dx, dy = cell_size_by_row(src.raster)       # degree rasters: one size per row
    return _derive(src, fn(src.raster.data, dx, dy), tool, label)


def hillshade(layer_id: str, azimuth: float, altitude: float, z_factor: float) -> dict:
    return _surface(layer_id, "hillshade", "hillshade",
                    lambda d, dx, dy: compute_hillshade(d, dx, dy, azimuth, altitude, z_factor))


def slope(layer_id: str, units: str, method: str = "planar") -> dict:
    label = f"slope ({units})" if method == "planar" else f"slope ({units}, {method})"
    src = _source(layer_id)
    if method == "geodesic" and is_geographic(src.raster):
        # true 3D slope on the WGS84 ellipsoid, like ArcMap GEODESIC. ArcMap first squares non-square
        # degree cells (JAXA 2" x 1" -> 2" x 2"); we do the same, so the result is a coarser raster.
        r = square_cells(src.raster) or src.raster
        data = ellipsoid_slope(r.data, r.origin_y, r.pixel_h, r.pixel_w, units, drop_border=True)  # ArcMap leaves the border empty
        if r is src.raster:
            return _derive(src, data, "slope", label)
        out = add_raster_layer(r.with_data(data), f"{src.name} - {label}, square cells",
                               derived_from=src.id, tool="slope")
        return {"layer": out.info(), "statistics": layer_stats.compute(data)}
    # planar, or geodesic on a projected raster (already in metres, so a plane fit is used)
    return _surface(layer_id, "slope", label,
                    lambda d, dx, dy: compute_slope(d, dx, dy, units, method))


def aspect(layer_id: str, flat_as_minus_one: bool = False, method: str = "planar") -> dict:
    flat_value = -1.0 if flat_as_minus_one else None
    label = "aspect" if method == "planar" else f"aspect ({method})"
    src = _source(layer_id)
    if method == "geodesic" and is_geographic(src.raster):
        # direction of the plane fitted on the WGS84 ellipsoid, like ArcMap GEODESIC (cells squared first, as for slope)
        r = square_cells(src.raster) or src.raster
        gx, gn = ellipsoid_gradients(r.data, r.origin_y, r.pixel_h, r.pixel_w)
        data = aspect_from_gradients(gx, gn, flat_value, flat_mask=flat_window_mask(r.data), drop_border=True)
        if r is src.raster:
            return _derive(src, data, "aspect", label)
        out = add_raster_layer(r.with_data(data), f"{src.name} - {label}, square cells",
                               derived_from=src.id, tool="aspect")
        return {"layer": out.info(), "statistics": layer_stats.compute(data)}
    if method == "geodesic":
        # ArcMap GEODESIC measures from true north; on a projected map "up" is grid north, so turn by the difference
        offset = grid_north_offset(src.raster)
        return _surface(layer_id, "aspect", label,
                        lambda d, dx, dy: aspect_from_gradients(*plane_fit_gradients(d, dx, dy), flat_value, offset))
    return _surface(layer_id, "aspect", label,
                    lambda d, dx, dy: compute_aspect(d, dx, dy, flat_value))


def curvature(layer_id: str) -> dict:
    return _surface(layer_id, "curvature", "curvature", compute_curvature)


def roughness(layer_id: str) -> dict:
    src = _source(layer_id)
    return _derive(src, compute_roughness(src.raster.data), "roughness", "roughness")


def tpi(layer_id: str) -> dict:
    src = _source(layer_id)
    return _derive(src, compute_tpi(src.raster.data), "tpi", "TPI")


def ruggedness(layer_id: str) -> dict:
    src = _source(layer_id)
    return _derive(src, compute_ruggedness(src.raster.data), "ruggedness", "ruggedness (TRI)")


def contours(layer_id: str, interval: float, base: float) -> dict:
    src = _layer(layer_id)
    fc = contour_lines(src.raster, interval, base)
    out = add_vector_layer(fc, f"{src.name} - contours {interval:g}", derived_from=src.id,
                           tool="contours")
    return {"layer": out.info(), "statistics": None, "extra": {"feature_count": len(fc["features"])}}
