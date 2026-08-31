"""
Integration and Unit Tests for BudBuy Multi-Agent Shopping Pipeline.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.commerce.ranking import rank_products, weights_from_priority, _bayesian_quality_score
from app.commerce.policies import evaluate_purchase
from app.agents.orchestrator import Orchestrator, COMPILED_GRAPH
from database.models import init_db




def test_langgraph_graph_compilation():
    """Verify that the LangGraph StateGraph builds with checkpointing."""
    assert COMPILED_GRAPH is not None


def test_bayesian_ranking_volume_priority():
    """
    Verify ranking mathematics:
    A battle-tested product with 12,000 reviews at 4.0★ must outrank
    an early product with 400 reviews at 4.3★ due to statistical evidence volume.
    """
    candidates = [
        {"product_id": "p1", "name": "Bestseller Buds 12k Reviews", "price": 2499, "rating": 4.0, "review_count": 12000, "specs": {}},
        {"product_id": "p2", "name": "Early Stage Buds 400 Reviews", "price": 2799, "rating": 4.3, "review_count": 400, "specs": {}},
        {"product_id": "p3", "name": "Mass Popular Buds 25k Reviews", "price": 2199, "rating": 4.5, "review_count": 25000, "specs": {}},
        {"product_id": "p4", "name": "New Unverified Buds 15 Reviews", "price": 2999, "rating": 4.7, "review_count": 15, "specs": {}},
    ]
    
    ranked = rank_products(candidates, budget_max=3000.0, soft_preferences=["wireless"])
    
    # Assert mass bestseller is #1
    assert ranked[0].product_id == "p3"
    # Assert 12k reviews @ 4.0★ beats 400 reviews @ 4.3★
    assert ranked[1].product_id == "p1"
    assert ranked[2].product_id == "p2"
    # Assert 15 reviews is penalized to last place
    assert ranked[3].product_id == "p4"


def test_deterministic_risk_guard_policy():
    """Verify Risk Guard deterministic policy evaluation."""
    # 1. Price exceeding budget must be rejected
    res_overbudget = evaluate_purchase(
        effective_price=3500.0, budget_max=3000.0, auto_purchase_limit=None,
        merchant_trust_score=0.95, stock_confirmed=True
    )
    assert not res_overbudget.approved
    assert "exceeds hard budget" in res_overbudget.reason

    # 2. Out of stock must be rejected
    res_oos = evaluate_purchase(
        effective_price=2500.0, budget_max=3000.0, auto_purchase_limit=None,
        merchant_trust_score=0.95, stock_confirmed=False
    )
    assert not res_oos.approved

    # 3. Untrusted merchant must be rejected
    res_untrusted = evaluate_purchase(
        effective_price=2500.0, budget_max=3000.0, auto_purchase_limit=None,
        merchant_trust_score=0.4, stock_confirmed=True
    )
    assert not res_untrusted.approved

    # 4. Valid product within budget must be approved with user confirmation
    res_valid = evaluate_purchase(
        effective_price=2500.0, budget_max=3000.0, auto_purchase_limit=None,
        merchant_trust_score=0.95, stock_confirmed=True
    )
    assert res_valid.approved
    assert res_valid.requires_user_confirmation


def test_end_to_end_orchestrator_execution():
    """Verify full LangGraph execution for a realistic query."""
    orch = Orchestrator("test_session_001", "Find ANC earbuds under ₹3000 for gym")
    orch.run()
    
    state = orch.state
    assert state.get("status") in ("AWAITING_APPROVAL", "AWAITING_PAYMENT", "COMPLETED")
    assert state.get("current_stage") in ("RISK", "PURCHASE")
    assert len(state.get("candidates", [])) > 0
    assert state.get("selected_product") is not None
    assert len(state["selected_product"].get("why_this_product", [])) >= 2


if __name__ == "__main__":
    print("Running BudBuy test suite...")
    init_db()
    test_langgraph_graph_compilation()
    print("✓ test_langgraph_graph_compilation passed")
    test_bayesian_ranking_volume_priority()
    print("✓ test_bayesian_ranking_volume_priority passed")
    test_deterministic_risk_guard_policy()
    print("✓ test_deterministic_risk_guard_policy passed")
    test_end_to_end_orchestrator_execution()
    print("✓ test_end_to_end_orchestrator_execution passed")
    print("\nAll BudBuy tests passed successfully!")

