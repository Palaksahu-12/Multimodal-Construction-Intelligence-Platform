import math

from schemas import (
    CostLineItem,
    MaterialEstimate,
    ProjectPlanRequest,
    ProjectPlanResponse,
    PropertyValuationRequest,
    PropertyValuationResponse,
)

SQM_PER_SQFT = 0.092903


def build_project_plan(request: ProjectPlanRequest) -> ProjectPlanResponse:
    project_type = request.project_type.lower()
    if "commercial" in project_type:
        assumed_cost_per_sqm = 25_000
    elif "renovation" in project_type:
        assumed_cost_per_sqm = 15_000
    else:
        assumed_cost_per_sqm = 20_000

    total_cost = request.budget_inr or request.built_up_area_sqm * assumed_cost_per_sqm
    total_days = request.target_timeline_days or max(90, math.ceil(request.built_up_area_sqm * 0.8))
    phase_data = [
        ("Design, approvals, and mobilization", 0.08, 0.15, []),
        ("Site preparation and foundation", 0.18, 0.20, ["Design, approvals, and mobilization"]),
        ("Structural frame and masonry", 0.32, 0.25, ["Site preparation and foundation"]),
        ("Electrical, plumbing, and services", 0.16, 0.15, ["Structural frame and masonry"]),
        ("Finishes, testing, and handover", 0.26, 0.25, ["Electrical, plumbing, and services"]),
    ]

    costs = [
        CostLineItem(
            phase=phase,
            estimated_cost_inr=round(total_cost * cost_share, 2),
            duration_days=max(1, round(total_days * duration_share)),
            depends_on=dependencies,
        )
        for phase, cost_share, duration_share, dependencies in phase_data
    ]
    costs[-1].estimated_cost_inr = round(total_cost - sum(item.estimated_cost_inr for item in costs[:-1]), 2)
    costs[-1].duration_days = max(1, total_days - sum(item.duration_days for item in costs[:-1]))

    area = request.built_up_area_sqm
    materials = [
        MaterialEstimate(
            material="Cement",
            estimated_quantity=round(area * 4.3, 1),
            unit="50 kg bags",
            note="Illustrative gross-area factor; depends on structural and finish design.",
        ),
        MaterialEstimate(
            material="Reinforcement steel",
            estimated_quantity=round(area * 38, 1),
            unit="kg",
            note="Very approximate planning allowance; must be replaced by engineer's bar schedule.",
        ),
        MaterialEstimate(
            material="Sand",
            estimated_quantity=round(area * 0.48, 2),
            unit="m³",
            note="Indicative allowance only; mix designs and local specifications vary.",
        ),
        MaterialEstimate(
            material="Coarse aggregate",
            estimated_quantity=round(area * 0.32, 2),
            unit="m³",
            note="Indicative allowance only; mix designs and local specifications vary.",
        ),
        MaterialEstimate(
            material="Masonry units",
            estimated_quantity=round(area * 86),
            unit="units",
            note="Broad allowance; wall layout and selected unit size are not modeled.",
        ),
    ]
    assumptions = [
        "Built-up area is treated as the total area across all floors; plot area is not used.",
        (
            f"Cost is based on the user-provided budget of INR {request.budget_inr:,.0f}."
            if request.budget_inr
            else (
                f"Cost uses an illustrative planning factor of INR {assumed_cost_per_sqm:,.0f}/m² "
                "and is not a current local-market quotation."
            )
        ),
        (
            f"Timeline uses the user-provided target of {request.target_timeline_days} days."
            if request.target_timeline_days
            else "Timeline is a coarse area-based planning allowance, not a contractor schedule."
        ),
        f"Project type: {request.project_type}; floors: {request.floors}."
        + (f" Location: {request.location}." if request.location else ""),
        "Material quantities are conceptual order-of-magnitude allowances, not construction drawings or a bill of quantities.",
    ]
    risks = [
        "Permitting, procurement lead times, weather, site access, and contractor availability may change the sequence or duration.",
        "Unknown soil, utilities, existing-condition defects, and design changes can materially affect cost and schedule.",
        "The indicative budget and material factors are not a quotation, engineered design, or verified local estimate.",
    ]
    return ProjectPlanResponse(
        estimate_status="INDICATIVE",
        estimated_cost_inr=round(total_cost, 2),
        estimated_duration_days=total_days,
        cost_breakdown=costs,
        materials=materials,
        assumptions=assumptions,
        risks=risks,
        exclusions=[
            "Land, taxes, financing, design fees, permits, utility connections, escalation, and site-specific works unless included in the user's budget.",
            "No live material prices, supplier quotations, soil report, structural design, or local code review is integrated.",
        ],
    )


