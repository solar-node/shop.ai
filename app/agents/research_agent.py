"""Intent planning and marketplace discovery for Shop.ai."""
import re
from app.agents.llm_client import call_structured
from app.mcp.client import merchant_client


INTENT_SYSTEM_PROMPT = """You are Shop.ai's Shopping Planner.

Turn a user's natural-language shopping goal into a compact, category-agnostic plan.
Infer the product category strictly from the request.
Do NOT invent specifications, features, preferences, or constraints that were not explicitly mentioned by the user or strictly required by their stated use case.
If the user did not specify RAM, SSD, ANC, battery, panel type, cushioning, etc., DO NOT add them.

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

Grounding Rules:
1. hard_constraints: Non-negotiable limits and explicit numeric/technical requirements stated by the user (e.g., "price <= 70000", "16GB RAM", "512GB SSD", "144Hz").
2. soft_preferences: Qualitative or optional preferences explicitly requested by the user (e.g., "good processor", "decent battery life", "IPS panel", "good cushioning", "breathability").
3. priority_order: Explicit priorities stated by the user (e.g., "performance over display quality") followed by their requested features and price.
4. Never hallucinate unstated attributes.

Examples:
User: Find wireless earbuds under 3000 for gym workouts with ANC and sweat resistance
Output: {"category":"earbuds","budget_max":3000,"use_case":"gym workouts","hard_constraints":["price <= 3000","wireless"],"soft_preferences":["ANC","sweat resistance"],"priority_order":["ANC","sweat resistance","price"],"brand_preference":"","auto_purchase_limit":null,"purchase_intent":"recommend"}

User: Find road running shoes under 6000 with good cushioning and breathability
Output: {"category":"running shoes","budget_max":6000,"use_case":"road running","hard_constraints":["price <= 6000"],"soft_preferences":["good cushioning","breathability"],"priority_order":["good cushioning","breathability","price"],"brand_preference":"","auto_purchase_limit":null,"purchase_intent":"recommend"}

User: Buy a camera automatically if it is below 50000 for travel
Output: {"category":"camera","budget_max":null,"use_case":"travel photography","hard_constraints":[],"soft_preferences":["travel-friendly"],"priority_order":["travel-friendly","price"],"brand_preference":"","auto_purchase_limit":50000,"purchase_intent":"auto_buy"}
"""


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


def _clean_search_token(term: str) -> str:
    """Normalizes technical constraint tokens into clean natural search keywords."""
    t = str(term).strip()
    if re.search(r"price\s*<=?", t, re.I):
        return ""
    m_ram = re.search(r"RAM\s*(?:>=|<=|=|>|<|:)?\s*(\d+\s*GB)", t, re.I)
    if m_ram:
        v = m_ram.group(1).replace(" ", "")
        return f"{v} RAM"
    m_ssd = re.search(r"(?:SSD|Storage)\s*(?:>=|<=|=|>|<|:)?\s*(\d+\s*(?:GB|TB))", t, re.I)
    if m_ssd:
        v = m_ssd.group(1).replace(" ", "")
        return f"{v} SSD"
    m_bat = re.search(r"(?:battery|battery capacity)\s*(?:>=|<=|=|>|<|:)?\s*(\d+\s*mAh)", t, re.I)
    if m_bat:
        v = m_bat.group(1).replace(" ", "")
        return f"{v} battery"
    cleaned = re.sub(r"[><=~]+", "", t).strip()
    cleaned = re.sub(r"\b(size|resolution|rating|compatibility)\b", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def build_search_query(requirements: dict, user_goal: str = "") -> str:
    """Constructs a natural, retrieval-friendly search query for shopping engines."""
    category = str(requirements.get("category") or "product").strip()
    budget = requirements.get("budget_max")
    brand = requirements.get("brand_preference") or ""

    raw_constraints = [_clean_search_token(x) for x in requirements.get("hard_constraints", [])]
    specs = [x for x in raw_constraints if x and len(x) < 30][:3]

    raw_prefs = [_clean_search_token(x) for x in requirements.get("soft_preferences", [])]
    prefs = [x for x in raw_prefs if x and len(x) < 25 and not any(w in x.lower() for w in ("over", "prioritize", "price"))][:2]

    query_parts = []
    if brand:
        query_parts.append(brand)
    query_parts.append(category)

    if specs:
        query_parts.append(" ".join(specs))
    elif prefs:
        query_parts.append(" ".join(prefs))

    if budget:
        query_parts.append(f"under {int(budget)}")

    return re.sub(r"\s+", " ", " ".join(query_parts)).strip()





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
