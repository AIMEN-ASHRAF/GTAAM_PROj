# Project Settings - backend ready (for Aimen)

Where: **File tab > Project group**, a new button "Project Settings" next to Save As. It opens a window.
The settings belong to the project: they are saved inside the .gtm file, come back when the project is opened,
and a new project starts at the defaults. Changing a setting marks the project as unsaved (the title shows `*`).

## The three fields (phase 1)

| Field | Values | Default | What it does |
|---|---|---|---|
| `analyze_in_utm` | true / false | false | ON: a degree (geographic) DEM is first moved to UTM (metres) and Hillshade, Slope, Aspect, Curvature, Roughness, TPI and Ruggedness run on that copy. OFF: they run on the degrees as before. |
| `utm_zone` | `"auto"` or `"1N"`..`"60N"` / `"1S"`..`"60S"` | `"auto"` | auto = the zone under the centre of the DEM. |
| `resampling` | `"nearest"`, `"bilinear"`, `"cubic"` | `"bilinear"` | How the heights are moved to UTM. bilinear is smoothest for slopes; nearest keeps the original heights untouched. |

A layer that is already in metres (UTM, ...) is never changed by this switch.
Not affected by the switch: Distance, Area, Elevation Profile, Layer Statistics, Histogram, NoData Check, Outlier Check and Contours
(they keep using the layer as loaded).
UTM only exists between 80 S and 84 N; for a DEM outside that the tool answers 400 "UTM is only defined ..." - show it as a message.

## Calls (all under `/api/v1/file/project`)

* `GET  /settings` -> `{"analyze_in_utm": false, "utm_zone": "auto", "resampling": "bilinear"}`
* `PUT  /settings` with any of the three fields -> the full settings. Only the fields sent change. 422 for a bad zone or resampling.
* `GET  /settings/utm-preview?layer_id=<id>` -> `{"applies": true, "zone": "43N", "epsg": 32643, "reason": null}`.
  Use it for a live line under the switch, e.g. "Will use UTM 43N for ALPSMLC30_N033E073_DSM". `applies: false` + `reason` for a layer already in metres.

Python client: `api.file.project_settings()`, `api.file.update_project_settings(analyze_in_utm=True, utm_zone="43N", resampling="bilinear")`, `api.file.utm_preview(layer_id)`.

## What comes back when it is ON

The new layer is in UTM: `layer.crs == "EPSG:32643"`, its name has the zone ("ALPS... (UTM 43N) - slope (degrees)") and
`layer.meta.analysis_utm = {"zone": "43N", "epsg": 32643, "resampling": "bilinear"}`. The window can show a small "UTM 43N" badge from that.

## Suggested window (all optional extras are later phases)

Phase 1 (now): the switch, "Zone: Auto / pick", "Resampling" drop-down, and the preview line.
Later: distance and area units, decimal places, default colour ramp (already stored in `workspace.options`), "match ArcMap" tick box.

## Honest numbers (AW3D30 N033E073, Slope)

Degrees, geodesic: mean 12.99 deg. UTM, bilinear: mean 12.62-12.71 deg (about 2-3 % lower because bilinear resampling smooths the terrain a little).
Use `nearest` if you need the original heights kept as they are.


## All settings (24 Nov 2026 update)
The window now has five pages (Coordinate System, Units & Analysis, Display, Project, Performance). Every field is
validated by the backend and saved in the .gtm file; an old project gets the defaults.

| Group | Field | Allowed values (default first) |
|---|---|---|
| Coordinate system | analyze_in_utm / utm_zone / resampling | false, true / auto, 1N..60S / bilinear, nearest, cubic |
| Units | distance_unit | metres, kilometres, feet, miles |
| | area_unit | hectares, square_metres, square_kilometres, acres |
| | height_unit / slope_unit | metres, feet / degrees, percent |
| Analysis defaults | match_arcmap, slope_method | true / planar, geodesic |
| | hillshade_azimuth, hillshade_altitude, contour_interval | 315, 45, 100 |
| Display | decimal_places, scale_bar, coordinate_format | 4 (0-8), true, decimal / dms |
| Project | author, auto_save_minutes | "", 0 / 1, 5, 10, 30 |
| Performance | preview_resolution, memory_limit_mb | high (low, medium, high, full), 0 / 512..4096 |

**What changes results today:** Analyze in UTM, UTM zone, resampling (backend). **Applied by the frontend:** analysis defaults (slope units and method, aspect method, hillshade azimuth/altitude,
contour interval): a tool field tagged `setting="..."` opens with the project's saved value. **Also applied:** decimal places and height unit (Statistics cards), distance unit (Distance and Elevation Profile windows), area unit (Area window).
Also applied: Match ArcMap (forces planar and hillshade 315/45 in the tool defaults), scale bar (same switch as View), coordinate format (decimal or DMS in the Pixel Inspector), auto-save (checked once a minute; saves only a project that already has a file and unsaved changes).
Author: stamped as a credit line (author and date) on exported map images.
**Stored only so far:** preview resolution, memory limit.


## Known limitation: layers in different coordinate systems on the map
The map canvas draws every raster on its own pixel grid, from the top-left. A UTM result (3326 x 3949 cells) drawn over the
degree DEM (3600 x 3600 cells) therefore does not line up, even though the values are correct. The Properties panel now
shows "Map placement: Own grid" for such a layer. A true fix means placing each raster by its real bounds in the canvas
coordinate system, which touches contours, measure tools, the pixel inspector and region editing (all use cell
coordinates today). It should be done by the frontend owner with the GUI open to test.
