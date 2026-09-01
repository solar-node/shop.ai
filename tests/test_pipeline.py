import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import math
from app.commerce.ranking import rank_products, _bayesian_quality_score
from app.commerce.policies import evaluate_purchase
from app.agents.orchestrator import COMPILED_GRAPH



def test_graph_compiles():
    assert COMPILED_GRAPH is not None


def test_review_volume_has_real_influence():
    high_volume = _bayesian_quality_score(4.0, 12000)
    lower_volume = _bayesian_quality_score(4.3, 400)
    assert high_volume > lower_volume


def test_requirement_evidence_can_overrule_volume():
    products = [
        {
            "product_id": "matched", "name": "Product A", "price": 5000,
            "rating": 4.5, "review_count": 4000, "available_qty": 5,
            "matched_requirements": ["required feature"], "missing_requirements": [],
        },
        {
            "product_id": "popular", "name": "Product B", "price": 5000,
            "rating": 4.8, "review_count": 20000, "available_qty": 5,
            "matched_requirements": [], "missing_requirements": ["required feature"],
        },
    ]
    reqs = {"hard_constraints": ["required feature"], "soft_preferences": []}
    ranked = rank_products(products, 6000, requirements=reqs)
    assert ranked[0].product_id == "matched"


def test_over_budget_is_zero_price_fit():
    products = [{
        "product_id": "x", "name": "X", "price": 7000,
        "rating": 4.5, "review_count": 5000, "available_qty": 1,
        "matched_requirements": [], "missing_requirements": [],
    }]
    ranked = rank_products(products, 5000, requirements={})
    assert ranked[0].components["price_value"] == 0.0


def test_risk_guard_is_deterministic():
    rejected = evaluate_purchase(7000, 5000, None, 0.95, True)
    assert not rejected.approved

    approved = evaluate_purchase(4500, 5000, 4000, 0.95, True)
    assert approved.approved and approved.requires_user_confirmation

    auto = evaluate_purchase(3500, 5000, 4000, 0.95, True)
    assert auto.approved and not auto.requires_user_confirmation


def test_budget_targeting_prefers_85_to_100_percent_zone():
    from app.commerce.ranking import _price_value_score
    # For budget ₹4,000:
    # A product at ₹3,600 (90% of budget, in the >=85% zone) scores higher than ₹2,800 (70%) and ₹600 (15%)
    top_zone = _price_value_score(3600, 4000)
    mid_zone = _price_value_score(2800, 4000)
    cheap_item = _price_value_score(600, 4000)
    assert top_zone >= 0.95
    assert top_zone > mid_zone > cheap_item


def test_high_review_volume_significantly_boosts_quality_score():
    from app.commerce.ranking import _bayesian_quality_score
    # A 4.3 rating with 15,000 verified reviews should achieve higher quality confidence
    # than a 4.6 rating with only 10 reviews due to Bayesian evidence shrinkage
    high_volume_score = _bayesian_quality_score(4.3, 15000)
    low_volume_score = _bayesian_quality_score(4.6, 10)
    assert high_volume_score > low_volume_score


def test_user_goal_dynamic_propagation():
    sample_query = "Find me high performance wireless earbuds under 3000"
    decision = evaluate_purchase(
        effective_price=2500,
        budget_max=3000,
        auto_purchase_limit=None,
        merchant_trust_score=0.95,
        stock_confirmed=True,
        user_goal=sample_query,
    )
    assert decision.approved
    
    from app.agents.risk_agent import check_purchase
    prod = {"product_id": "test_p1", "effective_price": 2500, "source": "Amazon"}
    reqs = {"budget_max": 3000}
    res = check_purchase(prod, reqs, user_goal=sample_query)
    assert res.get("approved")


if __name__ == "__main__":
    test_graph_compiles()
    test_review_volume_has_real_influence()
    test_requirement_evidence_can_overrule_volume()
    test_over_budget_is_zero_price_fit()
    test_budget_targeting_prefers_85_to_100_percent_zone()
    test_high_review_volume_significantly_boosts_quality_score()
    test_risk_guard_is_deterministic()
    test_user_goal_dynamic_propagation()
    print("ALL TESTS PASSED SUCCESSFULLY.")




