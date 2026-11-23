# Validation against ArcMap 10.8

Functions checked against ArcMap 10.8 (Spatial Analyst, 3D Analyst) between 29 Oct and 23 Nov 2026.

**Test data**
- `ALPSMLC30_N033E073_DSM.tif`: ALOS AW3D30 tile, EPSG:4326, 3600 x 3600, 0.000278 deg cells (geographic)
- `dem_utm43.tif`: the same tile reprojected in ArcMap (Project Raster, bilinear) to WGS 1984 UTM 43N, 3304 x 3924, 28.6 m cells (projected)

Projected data is the clean test: no degree-to-metre conversion, so only the formula is compared.

## Results (projected DEM, `dem_utm43.tif`)

| Function | ArcMap settings | Result |
|---|---|---|
| Slope | DEGREE, PLANAR, Z 1 | Max 67.7533 / Mean 12.7332 / Std 11.2211 in ArcMap; 67.8 / 12.7 / 11.2 in the app. Within 0.4%. |
| Hillshade | Az 315, Alt 45, no shadows, Z 1 | ArcMap Mean 171.51 / Std 37.79; app 172.0 / 37.8. After rounding down to whole numbers (ArcMap stores 8-bit), 100% of pixels identical. |
| Curvature | Z 1 | Min -10.3873 / Max 11.4871 / Std 0.836 in both. 100% pixel match (max difference ~1e-15). |
| Contours | interval 200, base 0, Z 1 | Same 15 levels (400-3200 m). Total length 12,389 km vs 12,432 km (-0.35%). App keeps ~410 tiny rings (<60 m) that ArcMap drops. |

## Results (geographic DEM, `ALPSMLC30_N033E073_DSM.tif`)

| Function | Result |
|---|---|
| Aspect | ArcMap (flat cells excluded) Mean 181.49 / Std 100.98; app 181.4 / 99.8. With ArcMap's square-cell assumption the app matches on 100% of pixels. ArcMap writes -1 for flat cells; the app leaves them blank. |
| Hillshade | ArcMap at Z 1 treats degrees as metres (dark, misleading output: Mean 55.8). The app's formula matches it on 100% of pixels when given the same cell size. With ArcMap Z 0.0000108 the difference from the app is about 1% in mean, because ArcMap assumes square cells. |
| Slope, GEODESIC | Checked 20 Nov 2026. ArcMap GEODESIC at the native 1" cell size (no resampling): Mean 12.9857 / Std 11.3697 / Max 69.238. App `method=geodesic`: 12.9856 / 11.3697 / 69.238 (interior cells). The earlier plane-fit approximation gave 12.9874 / 11.3715 / 69.242. |
| Slope, PLANAR | App default `method=planar` (Horn): Mean 13.0895 / Std 11.4287 / Max 69.636, about 0.8% above ArcMap GEODESIC because Horn weights the nearer neighbours double. ArcMap PLANAR at Z factor 1 on degrees is not comparable: it treats degrees as metres. |

## Degree-to-metre handling

For geographic DEMs the app converts degrees to metres using the WGS84 series at each row's own latitude (`core/raster/crs.py`, `cell_size_by_row`). ArcMap uses a fixed value and treats cells as square. The app's cell shape (about 25.8 m x 30.8 m at 33.5 N) is the more accurate one. For comparisons with ArcMap, use a projected DEM, or ArcMap's GEODESIC slope with the app's `method=geodesic`.

## Distance (geographic DEM, geodesic lengths)

Checked on 10 Nov 2026. Three lines drawn in ArcMap 10.8 on `test_lines.shp` (WGS 84). ArcMap length from the Python window: `Polyline.getLength("GEODESIC", "METERS")`. The app: `POST /analysis/measure/distance` with the same vertices as `points` (longitude, latitude), units metres, on the geographic DEM.

| Line | Vertices (lon, lat) | ArcMap geodesic | App | Difference |
|---|---|---|---|---|
| Short | (73.2, 33.3) to (73.25, 33.33) | 5,722.69 m | 5,722.6868 m | under 1 cm |
| Long | (73.1, 33.1) to (73.9, 33.9) | 115,754.26 m | 115,754.2576 m | under 1 cm |
| Bends | (73.1, 33.2), (73.3, 33.5), (73.5, 33.3), (73.8, 33.6) | 110,497.63 m | 110,497.6280 m | under 1 cm |

The app uses Vincenty's method on the WGS84 ellipsoid for degree-based layers (`core/measure/distance.py`, `geodesic_distance`). An earlier version used a sphere (haversine) and was off by 3 m, 71 m and 100 m on these lines. The three ArcMap values are also automated tests (`test_geodesic_matches_arcmap`).

### Distance: elevation difference

ArcMap `GetCellValue_management` returns the value of the cell a point falls in. The app normally blends the four nearest cells (bilinear), so this check used `"snap": true`, which moves each point to its cell centre. The points were chosen away from cell edges.

| Point (lon, lat) | ArcMap `GetCellValue` | App (`snap` on) |
|---|---|---|
| Start (73.1234, 33.1234) | 531 m | 531.0000 m |
| End (73.8765, 33.8765) | 1850 m | 1850.0000 m |
| Difference (end minus start) | 1319 m | 1319.0000 m |

Exact match (differences of 1e-10 m are float rounding). Without snap the app gives a bilinear value, which can differ slightly from the cell value by design; that was not compared with ArcMap.

### Distance: projected DEM (`dem_utm43.tif`, WGS 84 / UTM 43N)

Three lines in UTM metres. ArcMap: `Polyline.getLength("PLANAR", "METERS")` on a polyline in the raster's spatial reference. App: the same vertices through `POST /analysis/measure/distance`, which measures flat lengths on the grid for a projected layer.

