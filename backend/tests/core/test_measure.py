import numpy as np

from core.raster.model import Raster
from core.raster.sampling import sample_bilinear


def test_non_square_cells_are_read_like_arcmap_when_asked():
    """ArcMap splits a 2 x 1 cell into two 1 x 1 cells of equal height before interpolating
    (checked against Stack Profile on the 65N tile). Plain bilinear blends across the wide cell."""
    r = Raster(np.array([[0.0, 10.0], [0.0, 10.0]]), (2.0, 0, 0.0, 0, -1.0, 2.0), "EPSG:4326")
    xs, ys = [0.5, 1.5, 2.0, 2.5], [1.0] * 4
    assert np.allclose(sample_bilinear(r, xs, ys, square_cells=True), [0, 0, 5, 10])
    assert sample_bilinear(r, [1.5], [1.0])[0] == 2.5          # default behaviour unchanged


def test_square_cells_flag_changes_nothing_on_square_rasters():
    r = Raster(np.arange(16, dtype=float).reshape(4, 4), (1.0, 0, 0.0, 0, -1.0, 4.0), "EPSG:32643")
    xs, ys = [0.7, 1.9, 2.5], [3.1, 2.2, 1.4]
    assert np.allclose(sample_bilinear(r, xs, ys), sample_bilinear(r, xs, ys, square_cells=True))
