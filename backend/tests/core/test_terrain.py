import numpy as np
import pytest

from core.raster.crs import cell_size_by_row, cell_size_meters, is_geographic, metres_per_degree
from core.raster.resample import square_cells
from core.terrain.aspect import compute_aspect
from core.terrain.contours import contour_lines
from core.terrain.curvature import compute_curvature
from core.terrain.hillshade import compute_hillshade
from core.terrain.roughness import compute_roughness
from core.terrain.ruggedness import compute_ruggedness
from core.terrain.slope import compute_slope
from core.terrain.slope_ellipsoid import ellipsoid_gradients, ellipsoid_slope
from core.terrain.tpi import compute_tpi
from tests.conftest import make_hill, make_plane


def test_slope_of_a_plane_matches_trigonometry():
    plane = make_plane(0.5)
    s = compute_slope(plane.data, 30, 30)
    assert s[5:-5, 5:-5] == pytest.approx(np.degrees(np.arctan(0.5)), abs=1e-3)   # 26.565 deg
    p = compute_slope(plane.data, 30, 30, units="percent")
    assert p[5, 5] == pytest.approx(50.0, abs=1e-3)


def test_both_slope_methods_agree_on_a_plane():
    plane = make_plane(0.5)
    planar = compute_slope(plane.data, 30, 30, method="planar")
    geodesic = compute_slope(plane.data, 30, 30, method="geodesic")
    assert geodesic[5:-5, 5:-5] == pytest.approx(planar[5:-5, 5:-5], abs=1e-4)


def test_slope_methods_hand_worked_window_at_45n():
    # 45N, 1" x 1" cell: dx = 21.90 m, dy = 30.87 m (worked by hand in the Doc)
    win = np.array([[20, 24, 30], [22, 27, 33], [25, 31, 38]], dtype=np.float32)
    assert compute_slope(win, 21.90, 30.87, method="planar")[1, 1] == pytest.approx(15.60, abs=0.01)
    assert compute_slope(win, 21.90, 30.87, method="geodesic")[1, 1] == pytest.approx(15.66, abs=0.01)


def test_ellipsoid_slope_of_level_height_is_zero():
    flat = np.full((20, 20), 250.0)
    assert ellipsoid_slope(flat, 65.0, 1 / 3600, 2 / 3600) == pytest.approx(0.0, abs=1e-4)


def test_ellipsoid_slope_of_a_known_tilt():
    # height rises 0.5 m per metre going north: slope 26.565 deg (tan = 0.5)
    _, m_lat = metres_per_degree(33.5)
    rows = np.arange(40, dtype=float)[:, None]
    dem = np.repeat(-rows * 0.5 * (m_lat / 3600), 40, axis=1)
    assert ellipsoid_slope(dem, 33.5, 1 / 3600, 1 / 3600)[10:-10, 10:-10] == pytest.approx(26.565, abs=0.05)


def test_ellipsoid_slope_agrees_with_plane_fit_on_a_hill():
    lat0, dlat, dlon = 33.5, 1 / 3600, 1 / 3600
    hill = make_hill().data.astype(np.float64)
    mx, my = metres_per_degree(lat0)
    plane = compute_slope(hill, mx * dlon, my * dlat, method="geodesic")
    true3d = ellipsoid_slope(hill, lat0, dlat, dlon)
    assert true3d[3:-3, 3:-3] == pytest.approx(plane[3:-3, 3:-3], abs=0.05)


def test_slope_rejects_an_unknown_method():
    with pytest.raises(ValueError):
        compute_slope(make_plane(0.5).data, 30, 30, method="bilinear")


def test_aspect_of_a_plane_rising_east_faces_west():
    plane = make_plane(0.5)
    assert compute_aspect(plane.data, 30, 30)[10, 10] == pytest.approx(270.0, abs=1e-3)


def test_aspect_methods_agree_on_a_plane_and_reject_unknown():
    plane = make_plane(0.5)
    a = compute_aspect(plane.data, 30, 30, method="geodesic")[10, 10]
    assert a == pytest.approx(270.0, abs=1e-3)
    with pytest.raises(ValueError):
        compute_aspect(plane.data, 30, 30, method="bilinear")


