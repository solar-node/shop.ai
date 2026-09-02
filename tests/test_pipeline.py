import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import math
from app.commerce.ranking import rank_products, _bayesian_quality_score, _price_value_score, _availability_score, weights_from_priority, DEFAULT_WEIGHTS
from app.commerce.spec_extractor import match_requirements_against_product, evaluate_requirement_3state
from app.commerce.policies import evaluate_purchase
from app.agents.orchestrator import COMPILED_GRAPH


def test_graph_compiles():
    assert COMPILED_GRAPH is not None


def test_bayesian_score_bounds_and_shrinkage():
    """Validates Bayesian shrinkage, volume confidence bounding, and [0,1] normalization across all edge cases."""
    edge_cases = [
        (None, None),
        (0, 0),
        (5.0, 0),
        (5.0, 1),
        (4.5, 10),
        (4.2, 50),
        (4.8, 500),
        (4.6, 2500),
        (4.5, 5000),
        (4.7, 15000),
        (1.0, 5000),
        (-2.0, -10),
        ("invalid", "invalid"),
    ]
    for r, v in edge_cases:
        score = _bayesian_quality_score(r, v)
        assert 0.0 <= score <= 1.0, f"Bayesian score out of bounds: {score} for rating={r}, reviews={v}"

    # 15,000 reviews at 4.3★ must have higher statistical confidence than 10 reviews at 4.7★
    high_vol = _bayesian_quality_score(4.3, 15000)
    low_vol = _bayesian_quality_score(4.7, 10)
    assert high_vol > low_vol

    # Zero reviews rating shrinks to prior baseline
    zero_revs = _bayesian_quality_score(5.0, 0)
    assert zero_revs <= 0.40


def test_generic_priority_weighting_without_hardcoded_phrases():
    """Validates that structured priority_order dynamically shifts ranking dimensions and weights sum to 1.0."""
    # Feature heavy priority
    feat_weights = weights_from_priority(["camera quality", "battery life", "fast charging", "gaming performance"])
    assert feat_weights["feature_match"] > DEFAULT_WEIGHTS["feature_match"]
    assert math.isclose(sum(feat_weights.values()), 1.0, abs_tol=1e-4)

    # Budget / Price heavy priority
    budget_weights = weights_from_priority(["price", "budget savings", "affordability"])
    assert budget_weights["price_value"] > DEFAULT_WEIGHTS["price_value"]
    assert math.isclose(sum(budget_weights.values()), 1.0, abs_tol=1e-4)

    # Quality / Brand heavy priority
    brand_weights = weights_from_priority(["top rating", "trusted brand", "reliable build quality"])
    assert brand_weights["quality"] > DEFAULT_WEIGHTS["quality"]
    assert math.isclose(sum(brand_weights.values()), 1.0, abs_tol=1e-4)

    # Unseen custom priorities
    custom_weights = weights_from_priority(["consistent grind size", "easy cleaning", "price"])
    assert custom_weights["feature_match"] > DEFAULT_WEIGHTS["feature_match"]
    assert math.isclose(sum(custom_weights.values()), 1.0, abs_tol=1e-4)

    # Default fallback when no priority is given
    default_w = weights_from_priority([])
    assert default_w == DEFAULT_WEIGHTS
    assert math.isclose(sum(default_w.values()), 1.0, abs_tol=1e-4)


def test_3state_requirement_evaluation():
    """Validates that requirement evaluation strictly returns TRUE, FALSE, or UNKNOWN without fabricating facts."""
    evid = "Timemore C3 Manual Coffee Grinder with Stainless Steel Conical Burr for Consistent Grind Size, Easy to Clean"
    
    # Verified match -> TRUE
    assert evaluate_requirement_3state("consistent grind size", evid, {}, 6999, 12000) == "TRUE"
    assert evaluate_requirement_3state("easy cleaning", evid, {}, 6999, 12000) == "TRUE"
    
    # Missing from listing -> UNKNOWN (NOT False, NOT True)
    assert evaluate_requirement_3state("rain resistance", evid, {}, 6999, 12000) == "UNKNOWN"
    assert evaluate_requirement_3state("stylus support", evid, {}, 6999, 12000) == "UNKNOWN"
    
    # Hard constraint violated -> FALSE
    assert evaluate_requirement_3state("price <= 5000", evid, {}, 6999, 5000) == "FALSE"
    assert evaluate_requirement_3state("16GB RAM", "Laptop 8GB RAM 512GB SSD", {}, 50000, 60000) == "FALSE"


