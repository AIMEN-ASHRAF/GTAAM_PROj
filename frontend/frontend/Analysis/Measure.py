"""Analysis > Measure group."""
GROUP = {
    "label": "Measure",
    "tools": [
        dict(id="measure-distance", label="Distance", icon="ruler", kind="action",
             action="measure_distance", tip="Click points on the map to measure a distance"),

        dict(id="measure-area", label="Area", icon="area", kind="action",
             action="measure_area", tip="Click the corners of an area on the map to measure it"),

        dict(id="measure-profile", label="Elevation Profile", icon="profile", kind="action",
             action="measure_profile", tip="Draw a line on the map to see the height along it"),
    ],
}
