"""Transparent demonstration rules; these do not represent clinical cutoffs."""
RULE_VERSION = "demo-2026.10.1"
RULE_CONFIG = {
    "version": RULE_VERSION,
    "categories": ["Low priority", "Moderate priority", "High priority"],
    "case_weights": {"Lower review demo": 0, "Balanced demo": 1, "Higher review demo": 2},
    "missing_data": "Return a warning; never assume normal.",
    "clinical_thresholds": None,
}

def assess(case_type: str, panel_count: int, sample_type: str) -> dict:
    score = RULE_CONFIG["case_weights"][case_type]
    reasons = [f"Preset '{case_type}' contributed {score} demonstration points."]
    if panel_count > 1:
        score += 1
        reasons.append("Multiple selected demo panels contributed one workflow point.")
    if sample_type != "photo":
        reasons.append("Oral photo input was missing or unsupported.")
        missing = ["sample_type"]
    else:
        missing = []
        reasons.append("Oral photo input was recorded for human review; this system does not interpret the image.")
    category = "High priority" if score >= 2 else "Moderate priority" if score == 1 else "Low priority"
    return {"category": category, "explanation": reasons, "missing_inputs": missing,
            "rule_version": RULE_VERSION, "is_simulated": True,
            "disclaimer": "Synthetic workflow priority only; not a diagnosis, disease probability, or medical advice."}
