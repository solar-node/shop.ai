"""Category-agnostic deterministic Product Analyst.
The LLM decides what matters; this module only performs reproducible math on supplied evidence.
"""
import math
from dataclasses import dataclass
from typing import Any, Dict, List

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

DEFAULT_WEIGHTS = {"quality": 0.42, "feature_match": 0.28, "price_value": 0.22, "availability": 0.08}

PRIOR_RATING = 3.8
PRIOR_REVIEW_WEIGHT = 100.0
VOLUME_REFERENCE = 5000.0


@dataclass
class RankedProduct:
    product_id: str
    name: str
    price: float
    utility_score: float
    components: Dict[str, float]
    image_url: str = ""
    flipkart_url: str = ""
    source: str = ""


def _bayesian_quality_score(rating: float, review_count: int) -> float:
    """Rating quality with high review-volume importance and Bayesian shrinkage.
    Products with higher review volumes gain significant statistical confidence,
    ensuring highly-reviewed products outrank low-volume items with few reviews.
    """
    r = min(max(float(rating or 0), 1.0), 5.0)
    v = max(int(review_count or 0), 0)
    adjusted = (v * r + PRIOR_REVIEW_WEIGHT * PRIOR_RATING) / (v + PRIOR_REVIEW_WEIGHT)
    volume_confidence = min(1.30, math.log1p(v) / math.log1p(VOLUME_REFERENCE))
    score = (adjusted / 5.0) * (0.40 + 0.60 * volume_confidence)
    return round(min(max(score, 0.0), 1.0), 4)


def _price_value_score(price: float, budget_max: float) -> float:
    """Budget value targeting score.
    Prioritizes products utilizing the allocated budget effectively (>= 90% sweet spot, e.g. > ₹9,000 on ₹10,000)
    to deliver better build quality and specs, rather than rewarding cheap low-end items (e.g. ₹5,000 on ₹10,000).
    """
    if price <= 0:
        return 0.0
    if budget_max <= 0:
        return 0.90
    if price > budget_max:
        return 0.0

    ratio = price / budget_max
    if 0.90 <= ratio <= 1.00:
        # Ideal budget utilization zone (>= 90%, e.g. ₹9,000–₹10,000 on ₹10,000 budget)
        return round(0.95 + 0.05 * ((ratio - 0.90) / 0.10), 4)
    elif 0.80 <= ratio < 0.90:
        # High tier (80%-90%, e.g. ₹8,000–₹9,000 on ₹10,000 budget)
        return round(0.70 + 0.25 * ((ratio - 0.80) / 0.10), 4)
    elif 0.60 <= ratio < 0.80:
        # Moderate zone (60%-80%, e.g. ₹6,000–₹8,000 on ₹10,000 budget)
        return round(0.30 + 0.40 * ((ratio - 0.60) / 0.20), 4)
    else:
        # Low-end underspending zone (< 60%, e.g. ₹5,000 on ₹10,000 budget)
        return round(0.05 + 0.25 * (ratio / 0.60), 4)





def _feature_match_score(candidate: dict, requirements: dict) -> float:
    """Score the LLM's evidence labels; no category/attribute vocabulary is required."""
    matched = {str(x).strip().lower() for x in candidate.get("matched_requirements", []) if str(x).strip()}
    missing = {str(x).strip().lower() for x in candidate.get("missing_requirements", []) if str(x).strip()}
    requested = [str(x).strip().lower() for x in (
        requirements.get("hard_constraints", []) + requirements.get("soft_preferences", [])
    ) if str(x).strip()]

    if requested:
        supported = sum(1 for r in requested if any(r == m or r in m or m in r for m in matched))
        unsupported = sum(1 for r in requested if any(r == m or r in m or m in r for m in missing))
        score = supported / len(requested)
        score -= 0.25 * (unsupported / len(requested))
        return round(min(max(score, 0.0), 1.0), 4)

    # If the LLM supplied no explicit requirements, do not fabricate a feature score.
    return 0.5


def _availability_score(qty: Any) -> float:
    try:
        return 1.0 if float(qty) > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


@traceable(run_type="chain", name="Bayesian Product Analyst Ranker")
def rank_products(candidates: list, budget_max: float, soft_preferences: List[str] = None,
                  weights: Dict[str, float] = None, brand_preference: str = "",
                  requirements: dict = None, user_goal: str = "") -> List[RankedProduct]:


    requirements = requirements or {"soft_preferences": soft_preferences or [], "hard_constraints": []}
    weights = weights or DEFAULT_WEIGHTS
    ranked = []
    for c in candidates:
        price = float(c.get("price") or c.get("effective_price") or 0)
        rating = float(c.get("rating") or 0)
        reviews = int(c.get("review_count") or 0)
        components = {
            "quality": _bayesian_quality_score(rating, reviews),
            "feature_match": _feature_match_score(c, requirements),
            "price_value": _price_value_score(price, float(budget_max or 0)),
            "availability": _availability_score(c.get("available_qty", 0)),
        }
        score = sum(components[k] * float(weights.get(k, 0)) for k in components)
        ranked.append(RankedProduct(
            product_id=str(c.get("product_id")), name=str(c.get("name", "Product")), price=price,
            utility_score=round(score, 4), components=components,
            image_url=c.get("image_url", ""), flipkart_url=c.get("flipkart_url", ""), source=c.get("source", "")
        ))
    return sorted(ranked, key=lambda x: (-x.utility_score, -x.components["quality"], x.price))


def weights_from_priority(priority: Any) -> Dict[str, float]:
    """Keep weights stable; user priorities are represented by LLM requirement matching.
    This avoids another hidden vocabulary map inside the mathematical ranker.
    """
    return dict(DEFAULT_WEIGHTS)
