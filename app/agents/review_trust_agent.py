"""Review/trust research policy. Numeric review evidence is kept separate from LLM opinion."""
import math


def research_review_trust(requirements: dict) -> dict:
    """Return the statistical model parameters used by the deterministic analyst."""
    return {
        "rating_scale": [1.0, 5.0],
        "prior_rating": 3.8,
        "prior_weight": 150.0,
        "volume_reference": 10000.0,
        "volume_transform": "logarithmic",
        "interpretation": "Higher review volume increases confidence; it does not replace product fit.",
    }


def score_review_evidence(rating: float, review_count: int, model: dict) -> dict:
    r = min(max(float(rating or 0), 1.0), 5.0)
    v = max(int(review_count or 0), 0)
    m = float(model.get("prior_weight", 150.0))
    c = float(model.get("prior_rating", 3.8))
    adjusted = (v * r + m * c) / (v + m)
    confidence = min(1.2, math.log1p(v) / math.log1p(float(model.get("volume_reference", 10000))))
    return {"rating": r, "review_count": v, "adjusted_rating": round(adjusted, 4), "volume_confidence": round(confidence, 4)}
