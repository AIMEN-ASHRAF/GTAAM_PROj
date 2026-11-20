from typing import Literal

from pydantic import BaseModel, Field, model_validator

from schemas.common import XY


class LayerRequest(BaseModel):
    layer_id: str = Field(min_length=1)


class AspectRequest(LayerRequest):
    flat_as_minus_one: bool = False
    method: Literal["planar", "geodesic"] = "planar"


class DistanceRequest(LayerRequest):
    points: list[XY] | None = Field(None, min_length=2)    # map coordinates (the layer's CRS)
    pixels: list[XY] | None = Field(None, min_length=2)    # clicked cells as (row, col)
    units: Literal["metres", "kilometres", "feet", "miles", "auto"] = "metres"   # auto: m below 1 km, else km
    include_elevation: bool = True
    snap: bool = False                  # move each click to the centre of its cell

    @model_validator(mode="after")
    def _one_kind_of_point(self):
        if (self.points is None) == (self.pixels is None):
            raise ValueError("Send either 'points' or 'pixels', not both and not neither.")
        return self


class AreaRequest(LayerRequest):
    polygon: list[XY] | None = Field(None, min_length=3)   # map coordinates (the layer's CRS)
    pixels: list[XY] | None = Field(None, min_length=3)    # clicked cells as (row, col)
    units: Literal["square metres", "hectares", "square kilometres", "acres", "square miles", "auto"] = "square metres"
    include_surface: bool = False       # also the 3D surface area (uses the DEM heights)

    @model_validator(mode="after")
    def _one_kind_of_point(self):
        if (self.polygon is None) == (self.pixels is None):
            raise ValueError("Send either 'polygon' or 'pixels', not both and not neither.")
        return self


class ProfileRequest(LayerRequest):
    line: list[XY] | None = Field(None, min_length=2)      # map coordinates (the layer's CRS)
    pixels: list[XY] | None = Field(None, min_length=2)    # clicked cells as (row, col)
    samples: int = Field(200, ge=2, le=5000)
    units: Literal["metres", "kilometres", "feet", "miles", "auto"] = "metres"   # distance axis only

    @model_validator(mode="after")
    def _one_kind_of_point(self):
        if (self.line is None) == (self.pixels is None):
            raise ValueError("Send either 'line' or 'pixels', not both and not neither.")
        return self


class HillshadeRequest(LayerRequest):
    azimuth: float = Field(315, ge=0, le=360)
    altitude: float = Field(45, ge=0, le=90)
    z_factor: float = Field(1.0, gt=0)


class SlopeRequest(LayerRequest):
    units: Literal["degrees", "percent"] = "degrees"
    method: Literal["planar", "geodesic"] = "planar"     # like ArcMap's Method: Horn, or least-squares plane


class ContoursRequest(LayerRequest):
    interval: float = Field(100.0, gt=0)
    base: float = 0.0
