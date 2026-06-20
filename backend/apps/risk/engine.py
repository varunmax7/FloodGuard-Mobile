"""
Risk engine — implements CONTRACT.md §3.2 exactly.

hazard_class  = bucket(rain_corrected_mm_per_h) with IDF thresholds
rain_corrected = rain_raw * bias.multiplier + bias.offset
risk_level    = RISK_MATRIX[hazard_class][susceptibility_bucket(fsi_score)]
confidence    = f(model_agreement, station_density_nearby, forecast_lead_time)
"""
from dataclasses import dataclass

# ── IDF thresholds (mm/h) — tunable via admin in Phase 12 ────────────────────
HAZARD_THRESHOLDS: list[float] = [7.5, 35.0, 64.5]

# ── 4×3 Risk matrix [hazard_class][susceptibility] → risk_level ───────────────
#   susceptibility:   LOW_SUSC  MED_SUSC  HIGH_SUSC
RISK_MATRIX: dict[str, list[str]] = {
    "LOW":      ["LOW",      "LOW",      "MODERATE"],
    "MODERATE": ["LOW",      "MODERATE", "HIGH"],
    "HIGH":     ["MODERATE", "HIGH",     "SEVERE"],
    "SEVERE":   ["HIGH",     "SEVERE",   "SEVERE"],
}

SUSCEPTIBILITY_BUCKETS = ["LOW", "MED", "HIGH"]
HAZARD_LEVELS = ["LOW", "MODERATE", "HIGH", "SEVERE"]


@dataclass
class RiskResult:
    rain_corrected: float
    hazard_class: str
    susceptibility: str
    risk_level: str
    confidence: int
    explanation: str


def bucket_hazard(rain_corrected_mm_per_h: float) -> str:
    """Classify corrected rainfall rate into hazard class per §3.2 IDF thresholds."""
    r = max(0.0, rain_corrected_mm_per_h)
    if r < HAZARD_THRESHOLDS[0]:
        return "LOW"
    elif r < HAZARD_THRESHOLDS[1]:
        return "MODERATE"
    elif r < HAZARD_THRESHOLDS[2]:
        return "HIGH"
    return "SEVERE"


def bucket_susceptibility(fsi_score: float) -> str:
    """Map FSI score to susceptibility bucket per §3.2."""
    if fsi_score < 0.33:
        return "LOW"
    elif fsi_score < 0.66:
        return "MED"
    return "HIGH"


def compute_confidence(
    lead_time_hours: float,
    has_station_obs: bool,
    station_count_nearby: int = 0,
) -> int:
    """
    Simplified confidence score [0, 100].
    - Base 70
    - +15 if a co-located AWS station confirms with an observation
    - +5 for each additional nearby station (up to 3)
    - -5 per hour of forecast lead time beyond 1h
    """
    score = 70
    if has_station_obs:
        score += 15
    score += min(station_count_nearby, 3) * 5
    extra_lead = max(0.0, lead_time_hours - 1.0)
    score -= int(extra_lead * 5)
    return max(10, min(100, score))


def compute_risk(
    rain_raw_1h: float,
    bias_multiplier: float,
    bias_offset: float,
    fsi_score: float,
    lead_time_hours: float = 1.0,
    has_station_obs: bool = False,
    station_count_nearby: int = 0,
) -> RiskResult:
    """
    Full risk computation per CONTRACT.md §3.2.

    Args:
        rain_raw_1h: Raw 1-hour precipitation from ECMWF (mm/h)
        bias_multiplier: Correction factor from BiasFactor
        bias_offset: Additive correction from BiasFactor
        fsi_score: Flood Susceptibility Index [0, 1]
        lead_time_hours: Hours ahead this forecast is valid for
        has_station_obs: Whether an AWS station in same hex has recent obs
        station_count_nearby: Number of nearby stations with obs

    Returns:
        RiskResult with all computed fields
    """
    rain_corrected = max(0.0, rain_raw_1h * bias_multiplier + bias_offset)

    hazard_class = bucket_hazard(rain_corrected)
    susceptibility = bucket_susceptibility(fsi_score)

    susc_idx = SUSCEPTIBILITY_BUCKETS.index(susceptibility)
    risk_level = RISK_MATRIX[hazard_class][susc_idx]

    confidence = compute_confidence(lead_time_hours, has_station_obs, station_count_nearby)

    explanation = (
        f"{rain_corrected:.1f} mm/h corrected rainfall "
        f"(raw {rain_raw_1h:.1f} mm/h × {bias_multiplier:.2f} + {bias_offset:.1f}) "
        f"→ {hazard_class} hazard; "
        f"FSI {fsi_score:.2f} → {susceptibility} susceptibility "
        f"→ {risk_level} risk."
    )

    return RiskResult(
        rain_corrected=round(rain_corrected, 3),
        hazard_class=hazard_class,
        susceptibility=susceptibility,
        risk_level=risk_level,
        confidence=confidence,
        explanation=explanation,
    )
