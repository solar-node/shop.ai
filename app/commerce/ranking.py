"""Category-agnostic deterministic Product Analyst & Ranking Pipeline.
Performs reproducible, mathematically sound evaluation on supplied evidence without
hardcoding product names, categories, or expected results.
"""
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

DEFAULT_WEIGHTS: Dict[str, float] = {
    "feature_match": 0.35,
    "quality": 0.30,
    "price_value": 0.25,
    "availability": 0.10,
}

PRIOR_RATING = 3.8
PRIOR_REVIEW_WEIGHT = 100.0
VOLUME_REFERENCE = 5000.0

PRICE_KEYWORDS = {
    "price", "budget", "cost", "affordability", "cheap", "value",
    "savings", "inexpensive", "affordable", "economical", "pricing"
}
QUALITY_KEYWORDS = {
    "rating", "ratings", "review", "reviews", "brand", "reputation",
    "trust", "reliable", "durability", "build quality", "tested", "certified"
}
AVAIL_KEYWORDS = {
    "stock", "availability", "delivery", "shipping", "fast delivery",
    "same day", "prime", "in stock", "immediate"
}


@dataclass
class RankedProduct:
    product_id: str
    name: str
    price: float
    utility_score: float
    bayesian_quality: float
    components: Dict[str, float]
    matched_requirements: List[str] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)
    unknown_requirements: List[str] = field(default_factory=list)
    image_url: str = ""
    flipkart_url: str = ""
    source: str = ""


def _bayesian_quality_score(rating: Any, review_count: Any) -> float:
    """Computes Bayesian mean prior shrinkage with review-volume statistical confidence.
    Formula: R_adj = (v * R + m * C) / (v + m)
    Volume confidence bounded strictly in [0.0, 1.0].
    """
    try:
        r_raw = float(rating or 0)
    except (TypeError, ValueError):
        r_raw = 0.0

    try:
        v_raw = int(review_count or 0)
    except (TypeError, ValueError):
        v_raw = 0

    v = max(v_raw, 0)
    
    if r_raw <= 0:
        r = PRIOR_RATING
    else:
        r = min(max(r_raw, 1.0), 5.0)

    adjusted = (v * r + PRIOR_REVIEW_WEIGHT * PRIOR_RATING) / (v + PRIOR_REVIEW_WEIGHT)
    
    # Strictly bounded in [0.0, 1.0]
    volume_confidence = min(1.0, math.log1p(v) / math.log1p(VOLUME_REFERENCE))
    
    score = (adjusted / 5.0) * (0.40 + 0.60 * volume_confidence)
    return round(min(max(score, 0.0), 1.0), 4)


def _price_value_score(price: float, budget_max: float) -> float:
    """Evaluates budget utilization and price feasibility.
    - Above budget ceiling: strictly 0.0
    - Within budget: monotonic utilization score in [0.0, 1.0]
    """
    if price <= 0:
        return 0.0
    if budget_max <= 0:
        return 0.90
    if price > budget_max:
        return 0.0

    ratio = price / budget_max
    if 0.90 <= ratio <= 1.00:
        return round(0.95 + 0.05 * ((ratio - 0.90) / 0.10), 4)
    elif 0.80 <= ratio < 0.90:
        return round(0.70 + 0.25 * ((ratio - 0.80) / 0.10), 4)
    elif 0.60 <= ratio < 0.80:
        return round(0.30 + 0.40 * ((ratio - 0.60) / 0.20), 4)
    else:
        return round(0.05 + 0.25 * (ratio / 0.60), 4)



def _feature_match_score(candidate: dict, requirements: dict, user_goal: str = "") -> float:
    """Score evidence-backed requirement match using 3-state evaluation."""
    if "feature_match_score" in candidate and isinstance(candidate["feature_match_score"], (int, float)):
        return float(candidate["feature_match_score"])

    from app.commerce.spec_extractor import match_requirements_against_product
    _, _, _, score = match_requirements_against_product(candidate, requirements, user_goal)
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
        if any(w in s for w in ("out of stock", "unavailable", "sold out", "oos", "out-of-stock")):
            return 0.0
        if any(w in s for w in ("in stock", "in_stock", "available", "free delivery", "delivery")):
            return 1.0

    return 0.85