def test_ellipsoid_aspect_of_a_plane_rising_east_faces_west():
    # height rises to the east by 10 m per cell on a degree grid at 33 N -> downhill faces west (270)
    dem = np.tile(np.arange(20, dtype=np.float64) * 10.0, (20, 1))
    gx, gn = ellipsoid_gradients(dem, 33.5, 1 / 3600, 1 / 3600)
    assert gx[10, 10] > 0 and abs(gn[10, 10]) < 1e-9
    from core.terrain.aspect import aspect_from_gradients
    assert aspect_from_gradients(gx, gn)[10, 10] == pytest.approx(270.0, abs=1e-3)


def test_grid_north_offset_is_zero_for_degrees_and_small_for_utm():
    from core.raster.crs import grid_north_offset
    from core.raster.model import Raster
    deg = Raster(np.zeros((4, 4)), (0.001, 0, 70.0, 0, -0.001, 30.0), crs="EPSG:4326")
    assert grid_north_offset(deg) == 0.0
    # Dorre Island, UTM 49S: about 2 deg east of the zone centre at 25 S -> roughly +0.9 deg
    utm = Raster(np.zeros((4, 4)), (2, 0, 710000.0, 0, -2, 7210000.0), crs="EPSG:32749")
    assert grid_north_offset(utm) == pytest.approx(0.89, abs=0.1)


def test_north_offset_turns_aspect_back_towards_true_north():
    from core.terrain.aspect import aspect_from_gradients
    gx, gn = np.array([[0.5]]), np.array([[0.0]])            # rises east -> faces west (270 from grid north)
    assert aspect_from_gradients(gx, gn, None, 0.9)[0, 0] == pytest.approx(269.1, abs=1e-3)


def test_flat_ground_has_no_aspect_and_hillshade_180():
    flat = np.full((10, 10), 100.0, dtype=np.float32)
    assert np.isnan(compute_aspect(flat, 30, 30)).all()
    assert compute_hillshade(flat, 30, 30, altitude=45)[5, 5] == pytest.approx(180.0, abs=0.5)


def test_hillshade_sun_side_is_brighter():
    plane = make_plane(0.5)                    # slopes face west
    west = compute_hillshade(plane.data, 30, 30, azimuth=270)[10, 10]
    east = compute_hillshade(plane.data, 30, 30, azimuth=90)[10, 10]
    assert west > east


def test_curvature_hilltop_is_convex_positive():
    r = make_hill(geographic=False)
    c = compute_curvature(r.data, 30, 30)
    assert c[r.height // 2, r.width // 2] > 0


def test_roughness_tpi_ruggedness_on_a_single_peak():
    z = np.zeros((7, 7), dtype=np.float32)
    z[3, 3] = 10
    assert compute_roughness(z)[3, 3] == 10
    assert compute_tpi(z)[3, 3] == pytest.approx(10.0)
    assert compute_ruggedness(z)[3, 3] == pytest.approx(np.sqrt(8 * 100))


def test_geographic_cell_size_is_narrower_east_west():
    r = make_hill(geographic=True)
    dx, dy = cell_size_meters(r)
    assert is_geographic(r)
    assert 25 < dx < dy < 35


def test_contours_return_geojson_lines():
    fc = contour_lines(make_hill(geographic=False), interval=100)
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) >= 3
    assert fc["features"][0]["geometry"]["type"] == "MultiLineString"
    with pytest.raises(ValueError):
        contour_lines(make_hill(), interval=0.001)


def test_metres_per_degree_follows_wgs84():
    from core.raster.crs import metres_per_degree
    lon0, lat0 = metres_per_degree(0)
    assert lon0 == pytest.approx(111_319.5, abs=1)        # equator, east-west
    assert lat0 == pytest.approx(110_574.3, abs=1)        # equator, north-south
    lon, lat = metres_per_degree(33.5)                    # northern Pakistan
    assert lat == pytest.approx(110_913, abs=5)
    assert lon == pytest.approx(92_922, abs=5)
    assert metres_per_degree(90)[1] == pytest.approx(111_694, abs=2)


