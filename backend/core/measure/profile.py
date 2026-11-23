"""Elevation profile along a line."""
from __future__ import annotations

import numpy as np

from core.raster.model import Raster
from core.raster.sampling import sample_bilinear
from core.raster.utils import num, to_list

from .distance import segment_length


def elevation_profile(raster: Raster, line, geographic: bool, samples: int = 200) -> dict:
    if len(line) < 2:
        raise ValueError("The line needs at least two points.")
    pts = np.asarray(line, float)
    seg_coord = np.hypot(*np.diff(pts, axis=0).T)
    seg_real = np.array([segment_length(line[i], line[i + 1], geographic)
                         for i in range(len(line) - 1)])
    cum_coord = np.r_[0.0, np.cumsum(seg_coord)]
    cum_real = np.r_[0.0, np.cumsum(seg_real)]
    if cum_coord[-1] == 0:
        raise ValueError("The line has zero length.")
    t = np.linspace(0.0, cum_coord[-1], samples)
    xs = np.interp(t, cum_coord, pts[:, 0])
    ys = np.interp(t, cum_coord, pts[:, 1])
    dist = np.interp(t, cum_coord, cum_real)
    z = sample_bilinear(raster, xs, ys, square_cells=True)  # ArcMap reads non-square cells as square
    ok = np.isfinite(z)
    steps = np.diff(z[ok]) if ok.sum() > 1 else np.array([])
    # slope between neighbouring valid samples, in percent (rise / run * 100)
    run = np.diff(dist[ok]) if ok.sum() > 1 else np.array([])
    with np.errstate(divide="ignore", invalid="ignore"):
        grade = np.where(run > 0, steps / run * 100.0, np.nan) if steps.size else np.array([])
    grade = grade[np.isfinite(grade)]
    first = z[ok][0] if ok.any() else np.nan
    last = z[ok][-1] if ok.any() else np.nan
    return {
        "start_elevation": num(first), "end_elevation": num(last),
        # net slope: start height to end height over the length (ups and downs cancel out)
        "net_slope_percent": num((last - first) / (dist[ok][-1] - dist[ok][0]) * 100.0)
        if ok.sum() > 1 and dist[ok][-1] > dist[ok][0] else None,
        # average slope: every climb and descent counted, so a hilly line is not shown as flat
        "mean_slope_percent": num(np.abs(steps).sum() / (dist[ok][-1] - dist[ok][0]) * 100.0)
        if ok.sum() > 1 and dist[ok][-1] > dist[ok][0] else None,
        "max_slope_percent": num(np.abs(grade).max()) if grade.size else None,
        "distance": to_list(dist), "elevation": to_list(z), "x": to_list(xs), "y": to_list(ys),
        "total_distance": float(cum_real[-1]),
        "min": num(z[ok].min()) if ok.any() else None,
        "max": num(z[ok].max()) if ok.any() else None,
        "gain": num(steps[steps > 0].sum()) if steps.size else 0.0,
        "loss": num(-steps[steps < 0].sum()) if steps.size else 0.0,
        "samples_outside": int((~ok).sum()),
    }
