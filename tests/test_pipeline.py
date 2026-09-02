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


def test_budget_targeting_prefers_90_to_100_percent_zone():
    from app.commerce.ranking import _price_value_score
    # For budget ₹10,000:
    # A product at ₹9,500 (95% of budget, in the >=90% zone) scores top tier (>= 0.95),
    # significantly beating ₹8,500 (85%) and low-end ₹5,000 (50%)
    top_zone = _price_value_score(9500, 10000)
    mid_zone = _price_value_score(8500, 10000)
    low_zone = _price_value_score(5000, 10000)
    assert top_zone >= 0.95
    assert top_zone > mid_zone > low_zone
    assert low_zone < 0.30



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


def test_category_aware_spec_extraction():
    from app.commerce.spec_extractor import extract_product_specs
    
    # 1. Laptop
    laptop_specs = extract_product_specs("ASUS Vivobook 15 Core i5 13th Gen (16GB RAM / 512GB SSD / Windows 11)", category="laptop")
    assert laptop_specs.get("ram") == "16GB"
    assert "512GB" in laptop_specs.get("storage", "")

    # 2. Headphones
    headphone_specs = extract_product_specs("Sony WH-1000XM4 Wireless Active Noise Cancelling Headphones 30H Battery", category="headphones")
    assert headphone_specs.get("noise_cancellation") == "Active Noise Cancellation (ANC)"
    assert "30" in headphone_specs.get("battery_life", "")

    # 3. Monitor
    monitor_specs = extract_product_specs("LG UltraGear 27 inch QHD 144Hz IPS Gaming Monitor Height Adjustable Stand", category="monitor")
    assert monitor_specs.get("refresh_rate") == "144HZ"
    assert monitor_specs.get("screen_size") == "27 inch"
    assert "Height Adjustable" in monitor_specs.get("stand", "")

    # 4. Smartphone
    phone_specs = extract_product_specs("OnePlus 12R 5G (16GB RAM, 256GB Storage, 50MP OIS Camera, 5500mAh Battery, 100W Fast Charging)", category="smartphone")
    assert phone_specs.get("ram") == "16GB"
    assert "50MP" in phone_specs.get("camera", "")
    assert "100W" in phone_specs.get("fast_charging", "")

    # 5. Running Shoes
    shoe_specs = extract_product_specs("Nike Air Zoom Pegasus 40 Men Road Running Shoes with Responsive Cushioning Wide Fit", category="shoes")
    assert "Air Zoom" in shoe_specs.get("cushioning", "")
    assert shoe_specs.get("usage") == "Road Running"
    assert shoe_specs.get("fit") == "Wide Fit"


def test_grounded_requirement_matching():
    from app.commerce.spec_extractor import match_requirements_against_product

    product = {
        "name": "ASUS Vivobook 15 Core i5 13th Gen (16GB RAM / 512GB SSD / Win 11)",
        "specs": {"ram": "16GB", "storage": "512GB SSD", "processor": "Intel Core i5"},
    }
    reqs = {
        "hard_constraints": ["16GB RAM", "512GB SSD"],
        "soft_preferences": ["good processor", "decent battery life"],
        "priority_order": ["performance", "RAM", "SSD", "battery"],
    }
    matched, missing, score = match_requirements_against_product(product, reqs)
    assert "16GB RAM" in matched
    assert "512GB SSD" in matched
    assert "good processor" in matched
    assert "decent battery life" in missing
    assert score >= 0.70


def test_stock_availability_scoring():
    from app.commerce.ranking import _availability_score

    assert _availability_score(10, "in_stock") == 1.0
    assert _availability_score(None, "in_stock") == 1.0
    assert _availability_score(None, "free delivery") == 1.0
    assert _availability_score(0, "in_stock") == 0.0
    assert _availability_score(None, "out of stock") == 0.0
    assert _availability_score(None, None) == 0.85


def test_priority_weighting_shifts_weights():
    from app.commerce.ranking import weights_from_priority, DEFAULT_WEIGHTS

    perf_weights = weights_from_priority(["performance"], user_goal="Please prioritize performance over display quality")
    assert perf_weights["feature_match"] > DEFAULT_WEIGHTS["feature_match"]

    budget_weights = weights_from_priority(["price"], user_goal="I want the cheapest budget saver option")
    assert budget_weights["price_value"] > DEFAULT_WEIGHTS["price_value"]

    brand_weights = weights_from_priority(["brand"], user_goal="Prefer a reliable brand with top ratings")
    assert brand_weights["quality"] > DEFAULT_WEIGHTS["quality"]


if __name__ == "__main__":
    test_graph_compiles()
    test_review_volume_has_real_influence()
    test_requirement_evidence_can_overrule_volume()
    test_over_budget_is_zero_price_fit()
    test_budget_targeting_prefers_90_to_100_percent_zone()
    test_high_review_volume_significantly_boosts_quality_score()
    test_risk_guard_is_deterministic()
    test_user_goal_dynamic_propagation()
    test_category_aware_spec_extraction()
    test_grounded_requirement_matching()
    test_stock_availability_scoring()
    test_priority_weighting_shifts_weights()
    print("ALL TESTS PASSED SUCCESSFULLY.")





