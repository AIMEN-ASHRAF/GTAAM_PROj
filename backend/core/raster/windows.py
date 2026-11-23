"""3x3 neighbourhood helper shared by terrain, editing and nodata code."""
from __future__ import annotations

import numpy as np


def shifted(a: np.ndarray, mode: str = "edge", **pad_kw) -> dict[str, np.ndarray]:
    """The 3x3 neighbourhood of every cell, as nine same-shaped arrays.

        nw n ne
        w  c e        e.g. out["n"][i, j] is the cell just north of a[i, j]
        sw s se

    Edges are padded by repeating the border cells (mode="edge").
    """
    h, w = a.shape
    p = np.pad(a, 1, mode=mode, **pad_kw)
    return {
        "nw": p[0:h, 0:w], "n": p[0:h, 1:w + 1], "ne": p[0:h, 2:w + 2],
        "w": p[1:h + 1, 0:w], "c": a, "e": p[1:h + 1, 2:w + 2],
        "sw": p[2:h + 2, 0:w], "s": p[2:h + 2, 1:w + 1], "se": p[2:h + 2, 2:w + 2],
    }


def shifted_filled(a: np.ndarray, max_missing: int | None = None) -> dict[str, np.ndarray]:
    """Like `shifted`, but a missing (NaN) neighbour takes the value of the centre cell.

    max_missing: if given, a cell with more missing neighbours than this gets NaN in the centre entry
    ("c") and every neighbour entry, so whatever is computed from it comes out empty. ArcMap's planar
    slope works this way with max_missing=1 (a cell needs 7 of its 8 neighbours). With None, every
    cell that has data gets a value. A cell with no data of its own always stays NaN."""
    n = shifted(a)
    c = n["c"]
    keys = ("nw", "n", "ne", "w", "e", "sw", "s", "se")
    missing = sum(np.isnan(n[k]).astype(int) for k in keys)
    for k in keys:
        n[k] = np.where(np.isnan(n[k]), c, n[k])
    if max_missing is not None:
        too_many = missing > max_missing
        for k in keys + ("c",):
            n[k] = np.where(too_many, np.nan, n[k])
    return n


def bbox_of_mask(mask: np.ndarray, pad: int = 0) -> tuple[int, int, int, int] | None:
    """(row0, row1, col0, col1) of the True area (padded, clipped), or None if empty."""
    if not mask.any():
        return None
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    h, w = mask.shape
    return (max(rows[0] - pad, 0), min(rows[-1] + 1 + pad, h),
            max(cols[0] - pad, 0), min(cols[-1] + 1 + pad, w))
