"""Plain-language alert text generator — maps (risk_level, rain) → human strings."""

# (risk_level, hazard_class) → (headline, advice)
_TEXT: dict[tuple[str, str], tuple[str, str]] = {
    ("LOW",      "LOW"):      ("Light rain expected — Low flood risk",
                               "No action needed. Stay informed."),
    ("LOW",      "MODERATE"): ("Moderate rain expected — Low flood risk",
                               "No immediate action needed."),
    ("MODERATE", "LOW"):      ("Light rain — Moderate risk in flood-prone areas",
                               "Be cautious near low-lying zones."),
    ("MODERATE", "MODERATE"): ("Moderate rain — Moderate flood risk",
                               "Avoid unnecessary travel near flood-prone zones."),
    ("MODERATE", "HIGH"):     ("Heavy rain — Moderate flood risk",
                               "Avoid waterlogged roads. Stay alert."),
    ("MODERATE", "SEVERE"):   ("Very heavy rain — Moderate flood risk",
                               "Avoid low-lying areas. Have emergency plan ready."),
    ("HIGH",     "MODERATE"): ("Moderate rain — High flood risk in vulnerable areas",
                               "Avoid flood-prone streets. Follow GHMC alerts."),
    ("HIGH",     "HIGH"):     ("Heavy rain — High flood risk",
                               "Avoid low-lying roads. Move valuables to higher floors."),
    ("HIGH",     "SEVERE"):   ("Extremely heavy rain — High flood risk",
                               "Seek higher ground. Do not enter flooded streets."),
    ("SEVERE",   "HIGH"):     ("Heavy rain — Severe flood warning",
                               "Evacuate low-lying areas immediately. Follow authorities."),
    ("SEVERE",   "SEVERE"):   ("Extremely heavy rain — Severe flood emergency",
                               "Emergency alert. Evacuate immediately. Call 1916 (GHMC)."),
}

_DEFAULT: dict[str, tuple[str, str]] = {
    "LOW":      ("Low flood risk", "No action needed."),
    "MODERATE": ("Moderate flood risk", "Stay cautious near waterways."),
    "HIGH":     ("High flood risk", "Avoid flood-prone areas."),
    "SEVERE":   ("Severe flood warning", "Take immediate precautions."),
}


def generate(risk_level: str, hazard_class: str) -> tuple[str, str]:
    """
    Returns (plain_text headline, advice string).
    Falls back to risk_level-only text if the combination isn't mapped.
    """
    headline, advice = _TEXT.get(
        (risk_level, hazard_class),
        _DEFAULT.get(risk_level, ("Flood risk assessment available", "Stay informed.")),
    )
    return headline, advice
