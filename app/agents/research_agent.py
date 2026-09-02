"""Intent planning and marketplace discovery for Shop.ai."""
import re
from app.agents.llm_client import call_structured
from app.mcp.client import merchant_client


INTENT_SYSTEM_PROMPT = """You are Shop.ai's Shopping Planner.

Turn a user's natural-language shopping goal into a compact, category-agnostic plan.
Do not use a fixed category list. Infer the product category from the request.
Do not invent requirements that are not stated or strongly implied by the use case.
Separate non-negotiable constraints from preferences.

Return ONLY JSON:
{
  "category": "...",
  "budget_max": number|null,
  "use_case": "...",
  "hard_constraints": ["..."],
  "soft_preferences": ["..."],
  "priority_order": ["..."],
  "brand_preference": "...",
  "auto_purchase_limit": number|null,
  "purchase_intent": "recommend"|"auto_buy"
}

Examples:
User: Find ANC earbuds under 3000 for gym
Output: {"category":"earbuds","budget_max":3000,"use_case":"gym","hard_constraints":["price <= 3000","ANC"],"soft_preferences":["secure fit","sweat resistance","bass"],"priority_order":["ANC","secure fit","bass","price"],"brand_preference":"","auto_purchase_limit":null,"purchase_intent":"recommend"}

User: I need a laptop under 70000 for Python and ML
Output: {"category":"laptop","budget_max":70000,"use_case":"Python development and machine learning","hard_constraints":["price <= 70000"],"soft_preferences":["strong CPU","16GB RAM","GPU","SSD"],"priority_order":["compute performance","GPU","RAM","price"],"brand_preference":"","auto_purchase_limit":null,"purchase_intent":"recommend"}

User: Buy a camera automatically if it is below 50000 and good for travel
Output: {"category":"camera","budget_max":null,"use_case":"travel photography","hard_constraints":[],"soft_preferences":["travel-friendly","good image quality"],"priority_order":["image quality","portability","price"],"brand_preference":"","auto_purchase_limit":50000,"purchase_intent":"auto_buy"}

Reason from the actual request; do not copy example values into unrelated queries."""


def extract_intent(user_goal: str) -> dict:
    """Extracts structured shopping requirements using Primary (Gemini) with automatic
    Groq LLM fallback. Never relies on hardcoded regex heuristics.
    """
    data = call_structured(INTENT_SYSTEM_PROMPT, user_goal)
    if data and isinstance(data, dict) and data.get("category"):
        return data

    # Explicit failure representation when both Primary and Fallback providers fail
    return {
        "category": "product",
        "budget_max": None,
        "use_case": "",
        "hard_constraints": [],
        "soft_preferences": [],
        "priority_order": [],
        "brand_preference": "",
        "auto_purchase_limit": None,
        "purchase_intent": "recommend",
    }



def extract_requirements(user_goal: str) -> dict:
    return extract_intent(user_goal)


def build_search_query(requirements: dict, user_goal: str = "") -> str:
    category = str(requirements.get("category") or "product").strip()
    budget = requirements.get("budget_max")
    brand = requirements.get("brand_preference") or ""
    
    # Key specs from hard constraints
    specs = [str(x) for x in requirements.get("hard_constraints", []) if not str(x).lower().startswith("price")][:2]
    # Key prefs
    prefs = [str(x) for x in requirements.get("soft_preferences", [])[:2] if len(str(x)) < 25 and not any(w in str(x).lower() for w in ("under", "price", "budget"))]

    query_parts = []
    if brand:
        query_parts.append(brand)
    query_parts.append(category)
    if specs:
        query_parts.append(" ".join(specs))
    elif prefs:
        query_parts.append(" ".join(prefs[:1]))
    if budget:
        query_parts.append(f"under {int(budget)}")

    return " ".join(query_parts).strip()




def find_candidates(requirements: dict, user_goal: str = "", exclude_ids=None) -> list:
    """Retrieve raw marketplace evidence. Ranking deliberately happens later."""
    exclude_ids = set(exclude_ids or [])
    query = build_search_query(requirements, user_goal)
    candidates = []
    try:
        from app.integrations.product_scraper import scrape_live_products
        candidates = scrape_live_products(
            query=query,
            max_price=float(requirements.get("budget_max") or 0),
            max_results=10,
        ) or []
    except Exception as exc:
        print(f"[Research] Live marketplace search failed: {exc}")

    if not candidates:
        candidates = _search_local_catalog(requirements)

    return [p for p in candidates if p.get("product_id") not in exclude_ids]


def find_and_rank_candidates(requirements: dict, exclude_ids=None, user_goal: str = "") -> list:
    """Backward-compatible name; discovery is no longer responsible for ranking."""
    return find_candidates(requirements, user_goal, exclude_ids)


def _search_local_catalog(requirements: dict) -> list:
    """Use the merchant catalog without manufacturing category-specific products."""
    products = merchant_client.call(
        "search_products",
        category=str(requirements.get("category", "")),
        brand=str(requirements.get("brand_preference", "")),
        max_price=float(requirements.get("budget_max") or 0),
        query_text=" ".join(str(x) for x in requirements.get("soft_preferences", [])),
    )
    return products if isinstance(products, list) else []
