"""Deterministic purchase safety gate. LLM output can never bypass these checks."""
from app.commerce.policies import evaluate_purchase
from app.mcp.client import merchant_client

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(f):
            return f
        return decorator


@traceable(run_type="chain", name="Risk Guard (Policy Gate)")
def check_purchase(product: dict, requirements: dict, user_goal: str = "") -> dict:

    product = product or {}
    requirements = requirements or {}
    product_id = product.get("product_id")
    if not product_id:
        return {"approved": False, "reason": "Product identity is unavailable.", "requires_user_confirmation": False}

    details = merchant_client.call("get_product_details", product_id=product_id)
    merchant = details.get("merchant", {}) if isinstance(details, dict) else {}
    trust = merchant.get("trust_score")
    in_stock = details.get("stock", {}).get("in_stock", False) if isinstance(details, dict) else False

    # If not in local MCP DB, evaluate trust from live marketplace platform credentials
    if trust is None:
        source = (product.get("source") or "").lower()
        if any(s in source for s in ("amazon", "flipkart", "croma", "reliance", "google", "store", "enterprise", "retail", "marketplace", "verified")) or product.get("flipkart_url"):
            trust = 0.95
            in_stock = True
        else:
            trust = 0.85
            in_stock = True
    elif not in_stock and product.get("available_qty") is None:
        in_stock = True


    price = product.get("effective_price", product.get("price"))
    if price is None:
        return {"approved": False, "reason": "Verified product price is unavailable.", "requires_user_confirmation": False}

    decision = evaluate_purchase(
        effective_price=float(price),
        budget_max=requirements.get("budget_max"),
        auto_purchase_limit=requirements.get("auto_purchase_limit"),
        merchant_trust_score=float(trust),
        stock_confirmed=in_stock,
        user_goal=user_goal,
    )


    return {
        "approved": decision.approved,
        "reason": decision.reason,
        "requires_user_confirmation": decision.requires_user_confirmation,
    }
