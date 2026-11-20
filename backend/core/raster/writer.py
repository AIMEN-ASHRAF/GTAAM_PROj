"""Save a Raster as a GeoTIFF."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ._deps import require_rasterio
from .model import Raster

DEFAULT_NODATA = -9999.0


def write_geotiff(raster: Raster, path: str | Path, nodata: float | None = None) -> str:
    rasterio = require_rasterio()
    from rasterio.transform import Affine

    p = Path(path)
    if p.suffix.lower() not in (".tif", ".tiff"):
        p = p.with_suffix(".tif")
    p.parent.mkdir(parents=True, exist_ok=True)
    if nodata is None:
        nodata = raster.nodata if raster.nodata is not None else DEFAULT_NODATA
    out = np.where(np.isfinite(raster.data), raster.data, nodata).astype("float32")
    with rasterio.open(
        p, "w", driver="GTiff", height=raster.height, width=raster.width, count=1,
        dtype="float32", crs=raster.crs, transform=Affine(*raster.transform), nodata=nodata,
        compress="deflate", zlevel=1, predictor=3,   # fast and small for float data
    ) as dst:
        dst.write(out, 1)
    return str(p)


def _with_suffix(path: str | Path, suffixes: tuple[str, ...], default: str) -> Path:
    p = Path(path)
    if p.suffix.lower() not in suffixes:
        p = p.with_suffix(default)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_ascii_grid(raster: Raster, path: str | Path, nodata: float | None = None) -> str:
    """Esri ASCII Grid (.asc). Cells that are not square are written with separate dx / dy."""
    p = _with_suffix(path, (".asc",), ".asc")
    if nodata is None:
        nodata = raster.nodata if raster.nodata is not None else DEFAULT_NODATA
    a, _, c, _, e, f = raster.transform
    dx, dy = float(a), float(-e)
    out = np.where(np.isfinite(raster.data), raster.data, nodata)
    cell = f"cellsize {dx:.12g}" if abs(dx - dy) <= 1e-12 * max(dx, dy) else f"dx {dx:.12g}\ndy {dy:.12g}"
    head = (f"ncols {raster.width}\nnrows {raster.height}\n"
            f"xllcorner {c:.12g}\nyllcorner {f - raster.height * dy:.12g}\n{cell}\nNODATA_value {nodata:g}\n")
    with open(p, "w", encoding="ascii", newline="\n") as fh:
        fh.write(head)
        np.savetxt(fh, out, fmt="%.4f")
    return str(p)


def write_xyz_csv(raster: Raster, path: str | Path) -> str:
    """One row per valid cell: x, y, z at the cell centre (NoData cells are left out)."""
    p = _with_suffix(path, (".csv", ".xyz", ".txt"), ".csv")
    a, _, c, _, e, f = raster.transform
    xs = c + (np.arange(raster.width) + 0.5) * a
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("x,y,z\n")
        for row in range(raster.height):               # row by row: a big DEM never sits in memory twice
            z = raster.data[row]
            ok = np.isfinite(z)
            if raster.nodata is not None:
                ok &= z != raster.nodata
            if not ok.any():
                continue
            y = f + (row + 0.5) * e
            block = np.column_stack([xs[ok], np.full(int(ok.sum()), y), z[ok]])
            np.savetxt(fh, block, fmt="%.8f,%.8f,%.4f")
    return str(p)
