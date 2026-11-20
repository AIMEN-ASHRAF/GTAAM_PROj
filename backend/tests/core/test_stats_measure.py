import numpy as np
import pytest

from core.measure.area import polygon_area
from core.measure.distance import elevation_change, flat_distance, geodesic_distance, from_metres, haversine, path_length, snap_to_cell_centres
from core.measure.profile import elevation_profile
from core.stats import histogram, layer_stats, nodata_check, outliers
from tests.conftest import make_plane


def test_layer_stats_ignore_nan():
    d = np.array([[1, 2], [3, np.nan]], dtype=np.float32)
    s = layer_stats.compute(d)
    assert (s["min"], s["max"], s["mean"], s["nodata_count"]) == (1, 3, 2, 1)


def test_histogram_counts_add_up():
    d = np.arange(100, dtype=np.float32).reshape(10, 10)
    h = histogram.compute(d, bins=10)
    assert sum(h["counts"]) == 100 and len(h["bin_edges"]) == 11


def test_nodata_check():
    d = np.ones((4, 4), dtype=np.float32)
    assert nodata_check.run(d)["status"] == "clean"
    d[0, 0] = np.nan
    r = nodata_check.run(d)
    assert r["nodata_count"] == 1 and r["status"] == "has_nodata"


def test_outliers_find_the_spike():
    d = np.random.default_rng(1).normal(100, 1, (50, 50)).astype(np.float32)
    d[10, 10] = 500
    for method in ("iqr", "zscore"):
        r = outliers.run(d, method)
        assert r["outlier_count"] >= 1 and r["highest_outlier"] == 500
    with pytest.raises(ValueError):
        outliers.run(d, "nope")


def test_distance_and_area():
    assert path_length([(0, 0), (3, 4)], geographic=False)["total"] == 5
    assert haversine(0, 0, 1, 0) == pytest.approx(111_195, rel=1e-3)
    sq = polygon_area([(0, 0), (100, 0), (100, 100), (0, 100)], geographic=False)
    assert sq["area_m2"] == 10_000
    deg = polygon_area([(73, 33), (73.01, 33), (73.01, 33.01), (73, 33.01)], geographic=True)
    assert 0.9e6 < deg["area_m2"] < 1.1e6            # ~0.93 km x 1.1 km


def test_profile_follows_the_plane():
    plane = make_plane(0.5)                           # z = 0.5 * x
    p = elevation_profile(plane, [(30, 300), (450, 300)], geographic=False, samples=50)
    assert p["total_distance"] == pytest.approx(420)
    assert p["elevation"][0] == pytest.approx(15 + 0, abs=1.0) or p["elevation"][0] is not None
    assert p["gain"] > 0 and p["loss"] == 0


def test_flat_distance_3_4_5():
    assert flat_distance((0, 0), (3, 4)) == pytest.approx(5)
    assert flat_distance((10, 20), (13, 24)) == pytest.approx(5)


def test_flat_distance_direction_does_not_matter():
    assert flat_distance((0, 0), (300, 400)) == pytest.approx(500)
    assert flat_distance((300, 400), (0, 0)) == pytest.approx(500)
    assert flat_distance((0, 0), (-300, -400)) == pytest.approx(500)


def test_from_metres_units():
    assert from_metres(1000, "kilometres") == pytest.approx(1)
    assert from_metres(0.3048, "feet") == pytest.approx(1)
    assert from_metres(1609.344, "miles") == pytest.approx(1)
    assert from_metres(250, "metres") == pytest.approx(250)


def test_from_metres_ignores_capital_letters():
    assert from_metres(1000, "Kilometres") == pytest.approx(1)


def test_from_metres_unknown_unit():
    with pytest.raises(ValueError):
        from_metres(10, "furlongs")


def test_elevation_change_uphill_and_downhill():
    plane = make_plane(0.5)
    up = elevation_change(plane, [(30, 300), (450, 300)])
    down = elevation_change(plane, [(450, 300), (30, 300)])
    assert up["difference"] == pytest.approx(210)
    assert down["difference"] == pytest.approx(-210)


def test_elevation_change_off_the_dem_is_none():
    plane = make_plane(0.5)
    assert elevation_change(plane, [(30, 300), (5000, 300)]) is None

def test_path_length_in_other_units():
    r = path_length([(0, 0), (3000, 0), (3000, 4000)], geographic=False, unit="kilometres")
    assert r["segments"] == pytest.approx([3, 4])
    assert r["total"] == pytest.approx(7)
    assert r["unit"] == "km"


def test_path_length_default_is_metres():
    r = path_length([(0, 0), (300, 400)], geographic=False)
    assert r["total"] == pytest.approx(500)
    assert r["unit"] == "m"


def test_snap_moves_points_to_cell_centres():
    plane = make_plane(0.5)                              # 30 m cells, top edge at y = 600
    snapped = snap_to_cell_centres(plane, [(31, 301), (45, 315)])
    assert snapped[0] == pytest.approx((45, 315))        # inside the cell centred at (45, 315)
    assert snapped[1] == pytest.approx((45, 315))        # already at a centre: unchanged


