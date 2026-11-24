"""Curvature on a degree DEM: a smooth bowl of known curvature must come out right at every latitude."""
import numpy as np
import pytest

from core.raster.model import Raster
from core.terrain.curvature import compute_curvature
from services.analysis_service import cell_size_by_row


@pytest.mark.parametrize("lat0", [0.0, 33.0, 65.0, 80.0])
def test_bowl_on_degree_dem(lat0):
    R, h, n, k = 6371000.0, 1 / 3600.0, 121, 0.001
    lats = lat0 + (np.arange(n) - n // 2) * h
    lons = (np.arange(n) - n // 2) * h
    la, lo = np.meshgrid(lats, lons, indexing="ij")
    y = np.radians(la - lat0) * R
    x = np.radians(lo) * R * np.cos(np.radians(la))
    z = (0.5 * k * (x ** 2 + y ** 2)).astype("float32")[::-1]       # curvature = -2*k*100 = -0.2
    r = Raster(z, (h, 0, lons[0] - h / 2, 0, -h, lats[-1] + h / 2), "EPSG:4326", None)
    dx, dy = cell_size_by_row(r)
    c = compute_curvature(r.data, dx, dy)[30:-30, 30:-30]
    assert abs(c.mean() - (-0.2)) < 0.004                           # within 2 % (test uses a sphere, app an ellipsoid)