def build_property_valuation(request: PropertyValuationRequest) -> PropertyValuationResponse:
    assumptions = [
        "This is an indicative arithmetic scenario, not a valuation or a market-data lookup.",
        "The supplied reference price per m² is treated as the user's local comparable-rate input for the stated property area.",
        "Illustrative age, condition, amenity, and uncertainty adjustments are not calibrated to local sales.",
    ]
    limitations = [
        "No live comparable transactions, listing data, title review, inspection, or locality-level market feed is connected.",
        "Do not use this output as a certified appraisal, lending decision, or investment guarantee.",
    ]
    if request.reference_price_per_sqm_inr is None:
        return PropertyValuationResponse(
            estimate_status="NEEDS_LOCAL_REFERENCE_RATE",
            adjustment_breakdown=[],
            assumptions=assumptions,
            limitations=[
                "Provide a verified local reference price per m² to calculate an indicative range.",
                *limitations,
            ],
        )

    is_plot = request.property_type == "Plot"
    age_adjustment = 0.0 if is_plot else min(request.building_age_years * 0.01, 0.30)
    condition_adjustments = {"Poor": -0.15, "Average": 0.0, "Good": 0.10}
    condition_adjustment = 0.0 if is_plot else condition_adjustments[request.condition]
    amenity_adjustment = 0.0 if is_plot else min(len(request.amenities) * 0.02, 0.10)
    multiplier = max(0.5, 1 - age_adjustment + condition_adjustment + amenity_adjustment)

    area = request.area_sqm
    central_rate = request.reference_price_per_sqm_inr * multiplier
    central_value = central_rate * area
    price_low, price_high = central_rate * 0.9, central_rate * 1.1
    value_low, value_high = price_low * area, price_high * area

    rent_range = None
    yield_range = None
    if request.reference_monthly_rent_inr is not None:
        rent_range = [
            round(request.reference_monthly_rent_inr * 0.9, 2),
            round(request.reference_monthly_rent_inr * 1.1, 2),
        ]
        if request.investment_cost_inr is not None:
            yield_range = [
                round(rent_range[0] * 12 / request.investment_cost_inr * 100, 2),
                round(rent_range[1] * 12 / request.investment_cost_inr * 100, 2),
            ]

    place = request.locality or request.city
    return PropertyValuationResponse(
        estimate_status="INDICATIVE",
        estimated_value_range_inr=[round(value_low, 2), round(value_high, 2)],
        estimated_price_per_sqft_range_inr=[
            round(price_low * SQM_PER_SQFT, 2),
            round(price_high * SQM_PER_SQFT, 2),
        ],
        estimated_monthly_rent_range_inr=rent_range,
        gross_rental_yield_percent_range=yield_range,
        adjustment_breakdown=[
            f"Location supplied: {place}, {request.city}; no independent locality data was retrieved.",
            f"Reference price: INR {request.reference_price_per_sqm_inr:,.0f}/m², supplied by the user.",
            (
                "Building age, condition, and amenity adjustments are not applied to a plot."
                if is_plot
                else f"Age adjustment: -{age_adjustment:.0%}; condition adjustment: {condition_adjustment:+.0%}."
            ),
            f"Amenity adjustment: +{amenity_adjustment:.0%} using a capped illustrative allowance.",
            f"Combined illustrative adjusted central value: INR {central_value:,.0f}.",
            "Displayed range is +/-10% around the adjusted estimate to reflect uncertainty, not a statistical confidence interval.",
        ],
        assumptions=assumptions,
        limitations=limitations,
    )