def test_hard_constraints_and_ranking_integrity():
    """Validates that a product violating a hard constraint cannot outrank a compliant product."""
    products = [
        {
            "product_id": "compliant",
            "name": "Compliant Laptop 16GB RAM",
            "price": 65000,
            "rating": 4.2,
            "review_count": 500,
            "available_qty": 5,
            "specs": {"ram": "16GB", "storage": "512GB SSD"},
        },
        {
            "product_id": "violator",
            "name": "Non-compliant Laptop 8GB RAM",
            "price": 45000,
            "rating": 4.9,
            "review_count": 15000,
            "available_qty": 5,
            "specs": {"ram": "8GB", "storage": "256GB SSD"},
        },
    ]
    reqs = {
        "budget_max": 70000,
        "hard_constraints": ["price <= 70000", "16GB RAM"],
        "soft_preferences": ["512GB SSD"],
        "priority_order": ["16GB RAM", "512GB SSD", "price"],
    }
    ranked = rank_products(products, 70000, requirements=reqs)
    
    assert ranked[0].product_id == "compliant"
    assert ranked[0].utility_score > ranked[1].utility_score
    assert "16GB RAM" in ranked[1].missing_requirements



def test_unseen_arbitrary_categories():
    """Validates that the ranking and matching system functions purely category-agnostically on arbitrary queries."""
    # 1. Coffee Grinder (Unseen)
    grinder_cand = {
        "product_id": "g1",
        "name": "Timemore C3 Manual Coffee Grinder Conical Burr Consistent Grind Size, Easy to Clean",
        "price": 6999,
        "rating": 4.7,
        "review_count": 1200,
        "available_qty": 10,
    }
    g_reqs = {
        "budget_max": 12000,
        "hard_constraints": ["price <= 12000"],
        "soft_preferences": ["consistent grind size", "easy cleaning"],
        "priority_order": ["consistent grind size", "easy cleaning", "price"],
    }
    g_ranked = rank_products([grinder_cand], 12000, requirements=g_reqs)
    assert g_ranked[0].components["feature_match"] == 1.0
    assert "consistent grind size" in g_ranked[0].matched_requirements
    assert "easy cleaning" in g_ranked[0].matched_requirements
    assert g_ranked[0].utility_score >= 0.75


    # 2. Backpack (Unseen)
    pack_cand = {
        "product_id": "b1",
        "name": "Mokobara The Transit Backpack Padded Laptop Compartment Water Resistant Rain Cover",
        "price": 4999,
        "rating": 4.6,
        "review_count": 850,
        "available_qty": 5,
    }
    b_reqs = {
        "budget_max": 6000,
        "hard_constraints": ["price <= 6000"],
        "soft_preferences": ["laptop protection", "rain resistance"],
        "priority_order": ["laptop protection", "rain resistance", "price"],
    }
    b_ranked = rank_products([pack_cand], 6000, requirements=b_reqs)
    assert b_ranked[0].components["feature_match"] == 1.0
    assert "laptop protection" in b_ranked[0].matched_requirements
    assert "rain resistance" in b_ranked[0].matched_requirements


def test_utility_score_composition_and_transparency():
    """Validates that utility_score is an exact weighted sum of the 4 transparent components."""
    candidate = {
        "product_id": "p1",
        "name": "Product 1",
        "price": 9500,
        "rating": 4.5,
        "review_count": 3000,
        "available_qty": 5,
        "specs": {"ram": "16GB"},
        "matched_requirements": ["16GB RAM"],
    }
    reqs = {"budget_max": 10000, "hard_constraints": ["16GB RAM"], "soft_preferences": []}
    ranked = rank_products([candidate], 10000, requirements=reqs)
    p = ranked[0]

    # Transparency fields check
    assert hasattr(p, "bayesian_quality")
    assert hasattr(p, "utility_score")
    assert hasattr(p, "components")
    assert hasattr(p, "matched_requirements")
    assert hasattr(p, "unknown_requirements")

    weights = DEFAULT_WEIGHTS
    expected_utility = round(
        p.components["feature_match"] * weights["feature_match"]
        + p.components["quality"] * weights["quality"]
        + p.components["price_value"] * weights["price_value"]
        + p.components["availability"] * weights["availability"],
        4
    )
    assert math.isclose(p.utility_score, expected_utility, abs_tol=1e-4)


def test_risk_guard_is_deterministic():
    rejected = evaluate_purchase(7000, 5000, None, 0.95, True)
    assert not rejected.approved

    approved = evaluate_purchase(4500, 5000, 4000, 0.95, True)
    assert approved.approved and approved.requires_user_confirmation

    auto = evaluate_purchase(3500, 5000, 4000, 0.95, True)
    assert auto.approved and not auto.requires_user_confirmation


if __name__ == "__main__":
    test_graph_compiles()
    test_bayesian_score_bounds_and_shrinkage()
    test_generic_priority_weighting_without_hardcoded_phrases()
    test_3state_requirement_evaluation()
    test_hard_constraints_and_ranking_integrity()
    test_unseen_arbitrary_categories()
    test_utility_score_composition_and_transparency()
    test_risk_guard_is_deterministic()
    print("ALL TESTS PASSED SUCCESSFULLY.")
