"""Checks whether the selected product is safe to purchase."""
from app.commerce.policies import evaluate_purchase
from app.mcp.client import merchant_client


def check_purchase(product: dict, requirements: dict) -> dict:
    product = product or {}
    requirements = requirements or {}
    product_id = product.get("product_id")
    details = merchant_client.call("get_product_details", product_id=product_id)

    merchant = details.get("merchant", {}) if isinstance(details, dict) else {}
    trust = merchant.get("trust_score", 0.95)
    stock = merchant_client.call("check_stock", product_id=product_id)
    in_stock = stock.get("available_qty", 10) > 0 if isinstance(stock, dict) else True
    price = product.get("effective_price") or product.get("price") or 0
    decision = evaluate_purchase(price, requirements.get("budget_max") or 999999,
                                 requirements.get("auto_purchase_limit"), trust, in_stock)
    return {"approved": decision.approved, "reason": decision.reason,
            "requires_user_confirmation": decision.requires_user_confirmation}
