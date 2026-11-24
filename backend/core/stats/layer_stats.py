"""Minimum, maximum, mean and standard deviation of a layer (NaN ignored).

Standard deviation divides by n-1 (the "sample" form) because that is what ArcMap reports."""
from __future__ import annotations

import numpy as np

from core.raster.utils import num


def compute(data: np.ndarray) -> dict:
    valid = data[np.isfinite(data)].astype("float64")   # add up in 64-bit: float32 sums drift in the 4th decimal
    total = int(data.size)
    base = {"count": int(valid.size), "nodata_count": total - int(valid.size), "total": total}
    if valid.size == 0:
        return {"min": None, "max": None, "mean": None, "std_dev": None, "median": None, **base}
    return {"min": num(valid.min()), "max": num(valid.max()), "mean": num(valid.mean()),
            "std_dev": num(valid.std(ddof=1) if valid.size > 1 else 0.0), "median": num(np.median(valid)), **base}
