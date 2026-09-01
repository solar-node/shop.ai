"""
Deterministic purchase gate. The Risk Agent calls this - it never lets the LLM
directly approve a purchase (spec section 31: "Never allow the LLM to ... mark payment
successful / bypass authorization").
"""
from dataclasses import dataclass
from typing import Optional

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(f):
            return f
        return decorator


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    requires_user_confirmation: bool = False


@traceable(run_type="chain", name="Deterministic Purchase Safety Gate")
def evaluate_purchase(
    effective_price: float,
    budget_max: float | None,
    auto_purchase_limit: Optional[float],
    merchant_trust_score: float,
    stock_confirmed: bool,
    min_trust_score: float = 0.6,
    user_goal: str = "",
) -> RiskDecision:

    if budget_max is None:
        return RiskDecision(False, "A verified budget ceiling is required before purchase.")
    if effective_price > budget_max:
        return RiskDecision(False, f"Price ₹{effective_price} exceeds hard budget ₹{budget_max}.")

    if not stock_confirmed:
        return RiskDecision(False, "Stock not confirmed / reservation failed.")

    if merchant_trust_score < min_trust_score:
        return RiskDecision(False, f"Merchant trust score {merchant_trust_score} below minimum {min_trust_score}.")

    # 1. User explicitly enabled Auto-Pay / Auto-Buy mandate with a threshold
    if auto_purchase_limit is not None:
        if effective_price <= auto_purchase_limit:
            return RiskDecision(
                True,
                f"Price ₹{effective_price} is within your autonomous auto-pay limit ₹{auto_purchase_limit}. Auto-checkout authorized.",
                requires_user_confirmation=False,
            )
        else:
            return RiskDecision(
                True,
                f"Price ₹{effective_price} is within overall budget ₹{budget_max} but exceeds your auto-pay limit ₹{auto_purchase_limit}.",
                requires_user_confirmation=True,
            )

    # 2. Normal Function (User did not specify Auto-Pay): Always require user confirmation
    return RiskDecision(
        True,
        f"Product verified at ₹{effective_price}. Confirmation required before proceeding to checkout.",
        requires_user_confirmation=True,
    )

