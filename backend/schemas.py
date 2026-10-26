from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)


class SafetyHazard(BaseModel):
    hazard: str = Field(default="")
    severity: Literal["Low", "Medium", "High", "Uncertain"] = "Uncertain"
    evidence: str = Field(default="")
    corrective_action: str = Field(default="")


class SafetyAnalysis(BaseModel):
    summary: str = Field(default="")
    overall_risk: Literal["Low", "Medium", "High", "Uncertain"] = "Uncertain"
    hazards: list[SafetyHazard] = Field(default_factory=list)
    ppe_concerns: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class CrackAnalysis(BaseModel):
    summary: str = Field(default="")
    crack_visible: bool = False
    characteristics: list[str] = Field(default_factory=list)
    category: str = Field(default="Undetermined")
    indicative_severity: Literal["Minor", "Moderate", "Severe", "Undetermined"] = "Undetermined"
    possible_causes: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ProjectPlanRequest(InputModel):
    project_type: str = Field(min_length=2, max_length=80)
    built_up_area_sqm: float = Field(gt=0, le=100_000)
    location: str | None = Field(default=None, max_length=120)
    floors: int = Field(default=1, ge=1, le=100)
    budget_inr: float | None = Field(default=None, gt=0, le=10_000_000_000)
    target_timeline_days: int | None = Field(default=None, ge=5, le=5_000)


class CostLineItem(BaseModel):
    phase: str
    estimated_cost_inr: float
    duration_days: int


class MaterialEstimate(BaseModel):
    material: str
    estimated_quantity: float
    unit: str
    note: str


class ProjectPlanResponse(BaseModel):
    estimate_status: Literal["INDICATIVE"]
    estimated_cost_inr: float
    cost_breakdown: list[CostLineItem]
    materials: list[MaterialEstimate]
    assumptions: list[str]
    exclusions: list[str]


class PropertyValuationRequest(InputModel):
    city: str = Field(min_length=2, max_length=100)
    locality: str | None = Field(default=None, max_length=120)
    property_type: Literal["Apartment", "Independent house", "Plot", "Commercial"]
    built_up_area_sqm: float = Field(gt=0, le=100_000)
    building_age_years: int = Field(default=0, ge=0, le=150)
    condition: Literal["Poor", "Average", "Good"]
    amenities: list[str] = Field(default_factory=list, max_length=20)
    reference_price_per_sqm_inr: float | None = Field(default=None, gt=0, le=10_000_000)
    reference_monthly_rent_inr: float | None = Field(default=None, gt=0, le=100_000_000)
    investment_cost_inr: float | None = Field(default=None, gt=0, le=10_000_000_000)


class PropertyValuationResponse(BaseModel):
    estimate_status: Literal["INDICATIVE", "NEEDS_LOCAL_REFERENCE_RATE"]
    currency: Literal["INR"] = "INR"
    estimated_value_range_inr: list[float] | None = None
    estimated_price_per_sqft_range_inr: list[float] | None = None
    estimated_monthly_rent_range_inr: list[float] | None = None
    gross_rental_yield_percent_range: list[float] | None = None
    adjustment_breakdown: list[str]
    assumptions: list[str]
    limitations: list[str]


class ChatTurn(InputModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4_000)


class ChatRequest(InputModel):
    message: str = Field(min_length=1, max_length=4_000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message must not be blank.")
        return value


class ChatResponse(BaseModel):
    reply: str
    caveats: list[str] = Field(default_factory=list)


class DailySiteRequest(InputModel):
    site_update: str = Field(min_length=1, max_length=5_000)
    planned_activities: list[str] = Field(default_factory=list, max_length=30)
    workforce_available: int | None = Field(default=None, ge=0, le=10_000)
    materials_and_equipment: list[str] = Field(default_factory=list, max_length=40)
    constraints: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("site_update")
    @classmethod
    def site_update_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Site update must not be blank.")
        return value


class DailySiteResponse(BaseModel):
    summary: str
    reported_progress: list[str] = Field(default_factory=list)
    pending_tasks: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    suggested_next_actions: list[str] = Field(default_factory=list)
    coordination_points: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class WeatherRequest(InputModel):
    activity: str = Field(min_length=2, max_length=200)
    location: str | None = Field(default=None, max_length=120)
    condition_description: str | None = Field(default=None, max_length=1_000)
    precipitation_mm_per_hour: float | None = Field(default=None, ge=0, le=1_000)
    wind_speed_kmh: float | None = Field(default=None, ge=0, le=500)
    temperature_c: float | None = Field(default=None, ge=-80, le=70)

    @field_validator("activity")
    @classmethod
    def activity_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Activity must not be blank.")
        return value


class WeatherResponse(BaseModel):
    recommendation: Literal["GO", "NO-GO", "INSUFFICIENT INFORMATION"]
    explanation: str
    risks: list[str] = Field(default_factory=list)
    precautions: list[str] = Field(default_factory=list)
    conditions_used: list[str] = Field(default_factory=list)
    source_label: str = "User-provided conditions; current weather was not independently verified."
    limitations: list[str] = Field(default_factory=list)
