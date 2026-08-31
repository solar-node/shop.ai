"""Intent extraction and live product research."""

import re

from app.agents.llm_client import call_structured
from app.mcp.client import merchant_client
from app.commerce.ranking import rank_products, weights_from_priority


INTENT_SYSTEM_PROMPT = """You are the BudBuy Intent Agent.
Convert the user's shopping request into JSON with:
category, budget_max, soft_preferences, required_features, use_case,
priority, auto_purchase_limit, brand_preference.
Use only stated or clearly implied requirements. auto_purchase_limit must be
null unless the user explicitly asks for automatic purchase with a price limit.
Convert budgets to INR."""


def _extract_intent_heuristic(text: str) -> dict:
    t = text.lower()
    
    # 1. Budget extraction
    budget_max = 3000.0
    budget_match = re.search(r'(?:under|below|budget|max|upto|within|<=|<)?\s*(?:₹|rs\.?|inr)?\s*(\d{3,6})', t)
    numbers = [int(n.replace(",", "")) for n in re.findall(r'\b(\d{3,6})\b', t)]
    if budget_match and int(budget_match.group(1)) > 300:
        budget_max = float(budget_match.group(1))
    elif numbers:
        budget_max = float(max(numbers))

    # 2. Auto-purchase limit
    auto_limit = None
    if any(k in t for k in ["auto-buy", "autobuy", "auto-pay", "autopay", "auto buy", "auto pay"]):
        auto_match = re.search(r'(?:auto(?:-| )?(?:buy|pay)(?: under| if under| below| <=)?)\s*(?:₹|rs\.?|inr|\b)\s*(\d{3,6})', t)
        if auto_match:
            auto_limit = float(auto_match.group(1))
        else:
            auto_limit = budget_max

    # 3. Category extraction
    category = "earbuds"
    if any(w in t for w in ["headphone", "headphones", "over-ear", "on-ear"]):
        category = "headphones"
    elif any(w in t for w in ["speaker", "speakers", "soundbar"]):
        category = "speaker"
    elif "iem" in t:
        category = "iem"
    elif any(w in t for w in ["earbuds", "tws", "earphone", "earphones", "buds"]):
        category = "earbuds"

    # 4. Brand detection
    brands = []
    for b in ["sony", "boat", "oneplus", "noise", "realme", "jbl", "apple", "sennheiser", "bose", "boult", "zebronics", "xiaomi", "soundcore", "anker"]:
        if b in t:
            brands.append(b.capitalize() if b != "boat" else "boAt")
    brand_pref = " ".join(brands)

    # 5. Soft preferences
    prefs = []
    if "anc" in t or "noise" in t:
        prefs.append("ANC")
    if "gym" in t or "sport" in t or "workout" in t:
        prefs.append("gym")
    if "bass" in t:
        prefs.append("heavy bass")
    if "battery" in t:
        prefs.append("battery life")

    return {
        "category": category,
        "budget_max": budget_max,
        "soft_preferences": prefs,
        "required_features": [],
        "use_case": "general",
        "priority": "budget and quality match",
        "auto_purchase_limit": auto_limit,
        "brand_preference": brand_pref,
    }


def extract_intent(user_goal: str) -> dict:
    """Turn a natural-language request into structured requirements."""
    data = call_structured(INTENT_SYSTEM_PROMPT, user_goal)
    if not data or not data.get("budget_max"):
        data = _extract_intent_heuristic(user_goal)
    defaults = {
        "category": "earbuds", "budget_max": 3000.0, "soft_preferences": [],
        "required_features": [], "use_case": "general", "priority": "overall quality",
        "auto_purchase_limit": None, "brand_preference": "",
    }
    for key, value in defaults.items():
        data.setdefault(key, value)
    return data



def extract_requirements(user_goal: str) -> dict:
    """Backward-compatible name used by older callers."""
    return extract_intent(user_goal)


FALLBACK_IMAGES = {
    "sony": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500&q=80",
    "boat": "https://images.unsplash.com/photo-1606220588913-b3aacb4d2f46?w=500&q=80",
    "basspro": "https://images.unsplash.com/photo-1572536147248-ac59a8abfa4b?w=500&q=80",
    "soundmax": "https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=500&q=80",
    "headphones": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&q=80",
    "earbuds": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500&q=80",
    "speaker": "https://images.unsplash.com/photo-1545454675-3531b543be5d?w=500&q=80",
    "iem": "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=500&q=80",
    "default": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&q=80",
}


