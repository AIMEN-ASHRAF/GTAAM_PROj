"""File > Export group."""
GROUP = {
    "label": "Export",
    "tools": [
        dict(id="export-raster", label="Export Raster", icon="image", kind="action",
             action="export_raster", tip="Save a raster layer as GeoTIFF, ASCII Grid or XYZ points"),
        dict(id="export-vector", label="Export Vector", icon="export", kind="action",
             action="export_vector", tip="Save a vector layer as GeoJSON, Shapefile, GeoPackage or CSV"),
        dict(id="export-map-image", label="Export Image", icon="image", kind="action",
             action="export_image", tip="Save the map view as a PNG or JPG picture"),
    ],
}