def _degree_dem(top_lat, rows=60, cols=40, w_deg=2 / 3600, h_deg=1 / 3600):
    """A rough degree DEM (like an ALOS tile) that starts at top_lat and runs south."""
    from core.raster.model import Raster
    rng = np.random.default_rng(1)
    z = rng.normal(0, 2.4, (rows, cols)).cumsum(axis=1) + rng.normal(0, 1.2, (rows, cols)).cumsum(axis=0) + 500
    return Raster(z.astype(np.float32), (w_deg, 0, 60.0, 0, -h_deg, top_lat), "EPSG:4326", None)


def test_degree_cell_size_is_worked_out_per_row():
    r = _degree_dem(66.0, rows=3600, cols=10)             # one whole 1-degree tile, 66N down to 65N
    dx, dy = cell_size_by_row(r)
    assert dx.shape == (3600, 1) and dy.shape == (3600, 1)
    for row in (0, 1800, 3599):                            # each row uses its own latitude
        lat = 66.0 - (row + 0.5) / 3600
        m_lon, m_lat = metres_per_degree(lat)
        assert dx[row, 0] == pytest.approx(r.pixel_w * m_lon)
        assert dy[row, 0] == pytest.approx(r.pixel_h * m_lat)
    assert dx[0, 0] < dx[1800, 0] < dx[3599, 0]            # narrower toward the pole
    assert dx[0, 0] == pytest.approx(25.22, abs=0.05)
    assert dx[3599, 0] == pytest.approx(26.21, abs=0.05)
    assert cell_size_meters(r)[0] == pytest.approx(25.72, abs=0.02)   # the single middle value is unchanged


def test_projected_cell_size_is_still_a_single_number():
    dx, dy = cell_size_by_row(make_plane())
    assert (dx, dy) == (30.0, 30.0)


def test_slope_of_a_degree_plane_is_the_same_in_every_row():
    """A plane that rises 0.5 m per metre going east must read atan(0.5) in all rows, top to bottom."""
    from core.raster.crs import metres_per_degree_array
    from core.raster.model import Raster
    rows, cols, w_deg, h_deg, top = 3600, 12, 2 / 3600, 1 / 3600, 66.0
    lat = top - (np.arange(rows) + 0.5) * h_deg
    m_lon, _ = metres_per_degree_array(lat)
    row_width_m = w_deg * m_lon                            # real width of a cell in each row
    z = (0.5 * np.arange(cols)[None, :] * row_width_m[:, None]).astype(np.float64)
    r = Raster(z.astype(np.float32), (w_deg, 0, 60.0, 0, -h_deg, top), "EPSG:4326", None)
    expected = np.degrees(np.arctan(0.5))
    dx, dy = cell_size_by_row(r)
    per_row = compute_slope(r.data, dx, dy)[:, 2:-2]
    assert np.allclose(per_row, expected, atol=0.02)       # same slope top to bottom
    one_value = compute_slope(r.data, *cell_size_meters(r))[:, 2:-2]
    assert abs(one_value[0, 0] - expected) > 0.2           # the old single-value way drifts at the top row
    assert abs(one_value[-1, 0] - expected) > 0.2          # ... and at the bottom row, in the other direction


def test_square_cells_makes_wide_degree_cells_square_like_arcmap():
    from core.raster.model import Raster
    data = np.arange(24, dtype=np.float32).reshape(6, 4)
    r = Raster(data, (2 / 3600, 0.0, 60.0, 0.0, -1 / 3600, 66.0), "EPSG:4326", None)   # 2" wide, 1" tall
    sq = square_cells(r)
    assert sq.data.shape == (3, 4) and sq.pixel_w == pytest.approx(2 / 3600) and sq.pixel_h == pytest.approx(2 / 3600)
    assert sq.data[0, 0] == pytest.approx((0 + 4) / 2)          # two rows averaged
    assert (sq.origin_x, sq.origin_y) == (r.origin_x, r.origin_y)


def test_square_cells_leaves_square_cells_alone():
    from core.raster.model import Raster
    r = Raster(np.zeros((6, 4), np.float32), (1 / 3600, 0.0, 73.0, 0.0, -1 / 3600, 34.0), "EPSG:4326", None)
    assert square_cells(r) is None
