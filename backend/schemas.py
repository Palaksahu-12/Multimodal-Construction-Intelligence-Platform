import math
from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class InputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)


class OutputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)


class SafetyHazard(OutputModel):
    hazard: str = Field(min_length=1)
    severity: Literal["Low", "Medium", "High", "Uncertain"]
    evidence: str = Field(min_length=1)
    corrective_action: str = Field(min_length=1)


class SafetyAnalysis(OutputModel):
    summary: str = Field(min_length=1)
    overall_risk: Literal["Low", "Medium", "High", "Uncertain"]
    hazards: list[SafetyHazard]
    ppe_concerns: list[str]
    limitations: list[str] = Field(min_length=1)


class CrackAnalysis(OutputModel):
    summary: str = Field(min_length=1)
    crack_visible: bool
    characteristics: list[str]
    category: str = Field(min_length=1)
    indicative_severity: Literal["Minor", "Moderate", "Severe", "Undetermined"]
    possible_causes: list[str]
    concerns: list[str]
    recommended_next_steps: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)


class ProjectPlanRequest(InputModel):
    project_type: Literal["Residential", "Commercial", "Renovation"]
    built_up_area_sqm: float = Field(gt=0, le=100_000)
    location: str | None = Field(default=None, max_length=120)
    floors: int = Field(default=1, ge=1, le=100)
    budget_inr: float | None = Field(default=None, gt=0, le=10_000_000_000)
    target_timeline_days: int | None = Field(default=None, ge=5, le=5_000)


class CostLineItem(OutputModel):
    phase: str = Field(min_length=1)
    estimated_cost_inr: float = Field(ge=0)
    duration_days: int = Field(ge=1)
    depends_on: list[str]


class MaterialEstimate(OutputModel):
    material: str
    estimated_quantity: float
    unit: str
    note: str


class ProjectPlanResponse(OutputModel):
    estimate_status: Literal["INDICATIVE"]
    estimated_cost_inr: float = Field(gt=0)
    estimated_duration_days: int = Field(ge=1)
    cost_breakdown: list[CostLineItem]
    materials: list[MaterialEstimate]
    assumptions: list[str] = Field(min_length=1)
    risks: list[str] = Field(min_length=1)
    exclusions: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def totals_match_breakdown(self):
        if not self.cost_breakdown:
            raise ValueError("At least one project phase is required.")
        breakdown_cost = sum(item.estimated_cost_inr for item in self.cost_breakdown)
        if not math.isclose(breakdown_cost, self.estimated_cost_inr, abs_tol=0.01):
            raise ValueError("Project phase costs must sum to the estimated total.")
        if sum(item.duration_days for item in self.cost_breakdown) != self.estimated_duration_days:
            raise ValueError("Project phase durations must sum to the estimated total duration.")
        return self


class PropertyValuationRequest(InputModel):
    city: str = Field(min_length=2, max_length=100)
    locality: str | None = Field(default=None, max_length=120)
    property_type: Literal["Apartment", "Independent house", "Plot", "Commercial"]
    area_sqm: float = Field(
        gt=0,
        le=100_000,
        validation_alias=AliasChoices("area_sqm", "built_up_area_sqm"),
    )
    building_age_years: int = Field(default=0, ge=0, le=150)
    condition: Literal["Poor", "Average", "Good"] = "Average"
    amenities: list[str] = Field(default_factory=list, max_length=20)
    reference_price_per_sqm_inr: float | None = Field(default=None, gt=0, le=10_000_000)
    reference_monthly_rent_inr: float | None = Field(default=None, gt=0, le=100_000_000)
    investment_cost_inr: float | None = Field(default=None, gt=0, le=10_000_000_000)


class PropertyValuationResponse(OutputModel):
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


class ChatResponse(OutputModel):
    reply: str = Field(min_length=1)
    caveats: list[str]


class DailySiteRequest(InputModel):
    site_update: str = Field(min_length=1, max_length=5_000)
    planned_activities: list[str] = Field(default_factory=list, max_length=30)
    workforce_available: int | None = Field(default=None, ge=0, le=10_000)
    materials_and_equipment: list[str] = Field(default_factory=list, max_length=40)
    constraints: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("planned_activities", "materials_and_equipment", "constraints")
    @classmethod
    def validate_list_items(cls, values: list[str]) -> list[str]:
        if any(not value or len(value) > 300 for value in values):
            raise ValueError("List items must contain 1 to 300 characters.")
        return values

    @field_validator("site_update")
    @classmethod
    def site_update_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Site update must not be blank.")
        return value


class DailySiteResponse(OutputModel):
    summary: str = Field(min_length=1)
    reported_progress: list[str]
    pending_tasks: list[str]
    risks: list[str]
    suggested_next_actions: list[str]
    coordination_points: list[str]
    limitations: list[str] = Field(min_length=1)


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


class WeatherResponse(OutputModel):
    recommendation: Literal["GO", "NO-GO", "INSUFFICIENT INFORMATION"]
    explanation: str = Field(min_length=1)
    risks: list[str]
    precautions: list[str]
    conditions_used: list[str] = Field(default_factory=list)
    source_label: str = "User-provided conditions; current weather was not independently verified."
    limitations: list[str] = Field(min_length=1)