def _classify_priority_dimension(priority_text: str) -> str:
    """Classifies a user priority item into one of the 4 ranking dimensions generically."""
    p_low = priority_text.lower().strip()
    
    if any(w in p_low for w in PRICE_KEYWORDS):
        return "price_value"
    if any(w in p_low for w in QUALITY_KEYWORDS) and not any(w in p_low for w in ("camera", "display", "screen", "audio", "sound", "picture", "video")):
        return "quality"
    if any(w in p_low for w in AVAIL_KEYWORDS):
        return "availability"
    
    # All functional specifications and product features map to feature_match
    return "feature_match"


def weights_from_priority(
    priority: Any = None,
    requirements: Optional[dict] = None,
    user_goal: str = ""
) -> Dict[str, float]:
    """Dynamically adjusts ranking weights from structured user priorities generically."""
    priority_order = []
    if isinstance(priority, list):
        priority_order = [str(x) for x in priority if str(x).strip()]
    elif requirements and isinstance(requirements.get("priority_order"), list):
        priority_order = [str(x) for x in requirements["priority_order"] if str(x).strip()]

    if not priority_order:
        return dict(DEFAULT_WEIGHTS)

    p_scores: Dict[str, float] = {
        "feature_match": 0.0,
        "quality": 0.0,
        "price_value": 0.0,
        "availability": 0.0,
    }

    for idx, p in enumerate(priority_order):
        weight = max(1.0, 3.0 - (0.4 * idx))
        dim = _classify_priority_dimension(p)
        p_scores[dim] += weight

    total_p = sum(p_scores.values())
    if total_p <= 0:
        return dict(DEFAULT_WEIGHTS)

    p_dist = {d: p_scores[d] / total_p for d in p_scores}

    # Blend 40% default prior + 60% empirical user priority distribution
    blended = {d: 0.40 * DEFAULT_WEIGHTS[d] + 0.60 * p_dist[d] for d in DEFAULT_WEIGHTS}
    total_b = sum(blended.values())
    normalized = {d: round(blended[d] / total_b, 4) for d in blended}

    # Ensure exact sum to 1.0000
    diff = round(1.0 - sum(normalized.values()), 4)
    normalized["feature_match"] = round(normalized["feature_match"] + diff, 4)
    return normalized


@traceable(run_type="chain", name="Deterministic Product Analyst Ranker")
def rank_products(
    candidates: list,
    budget_max: float,
    soft_preferences: List[str] = None,
    weights: Dict[str, float] = None,
    brand_preference: str = "",
    requirements: dict = None,
    user_goal: str = ""
) -> List[RankedProduct]:
    """Deterministically ranks products using 4-component utility math."""
    requirements = requirements or {
        "soft_preferences": soft_preferences or [],
        "hard_constraints": [],
        "brand_preference": brand_preference
    }
    weights = weights or weights_from_priority(requirements.get("priority_order"), requirements, user_goal)
    
    from app.commerce.spec_extractor import match_requirements_against_product
    
    ranked = []
    for c in candidates:
        price = float(c.get("price") or c.get("effective_price") or 0)
        rating = c.get("rating")
        reviews = c.get("review_count")
        
        matched, contradicted, unknown, feat_score = match_requirements_against_product(c, requirements, user_goal)
        bayesian_q = _bayesian_quality_score(rating, reviews)
        price_val = _price_value_score(price, float(budget_max or 0))
        avail = _availability_score(c.get("available_qty"), c.get("availability"))
        
        components = {
            "feature_match": feat_score,
            "quality": bayesian_q,
            "price_value": price_val,
            "availability": avail,
        }
        
        utility = sum(components[k] * float(weights.get(k, 0)) for k in components)
        
        ranked.append(RankedProduct(
            product_id=str(c.get("product_id")),
            name=str(c.get("name", "Product")),
            price=price,
            utility_score=round(min(max(utility, 0.0), 1.0), 4),
            bayesian_quality=bayesian_q,
            components=components,
            matched_requirements=matched,
            missing_requirements=contradicted,
            unknown_requirements=unknown,
            image_url=c.get("image_url", ""),
            flipkart_url=c.get("flipkart_url", ""),
            source=c.get("source", "")
        ))

    # Rank deterministically by utility score desc, feature match desc, quality desc, price asc
    return sorted(
        ranked,
        key=lambda x: (-x.utility_score, -x.components["feature_match"], -x.bayesian_quality, x.price)
    )
