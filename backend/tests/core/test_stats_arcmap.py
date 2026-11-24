"""Layer statistics follow ArcMap: standard deviation divides by n-1, sums are done in 64-bit."""
import numpy as np

from core.stats import layer_stats, outliers


def test_std_is_sample_std_like_arcmap():
    d = np.array([[1, 2, 3], [4, 5, np.nan]], dtype="float32")
    s = layer_stats.compute(d)
    assert s["std_dev"] == np.std([1, 2, 3, 4, 5], ddof=1)      # 1.5811..., not 1.4142 (n)
    assert s["nodata_count"] == 1 and s["count"] == 5


def test_mean_is_not_float32_drift():
    d = np.full((2000, 2000), 781.7675, dtype="float32")
    d[0, 0] = 213.0
    assert abs(layer_stats.compute(d)["mean"] - d.astype("float64").mean()) < 1e-9


def test_zscore_bounds_use_same_std():
    d = np.arange(1, 101, dtype="float32").reshape(10, 10)
    lo, hi, _ = outliers.bounds(d, "zscore", 3.0)
    assert abs(hi - (50.5 + 3 * np.std(np.arange(1, 101), ddof=1))) < 1e-9
