"""
Deterministic ranking engine. The LLM (Research Agent) extracts preferences/weights;
this module computes the actual utility score. Never let the LLM just "decide" a winner
(spec section 5).
"""
import math
from dataclasses import dataclass
from typing import Dict, List

DEFAULT_WEIGHTS = {
    "quality": 0.45,           # Volume-weighted Bayesian rating confidence (primary driver)
    "feature_match": 0.25,     # Spec & user requirement match (ANC, gym, battery, brand)
    "price_value": 0.20,       # Budget fit & pricing value
    "availability": 0.10,      # In-stock inventory verification
}

PRIOR_CATEGORY_RATING = 3.8     # Bayesian prior mean rating
PRIOR_REVIEW_WEIGHT = 150.0     # Evidence weight threshold for Bayesian shrinkage (m)


@dataclass
class RankedProduct:
    product_id: str
    name: str
    price: float
    utility_score: float
    components: Dict[str, float]
    image_url: str = ""
    flipkart_url: str = ""
    source: str = "local"


def _price_value_score(price: float, budget_max: float) -> float:
    """
    Evaluates price within budget ceiling.
    Products under budget ceiling receive high utility.
    """
    if budget_max <= 0:
        return 0.85
    if price > budget_max * 1.05:
        return 0.0

    ratio = min(price / budget_max, 1.0)
    if 0.40 <= ratio <= 1.0:
        return round(0.85 + (1.0 - ratio) * 0.15, 3)
    return 0.85


def _feature_match_score(specs: dict, soft_preferences: List[str], product_name: str = "", brand_preference: str = "") -> float:
    # Extract only truthy spec tokens
    valid_specs = [f"{k}:{v}" for k, v in specs.items() if v and str(v).lower() not in ("false", "0", "none", "null")]
    text = (" ".join(valid_specs) + " " + product_name).lower()
    
    brand_bonus = 0.0
    if brand_preference:
        if brand_preference.lower() in text:
            brand_bonus = 0.12
        else:
            brand_bonus = -0.08

    if soft_preferences:
        hits = 0
        for pref in soft_preferences:
            p = str(pref).lower().strip()
            if not p or p in ("none", "null"):
                continue
            if p in text:
                hits += 1
            elif p in ("anc", "noise cancellation", "noise cancelling") and ("anc" in text or "noise" in text):
                hits += 1
            elif p in ("gym", "sport", "workout", "sweat", "waterproof") and ("gym" in text or "sport" in text or "ipx" in text or "ip5" in text or "water" in text or "sweat" in text):
                hits += 1
            elif p in ("battery", "battery life", "playback") and ("battery" in text or "playtime" in text or "playback" in text or "hours" in text or "hrs" in text):
                hits += 1
            elif p in ("bass", "deep bass", "heavy bass") and ("bass" in text or "driver" in text):
                hits += 1

        match_ratio = hits / max(len(soft_preferences), 1)
        feature_score = 0.35 + (match_ratio * 0.60) + brand_bonus
        return round(min(max(feature_score, 0.20), 1.0), 3)

    return round(min(max(0.85 + brand_bonus, 0.20), 1.0), 3)



def _bayesian_quality_score(rating: float, review_count: int) -> float:
    """
    Computes statistical Bayesian rating adjusted by review evidence volume with high-volume scaling.
    Formula:
      R_adj = (v * R + m * C) / (v + m)
    where:
      v = review_count
      m = PRIOR_REVIEW_WEIGHT (150)
      C = PRIOR_CATEGORY_RATING (3.8)
    
    Volume Confidence Factor:
      V_conf = min(1.20, ln(1 + v) / ln(1 + 10000))
      Score = (R_adj / 5.0) * (0.55 + 0.45 * V_conf)

    This ensures a battle-tested product with 12,000 reviews at 4.0 stars
    confidently outranks an early product with 400 reviews at 4.3 stars.
    """
    v = max(0, review_count)
    r = min(max(rating, 1.0), 5.0)
    m = PRIOR_REVIEW_WEIGHT
    c = PRIOR_CATEGORY_RATING

    # Bayesian shrinkage toward prior mean
    r_adj = (v * r + m * c) / (v + m)

    # Logarithmic evidence volume factor (scaled to 10,000 verified reviews)
    volume_conf = min(1.20, math.log(1 + v) / math.log(1 + 10000))

    # Composite quality score with 45% dynamic volume scaling
    quality_score = (r_adj / 5.0) * (0.55 + 0.45 * volume_conf)
    return round(min(max(quality_score, 0.20), 1.0), 4)



def _availability_score(available_qty: int) -> float:
    if available_qty <= 0:
        return 0.0
    return round(min(available_qty / 10, 1.0), 3)


def rank_products(candidates: list, budget_max: float, soft_preferences: List[str] = None,
                   weights: Dict[str, float] = None, brand_preference: str = "") -> List[RankedProduct]:
    """
    candidates: list of dicts with keys: product_id, name, price, specs, rating, review_count, available_qty
    """
    weights = weights or DEFAULT_WEIGHTS
    soft_preferences = soft_preferences or []
    ranked = []
    
    for c in candidates:
        rating = float(c.get("rating", 4.2))
        reviews = int(c.get("review_count", 150))
        price = float(c.get("price", 0))

        quality_score = _bayesian_quality_score(rating, reviews)
        feature_score = _feature_match_score(c.get("specs", {}), soft_preferences, c.get("name", ""), brand_preference)
        price_score = _price_value_score(price, budget_max)
        avail_score = _availability_score(c.get("available_qty", 10))

        components = {
            "feature_match": feature_score,
            "quality": quality_score,
            "price_value": price_score,
            "availability": avail_score,
        }
        
        score = sum(components[k] * weights.get(k, 0) for k in components)
        ranked.append(RankedProduct(
            product_id=c["product_id"], name=c["name"], price=price,
            utility_score=round(score, 4), components=components
        ))

    ranked.sort(key=lambda r: r.utility_score, reverse=True)
    return ranked


def weights_from_priority(priority: str) -> Dict[str, float]:
    """User says e.g. 'I care mostly about battery life / price' -> shift weights."""
    w = dict(DEFAULT_WEIGHTS)
    priority = (priority or "").lower()
    if "price" in priority or "budget" in priority or "cheap" in priority:
        w["price_value"] = 0.30
        w["quality"] = 0.40
        w["feature_match"] = 0.20
    elif "battery" in priority or "feature" in priority or "anc" in priority:
        w["feature_match"] = 0.35
        w["quality"] = 0.40
        w["price_value"] = 0.15
    elif "quality" in priority or "rating" in priority or "review" in priority:
        w["quality"] = 0.55
        w["feature_match"] = 0.20
        w["price_value"] = 0.15
    return w


