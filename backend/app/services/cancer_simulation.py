"""Deterministic demonstration signal generator. It has no clinical interpretation."""
from datetime import date
from hashlib import sha256

RULE_VERSION = "cancer-demo-2026.10.1"
SCENARIO_RANGES = {
    "Lower review demo": (12, 34),
    "Balanced demo": (35, 66),
    "Higher review demo": (67, 89),
}
INDICATORS = ("Illustrative signal A", "Illustrative signal B", "Illustrative signal C")

def simulate(*, sample_type: str, panels: list[str], scenario: str, participant_code: str, age: int | None, collected_at: date) -> dict:
    """Return stable synthetic outputs keyed by the provided pseudonymous input set."""
    if sample_type != "photo":
        raise ValueError("Unsupported sample type")
    if scenario not in SCENARIO_RANGES:
        raise ValueError("Unsupported demonstration scenario")
    material = "|".join((sample_type, scenario, participant_code, str(age or ""), collected_at.isoformat(), *sorted(panels)))
    digest = sha256(material.encode("utf-8")).digest()
    low, high = SCENARIO_RANGES[scenario]
    score = low + int.from_bytes(digest[:2], "big") % (high - low + 1)
    readings = [] if sample_type == "photo" else [
        {"name": name, "value": round(0.1 + digest[i] / 255 * 9.8, 2), "unit": "demo units",
         "explanation": "Deterministic synthetic display value; no biological or clinical meaning.", "is_simulated": True}
        for i, name in enumerate(INDICATORS)
    ]
    if score < 35:
        category = "Lower simulated signal"
    elif score < 67:
        category = "Intermediate simulated signal"
    else:
        category = "Elevated simulated signal requiring professional review"
    return {
        "signal_score": score,
        "category": category,
        "readings": readings,
        "explanation": [
            f"The '{scenario}' demonstration preset selected a configured synthetic score range ({low}–{high}).",
            "The score is reproducible for the same demo inputs and is not calculated from medically validated relationships.",
            "The selected photo is not analyzed by this prototype; this score is a scenario-based synthetic workflow value only.",
        ],
        "missing_inputs": ["age"] if age is None else [],
        "rule_version": RULE_VERSION,
        "is_simulated": True,
        "disclaimer": "Prototype screening signal only. This is not a cancer probability, diagnosis, test result, or medical advice.",
    }