| Line | Vertices (x, y) | ArcMap PLANAR | App | Difference |
|---|---|---|---|---|
| A | (350000, 3700000), (352000, 3701500) | 2,500.0000 m | 2,500.0000 m | 0 |
| B | (330000, 3680000), (390000, 3740000) | 84,852.8137 m | 84,852.8137 m | 0 |
| C | (335000, 3690000), (350000, 3720000), (365000, 3700000), (385000, 3730000) | 94,596.5324 m | 94,596.5324 m | 0 |

ArcMap GEODESIC on the same lines is longer (2,500.32 / 84,865.94 / 94,610.88 m, about 0.015%) because UTM shrinks distances slightly. A projected layer is measured on the grid, so the planar value is the one to compare.

Not yet compared with ArcMap: measuring a loaded line layer.

## Slope edges, percent rise, contours on a second DEM (23 Nov 2026)

| Check | Result |
|---|---|
| Percent-rise slope | Formula verified (rise x 100 = tan(slope) x 100). Min and max match ArcMap exactly. |
| Planar slope, edge cells | ArcMap fills a missing neighbour for slope, so border cells still get a value (needs at least 7 of 8 neighbours). Valid cells on the Dorre Island DEM: ArcMap 2,490,179, app 2,490,202. The value used for the one missing neighbour is close but not identical to ArcMap's (mean 9.4339 vs 9.4375). Curvature and aspect/hillshade reuse the same rule; curvature fills every missing neighbour with the centre value and matches ArcMap's valid-cell count (2,499,861). |
| Contours (Dorre Island, UTM and degree DEMs) | Same levels. ArcMap lines are about 0.3 to 0.5% longer (roughly twice the vertices) and ArcMap omits about 76 tiny loops. The app now skips zero-length loops and says so when no level falls inside the DEM range. |

## Area (geographic and projected polygons)

Test polygons drawn clockwise (ArcMap reads counter-clockwise shapefile rings as empty). ArcMap: Add Geometry Attributes (AREA_GEODESIC, PERIMETER_LENGTH_GEODESIC, and the planar fields). App: `polygon_area`.

| Polygon | ArcMap | App | Difference |
|---|---|---|---|
| Degree DEM, geodesic (73.3-73.5 E, 33.3-33.5 N) | 412,720,676.09 m2; perimeter 81,576.2803 m | 412,720,715.49 m2; 81,576.2746 m | 39 m2 in 412 km2 (1e-7); perimeter 6 mm |
| UTM 43N, planar (10 km square) | 100,000,000 m2; perimeter 40,000 m | 100,000,000 m2; 40,000 m | 0 |

Degree-DEM line length (geodesic): ArcMap 72,725.7757 m, app 72,725.7283 m (5 cm in 72.7 km). UTM line (planar): 48,899.79938 m both.

Not compared: surface (3D) area, which is hidden in the app behind a flag.

## Elevation Profile

ArcMap 3D Analyst, Stack Profile, on a 3-point line per DEM. The app profile was sampled at the same positions as ArcMap's output points (ArcMap samples about once per cell).

| DEM | ArcMap points | Largest difference |
|---|---|---|
| Degree tile (`ALPSMLC30_N033E073_DSM.tif`) | 2,645 | 0.00003 m |
| UTM (`dem_utm43.tif`) | 1,711 | 0.00003 m |
| 65 N tile (`ALPSMLC30_N065E060_DSM.tif`, 2" x 1" cells) | 2,668 | 0.00002 m |

On non-square cells (tiles above 60 N) ArcMap treats the raster as square cells of the smaller side before interpolating. The app does the same for the profile, for any cell ratio (`sample_bilinear(..., square_cells=True)`). Without it the 65 N profile differed by up to 11.8 m.

## Non-square cells and GEODESIC slope

ArcMap Slope (GEODESIC) on the 65 N tile writes a 1800 x 1800 output with 2" square cells, so it resamples the 3600 x 1800 input first. The app does the same (`core/raster/resample.py`, `square_cells`: area-weighted average of the covered cells, any ratio). Result against ArcMap: mean difference 0.17 degrees (largest 1.1) on a tile whose mean slope is 7 degrees. On a square-cell tile the same check gives 0.001 degrees (99.6% of cells within 0.01). ArcMap's exact resampling inside the Slope tool is not known: its own resampled DEM (Plus tool) is nearest-neighbour, but the slope agrees better with averaging.

GEODESIC slope border: ArcMap leaves the outermost ring of cells empty (3,598 x 3,598 valid cells on the 3,600 x 3,600 AW3D30 tile, 1,798 x 1,798 on the 65 N tile, 3,599 x 3,599 on the 3,601 x 3,601 SRTM tile). The app now does the same for geodesic slope on degree DEMs (`drop_border=True`). Planar slope still fills the border like ArcMap does. Geodesic aspect has not been checked for this and still fills.

## Second dataset: SRTM 1 arc-second (23 Nov 2026)

`n33_e073_1arc_v3.tif`, USGS SRTM 1 Arc-Second Global, tile N33 E073 (3601 x 3601, EPSG:4326, EGM96 heights, no voids). Opens in the app unchanged. ArcMap Slope GEODESIC (DEGREE) vs the app: mean 12.1314 vs 12.1301, max 72.070 vs 72.068; mean absolute difference 0.001 degrees, 99.87% of cells within 0.01 degrees, largest difference 0.106 degrees.

## Not yet validated
Layer Statistics and Histogram, surface (3D) area, aspect and hillshade on degree DEMs beyond the cases above, and the remaining tabs. Roughness, TPI and Ruggedness have no single ArcMap tool and were compared with Raster Calculator; their numbers still need to be added to this file.
