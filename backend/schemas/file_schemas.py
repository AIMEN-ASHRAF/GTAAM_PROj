from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class IdentifyRequest(BaseModel):
    x: float
    y: float
    tolerance: float = Field(gt=0, description="how close counts as a hit, in the units of `crs`")
    crs: str | None = Field("EPSG:4326", description="coordinate system of x, y")


class ProjectNew(BaseModel):
    name: str = Field("Untitled project", min_length=1, max_length=120)


class ProjectPath(BaseModel):
    path: str = Field(min_length=1)


class CanvasLayer(BaseModel):
    """One layer as one map canvas shows it."""
    id: str = Field(min_length=1)
    visible: bool = True
    opacity: float = Field(1.0, ge=0.0, le=1.0)


class Canvas(BaseModel):
    """A map canvas: its own list of layers (top first), view and drawn regions.
    The layer data itself is shared - a layer can be in several canvases."""
    id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=120)
    view: dict | None = None          # zoom and pan, kept for the window
    regions: list | None = None       # editing regions drawn on this canvas
    layers: list[CanvasLayer] = []

    @field_validator("layers")
    @classmethod
    def _no_duplicate_layers(cls, v: list[CanvasLayer]) -> list[CanvasLayer]:
        ids = [l.id for l in v]
        if len(ids) != len(set(ids)):
            raise ValueError("a layer can appear only once in a canvas")
        return v


class CanvasSet(BaseModel):
    canvases: list[Canvas] | None = None     # omit to keep the canvases the project already has
    active_canvas: str | None = None

    @model_validator(mode="after")
    def _check_canvases(self):
        if self.canvases is None:
            return self
        ids = [c.id for c in self.canvases]
        if len(ids) != len(set(ids)):
            raise ValueError("canvas ids must be unique")
        if self.active_canvas is not None and self.active_canvas not in ids:
            raise ValueError("active_canvas must be one of the canvases")
        return self


class ProjectSave(CanvasSet):
    path: str | None = None           # omit to save over the current file
    name: str | None = None           # project name (Save As: usually the file name)
    gui: dict | None = None           # the window's own state, stored in the project


class ProjectSaveAs(ProjectPath, CanvasSet):
    name: str | None = None
    gui: dict | None = None


class ProjectInfo(BaseModel):
    name: str
    path: str | None = None
    dirty: bool
    layer_count: int
    created: str


class SaveResult(ProjectInfo):
    saved_layers: int
    skipped_layers: list[str] = []    # layers that could not be written to disk


class OpenResult(ProjectInfo):
    missing_layers: list[str] = []
    gui: dict = {}                    # window state saved with the project
    canvases: list[Canvas] = []       # the map canvases (always at least one)
    active_canvas: str | None = None
    layers: list[dict] = []           # every layer, top first (rasters carry a "display" bundle)


class AddRasterRequest(BaseModel):
    path: str = Field(min_length=1)
    name: str | None = None


class AddVectorRequest(BaseModel):
    path: str = Field(min_length=1)   # a vector file, or a .gdb folder
    name: str | None = None
    layer: str | None = None          # which layer of a multi-layer file (GeoPackage, geodatabase ...)


class VectorLayerNames(BaseModel):
    layers: list[str]                 # empty for files that hold one thing


class AddBasemapRequest(BaseModel):
    name: str = Field(min_length=1)
    url_template: str = Field(min_length=1)   # e.g. https://tile.openstreetmap.org/{z}/{x}/{y}.png
    attribution: str | None = None


class LayerUpdate(BaseModel):
    name: str | None = None
    visible: bool | None = None
    opacity: float | None = Field(None, ge=0, le=1)


class LayerOrder(BaseModel):
    layer_ids: list[str]              # top of the drawing order first


class ExportElevationsRequest(BaseModel):
    layer_id: str
    path: str = Field(min_length=1)
    format: Literal["geotiff", "ascii", "xyz"] = "geotiff"
    nodata: float | None = None          # value written for empty cells (GeoTIFF / ASCII)


class ExportVectorRequest(BaseModel):
    layer_id: str
    path: str = Field(min_length=1)
    format: Literal["geojson", "shapefile", "gpkg", "csv"] = "geojson"


class FullscreenRequest(BaseModel):
    enabled: bool


class ProjectSettings(BaseModel):
    """Per-project analysis settings (saved inside the project file)."""
    analyze_in_utm: bool = False                    # move degree DEMs to UTM (metres) before terrain analysis
    utm_zone: str = "auto"                          # 'auto' or e.g. '43N' / '41S'
    resampling: Literal["nearest", "bilinear", "cubic"] = "bilinear"   # used when moving to UTM


class ProjectSettingsUpdate(BaseModel):
    """Only the fields that are sent are changed."""
    analyze_in_utm: bool | None = None
    utm_zone: str | None = Field(default=None, pattern=r"^(?i:auto|([1-9]|[1-5][0-9]|60)[NS])$")
    resampling: Literal["nearest", "bilinear", "cubic"] | None = None


class UtmPreview(BaseModel):
    """What 'Analyze in UTM' would do for one layer (so the window can show it before running)."""
    applies: bool                                   # False for a layer that is already in metres
    zone: str | None = None                         # '43N'
    epsg: int | None = None
    reason: str | None = None
