from typing import Literal
from pydantic import BaseModel, Field, model_validator


class EdgeInput(BaseModel):
    left_stitches: int = Field(0, ge=0)
    right_stitches: int = Field(0, ge=0)
    left_operation: str = "K"
    right_operation: str = "K"


class SwatchInput(BaseModel):
    stitches: int = Field(..., gt=0)
    rows: int = Field(..., gt=0)
    yarn_length_m: float = Field(..., gt=0)


class CalculationRequest(BaseModel):
    pattern_id: str
    pattern_version: str = "1.0.0"
    yarn_id: str | None = None
    width_cm: float = Field(..., gt=0)
    height_cm: float = Field(..., gt=0)
    gauge_stitches_per_10cm: float = Field(..., gt=0)
    gauge_rows_per_10cm: float = Field(..., gt=0)
    allowance_percent: float = Field(0.0, ge=0, le=50)
    partial_repeat_mode: Literal["reject", "left", "right", "split", "center"] = "reject"
    edges: EdgeInput = EdgeInput()
    # "auto": measured swatch if supplied, else approved calibration model if one exists,
    # else the uncalibrated crochet geometry baseline. Calibration is a supplement, not a gate.
    calculation_mode: Literal["auto", "swatch", "geometry", "calibrated", "crochet_baseline"] = "auto"
    domain_policy: Literal["strict","warn","research"] = "strict"
    swatch: SwatchInput | None = None
    yarn_diameter_mm: float | None = Field(None, gt=0)
    hook_mm: float | None = Field(None, gt=0)
    # The shade being made in. It changes nothing about the arithmetic; it is
    # carried so the work log records which colour the piece was for.
    colour_id: str | None = None
    title: str | None = None

    @model_validator(mode="after")
    def validate_mode(self):
        if self.calculation_mode == "swatch" and self.swatch is None:
            raise ValueError("swatch data are required for measured-swatch mode")
        if self.calculation_mode == "geometry" and self.yarn_diameter_mm is None:
            raise ValueError("yarn_diameter_mm is required for research geometry mode")
        return self


class EditorCellInput(BaseModel):
    row: int = Field(..., ge=1)
    col: int = Field(..., ge=1)
    operation_id: str
    span: int = Field(1, ge=1)

class EditorPatternInput(BaseModel):
    pattern_id: str
    version: str = "1.0.0"
    name: str
    width: int = Field(..., ge=1, le=500)
    height: int = Field(..., ge=1, le=500)
    cells: list[EditorCellInput]

class SavePatternRequest(BaseModel):
    pattern: EditorPatternInput
    family_id: str = "CUSTOM"
    difficulty: Literal["basic","easy","intermediate","experienced","unknown"] = "unknown"
    tags: list[str] = []
    techniques: list[str] = []


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    calculation: CalculationRequest
    result: dict | None = None
    status: Literal["draft","calculated","archived"] = "draft"

class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    calculation: CalculationRequest | None = None
    result: dict | None = None
    status: Literal["draft","calculated","archived"] | None = None


class YarnCreateRequest(BaseModel):
    yarn_id: str = Field(..., min_length=1, max_length=100)
    brand: str = Field(..., min_length=1, max_length=200)
    product: str = Field(..., min_length=1, max_length=200)
    variant: str | None = None
    cyc_weight: int | None = Field(None, ge=0, le=7)
    package_mass_g: float = Field(..., gt=0)
    package_length_m: float = Field(..., gt=0)
    fibre_composition: dict[str,float]
    tex: float | None = Field(None, gt=0)
    nominal_diameter_mm: float | None = Field(None, gt=0)
    wpi: float | None = Field(None, gt=0)
    recommended_needle_min_mm: float | None = Field(None, gt=0)
    recommended_needle_max_mm: float | None = Field(None, gt=0)
    description: str | None = Field(None, max_length=4000)
    photo_url: str | None = Field(None, max_length=1000)
    product_line: str | None = Field(None, max_length=200)
    price_amount: float | None = Field(None, gt=0)
    price_currency: str | None = Field(None, min_length=3, max_length=3)

    @model_validator(mode="after")
    def fibre_total(self):
        if abs(sum(self.fibre_composition.values())-100.0)>0.05:
            raise ValueError("fibre composition must total 100%")
        return self


class YarnExtraUpdateRequest(BaseModel):
    """Collaborative/editorial fields any signed-in user may update on a yarn:
    an indicative price is explicitly approximate ("orientacni") and can be
    kept current by the community, unlike the sourced technical fields."""
    description: str | None = Field(None, max_length=4000)
    photo_url: str | None = Field(None, max_length=1000)
    product_line: str | None = Field(None, max_length=200)
    price_amount: float | None = Field(None, gt=0)
    price_currency: str | None = Field(None, min_length=3, max_length=3)


class SupplierCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    price_amount: float | None = Field(None, gt=0)
    price_currency: str | None = Field(None, min_length=3, max_length=3)
    product_url: str | None = Field(None, max_length=1000)
    notes: str | None = Field(None, max_length=1000)


class StashUpsertRequest(BaseModel):
    yarn_id: str = Field(..., min_length=1, max_length=100)
    quantity_g: float | None = Field(None, ge=0)
    quantity_skeins: float | None = Field(None, ge=0)
    notes: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def quantity_present(self):
        if self.quantity_g is None and self.quantity_skeins is None:
            raise ValueError("quantity_g or quantity_skeins is required")
        return self


class ProductLineCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=4000)
    photo_url: str | None = Field(None, max_length=1000)
    product_url: str | None = Field(None, max_length=1000)


class ProductLineUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=4000)
    photo_url: str | None = Field(None, max_length=1000)
    product_url: str | None = Field(None, max_length=1000)


class ProductMaterialCreateRequest(BaseModel):
    yarn_id: str = Field(..., min_length=1, max_length=100)
    length_m: float | None = Field(None, gt=0)
    quantity_g: float | None = Field(None, gt=0)
    notes: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def quantity_present(self):
        if self.length_m is None and self.quantity_g is None:
            raise ValueError("length_m or quantity_g is required")
        return self


class CompanySettingsRequest(BaseModel):
    company_name: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=1000)
    company_number: str | None = Field(None, max_length=100)
    vat_number: str | None = Field(None, max_length=100)
    email: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=100)
    website: str | None = Field(None, max_length=300)

class SwatchCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    pattern_id: str
    pattern_version: str
    yarn_id: str
    needle_mm: float | None = Field(None, gt=0)
    stitches: int = Field(..., gt=0)
    rows: int = Field(..., gt=0)
    width_cm: float = Field(..., gt=0)
    height_cm: float = Field(..., gt=0)
    yarn_length_m: float | None = Field(None, gt=0)
    yarn_mass_g: float | None = Field(None, gt=0)
    notes: str | None = Field(None, max_length=4000)

    @model_validator(mode="after")
    def consumption_present(self):
        if self.yarn_length_m is None and self.yarn_mass_g is None:
            raise ValueError("at least yarn_length_m or yarn_mass_g is required")
        return self