def _resolve_image_url(image_url: str, name: str, category: str) -> str:
    if image_url and image_url.startswith("http"):
        return image_url
    name = (name or "").lower()
    for key, url in FALLBACK_IMAGES.items():
        if key in name:
            return url
    return FALLBACK_IMAGES.get((category or "").lower(), FALLBACK_IMAGES["default"])


def _build_search_query(requirements: dict, user_goal: str = "") -> str:
    if user_goal and len(user_goal.strip()) > 3:
        return re.sub(
            r"^(find|search|compare|show|get|buy|look for|i want|please find)\s+",
            "", user_goal.strip(), flags=re.IGNORECASE,
        )

    parts = [requirements.get("category", "earbuds")]
    brand = requirements.get("brand_preference")
    if brand:
        parts.insert(0, brand)

    prefs = requirements.get("soft_preferences", [])
    if any(p.lower() == "anc" for p in prefs):
        parts.append("ANC")
    if any("wireless" in p.lower() or "bluetooth" in p.lower() for p in prefs):
        parts.append("wireless")
    return " ".join(parts)


def find_and_rank_candidates(requirements: dict, exclude_ids=None, user_goal: str = "") -> list:
    """Search live products first, then the local MCP catalog, and rank them."""
    exclude_ids = exclude_ids or []
    candidates = []

    try:
        from app.integrations.product_scraper import scrape_live_products
        products = scrape_live_products(
            query=_build_search_query(requirements, user_goal),
            max_price=requirements.get("budget_max", 0) or 0,
            max_results=6,
        )
        for product in products:
            if product["product_id"] in exclude_ids:
                continue
            if not product.get("image_url", "").startswith("http"):
                product["image_url"] = _resolve_image_url(
                    "", product.get("name", ""), requirements.get("category", "")
                )
            candidates.append(product)
    except Exception as error:
        print(f"[Research] Live search failed: {error}")

    if not candidates:
        candidates = _search_local_catalog(requirements, exclude_ids)

    ranked = rank_products(
        candidates,
        budget_max=requirements.get("budget_max", 0) or 999999,
        soft_preferences=requirements.get("soft_preferences", []),
        weights=weights_from_priority(requirements.get("priority", "")),
    )

    lookup = {p["product_id"]: p for p in candidates}
    results = []
    for item in ranked:
        original = lookup.get(item.product_id, {})
        data = item.__dict__.copy()
        data.update({
            "image_url": original.get("image_url") or _resolve_image_url(
                "", item.name, requirements.get("category", "")
            ),
            "flipkart_url": original.get("flipkart_url", ""),
            "source": original.get("source", "Live Marketplace"),
            "specs": original.get("specs", {}),
            "rating": original.get("rating", 4.3),
            "review_count": original.get("review_count", 1500),
            "old_price": original.get("old_price"),
            "discount_pct": original.get("discount_pct"),
            "delivery": original.get("delivery", "Free Delivery"),
            "badge": original.get("badge", "Top Match"),
        })
        results.append(data)
    return results


def _search_local_catalog(requirements: dict, exclude_ids: list) -> list:
    brand = requirements.get("brand_preference")
    brand_str = " ".join(brand) if isinstance(brand, list) else str(brand or "")
    category = requirements.get("category", "earbuds")
    category_str = " ".join(category) if isinstance(category, list) else str(category or "earbuds")

    products = merchant_client.call(
        "search_products",
        category=category_str,
        brand=brand_str,
        max_price=requirements.get("budget_max", 0) or 0,
    )
    candidates = []
    if isinstance(products, list):
        for product in products:
            if not isinstance(product, dict) or product.get("product_id") in exclude_ids:
                continue
            stock = merchant_client.call("check_stock", product_id=product["product_id"])
            stock_qty = stock.get("available_qty", 10) if isinstance(stock, dict) else 10
            candidates.append({
                "product_id": product["product_id"],
                "name": product["name"],
                "price": product["price"],
                "image_url": _resolve_image_url(
                    product.get("image_url", ""), product["name"], category_str
                ),
                "rating": product.get("rating", 4.0),
                "review_count": product.get("review_count", 1000),
                "specs": product.get("specs", {}),
                "source": "local",
                "available_qty": stock_qty,
            })
    return candidates
