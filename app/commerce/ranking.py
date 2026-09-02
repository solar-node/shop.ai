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

DEFAULT_WEIGHTS = {"feature_match": 0.35, "quality": 0.30, "price_value": 0.25, "availability": 0.10}

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
    """Rating quality with review-volume confidence and Bayesian shrinkage.
    Formula: R_adj = (v * R + m * C) / (v + m)
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


def _feature_match_score(candidate: dict, requirements: dict, user_goal: str = "") -> float:
    """Score evidence-backed requirement and specification match."""
    if "feature_match_score" in candidate and isinstance(candidate["feature_match_score"], (int, float)):
        return float(candidate["feature_match_score"])

    from app.commerce.spec_extractor import match_requirements_against_product
    _, _, score = match_requirements_against_product(candidate, requirements, user_goal)
    return score


def _availability_score(qty: Any, availability_status: Any = "in_stock") -> float:
    """Stock availability score:
    - In stock with verified quantity > 0: 1.0
    - Active marketplace listing / in_stock: 1.0
    - Unknown stock status: 0.85 (neutral/available)
    - Confirmed out of stock: 0.0
    """
    if isinstance(qty, (int, float)):
        if qty <= 0:
            return 0.0
        return 1.0

    if isinstance(availability_status, str):
        s = availability_status.strip().lower()
        if any(w in s for w in ("out of stock", "unavailable", "sold out", "oos")):
            return 0.0
        if any(w in s for w in ("in stock", "in_stock", "available", "free delivery", "delivery")):
            return 1.0

    return 0.85


@traceable(run_type="chain", name="Bayesian Product Analyst Ranker")
def rank_products(candidates: list, budget_max: float, soft_preferences: List[str] = None,
                  weights: Dict[str, float] = None, brand_preference: str = "",
                  requirements: dict = None, user_goal: str = "") -> List[RankedProduct]:

    requirements = requirements or {"soft_preferences": soft_preferences or [], "hard_constraints": [], "brand_preference": brand_preference}
    weights = weights or weights_from_priority(requirements.get("priority_order"), requirements, user_goal)
    ranked = []
    
    for c in candidates:
        price = float(c.get("price") or c.get("effective_price") or 0)
        rating = float(c.get("rating") or 0)
        reviews = int(c.get("review_count") or 0)
        components = {
            "feature_match": _feature_match_score(c, requirements, user_goal),
            "quality": _bayesian_quality_score(rating, reviews),
            "price_value": _price_value_score(price, float(budget_max or 0)),
            "availability": _availability_score(c.get("available_qty"), c.get("availability")),
        }
        score = sum(components[k] * float(weights.get(k, 0)) for k in components)
        ranked.append(RankedProduct(
            product_id=str(c.get("product_id")), name=str(c.get("name", "Product")), price=price,
            utility_score=round(score, 4), components=components,
            image_url=c.get("image_url", ""), flipkart_url=c.get("flipkart_url", ""), source=c.get("source", "")
        ))
    return sorted(ranked, key=lambda x: (-x.utility_score, -x.components["feature_match"], -x.components["quality"], x.price))


def weights_from_priority(priority: Any = None, requirements: dict = None, user_goal: str = "") -> Dict[str, float]:
    """Dynamically adjusts ranking weights when user explicitly specifies priorities."""
    text = (str(user_goal) + " " + " ".join(str(p) for p in (priority or []))).lower()
    
    # 1. Feature / Performance / Specification heavy priorities
    if any(w in text for w in ("prioritize performance", "performance over", "camera quality is highest", "highest priority", "main priority", "anc is must", "highest spec")):
        return {"feature_match": 0.45, "quality": 0.25, "price_value": 0.20, "availability": 0.10}

    # 2. Budget / Cost Saver priorities
    if any(w in text for w in ("cheapest", "lowest price", "budget saver", "most economical", "tight budget", "price first")):
        return {"feature_match": 0.28, "quality": 0.25, "price_value": 0.37, "availability": 0.10}

    # 3. Brand / Trust / Rating priorities
    if any(w in text for w in ("reliable brand", "prefer a reliable", "highest rated", "top rated", "most trusted", "best brand")):
        return {"feature_match": 0.30, "quality": 0.40, "price_value": 0.20, "availability": 0.10}

    # Standard documented default architecture
    return dict(DEFAULT_WEIGHTS)