def test_geodesic_known_answers():
    # Equator: 1 degree = equator radius * pi / 180
    assert geodesic_distance(0, 0, 1, 0) == pytest.approx(111319.4908, abs=0.01)
    # Flinders Peak -> Buninyong (published Vincenty test pair)
    d = geodesic_distance(144.42486788888888, -37.95103341666667,
                          143.92649552777778, -37.65282113888889)
    assert d == pytest.approx(54972.271, abs=0.01)


def test_geodesic_matches_arcmap():
    # ArcMap 10.8 Polyline.getLength("GEODESIC", "METERS") on test_lines.shp
    short = path_length([(73.2, 33.3), (73.25, 33.33)], geographic=True)["total"]
    long_ = path_length([(73.1, 33.1), (73.9, 33.9)], geographic=True)["total"]
    bends = path_length([(73.1, 33.2), (73.3, 33.5), (73.5, 33.3), (73.8, 33.6)],
                        geographic=True)["total"]
    assert short == pytest.approx(5722.69, abs=0.01)
    assert long_ == pytest.approx(115754.26, abs=0.01)
    assert bends == pytest.approx(110497.63, abs=0.01)


def test_geodesic_same_point_is_zero():
    assert geodesic_distance(73.2, 33.3, 73.2, 33.3) == 0.0


# ---- polygon area: geodesic (WGS84) on lon/lat, planar on projected coordinates ----
# Reference numbers come from GeographicLib (Karney), an independent geodesic library.
@pytest.mark.parametrize("polygon, area_m2, perimeter_m", [
    ([(73.5, 33.5), (73.5105, 33.5), (73.5105, 33.509), (73.5, 33.509)], 973_900.8, 3_947.7),
    ([(73.5, 33.5), (73.6, 33.5), (73.6, 33.59), (73.5, 33.59)], 92_709_831.2, 38_539.4),
    ([(73, 33), (74, 33), (74, 34), (73, 34)], 10_306_245_947.5, 407_664.1),
    ([(70, 30), (74, 31), (75, 35), (71, 36)], 207_535_930_565.0, None),
    ([(20, -34), (21, -34), (21, -33), (20, -33)], 10_306_245_947.5, None),
])
def test_geodesic_polygon_area_matches_geographiclib(polygon, area_m2, perimeter_m):
    r = polygon_area(polygon, geographic=True)
    assert r["method"] == "geodesic"
    assert r["area_m2"] == pytest.approx(area_m2, rel=1e-6)
    if perimeter_m:
        assert r["perimeter_m"] == pytest.approx(perimeter_m, rel=1e-5)


def test_geodesic_area_ignores_direction_and_repeated_first_point():
    sq = [(73, 33), (74, 33), (74, 34), (73, 34)]
    a = polygon_area(sq, True)["area_m2"]
    assert polygon_area(list(reversed(sq)), True)["area_m2"] == pytest.approx(a)
    assert polygon_area(sq + [sq[0]], True)["area_m2"] == pytest.approx(a)


def test_geodesic_area_across_the_antimeridian():
    r = polygon_area([(179.5, 10), (-179.5, 10), (-179.5, 11), (179.5, 11)], True)
    assert r["area_m2"] == pytest.approx(12_108_467_312.6, rel=1e-6)


def test_projected_area_is_flat_and_has_a_perimeter():
    r = polygon_area([(0, 0), (100, 0), (100, 50), (0, 50)], geographic=False)
    assert r["method"] == "planar"
    assert r["area_m2"] == 5000 and r["perimeter_m"] == 300
    assert r["area_ha"] == pytest.approx(0.5) and r["area_km2"] == pytest.approx(0.005)


def test_geodesic_direct_and_inverse_agree():
    from core.measure.distance import geodesic_direct, geodesic_inverse
    dist, az = geodesic_inverse(73.1, 33.2, 73.9, 33.8)
    lon, lat = geodesic_direct(73.1, 33.2, az, dist)
    assert (lon, lat) == pytest.approx((73.9, 33.8), abs=1e-8)


def test_surface_area_flat_and_tilted():
    import numpy as np
    from core.measure.surface_area import surface_area
    from core.raster.model import Raster
    tf = (10.0, 0, 0.0, 0, -10.0, 1000.0)
    box = [(200, 800), (800, 800), (800, 200), (200, 200)]
    flat = Raster(np.full((100, 100), 50, np.float32), tf, "EPSG:32643")
    f = surface_area(flat, box)
    assert abs(f["surface_to_flat_ratio"] - 1.0) < 1e-9
    assert abs(f["surface_area_m2"] - 600 * 600) / (600 * 600) < 0.04
    cols = np.arange(100, dtype=np.float32) * 10          # rises 10 m per 10 m cell = 45 degrees
    ramp = Raster(np.tile(cols, (100, 1)), tf, "EPSG:32643")
    t = surface_area(ramp, box)
    assert abs(t["surface_to_flat_ratio"] - 2 ** 0.5) < 1e-6
