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


def _heuristic_fallback(text: str) -> dict:
    """Minimal outage fallback: extract only information that can be safely inferred generically."""
    t = text.lower()
    
    # 1. Budget extraction
    budget = None
    budget_match = re.search(r"(?:under|below|within|budget(?:\s+of)?|max(?:\s+of)?|<=?)\s*(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:,\d{3})+|\d{3,7})", t)
    if budget_match:
        budget = int(budget_match.group(1).replace(",", ""))
    else:
        raw_nums = re.findall(r"(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:,\d{3})+|\d{3,7})", t)
        nums = [int(x.replace(",", "")) for x in raw_nums if int(x.replace(",", "")) >= 100]
        budget = max(nums) if nums else None

    auto = None
    if any(x in t for x in ("auto-buy", "autobuy", "auto buy", "auto-pay", "autopay", "automatically")):
        auto = budget

    # 2. Category inference
    category = ""
    known_cats = [
        ("running shoes", ["running shoes", "running shoe", "road running shoes", "running sneakers", "jogging shoes"]),
        ("laptop", ["laptop", "notebook", "macbook", "ultrabook"]),
        ("monitor", ["monitor", "display", "gaming monitor"]),
        ("smartphone", ["smartphone", "mobile phone", "phone", "android phone", "iphone"]),
        ("earbuds", ["earbuds", "earbud", "tws", "airpods"]),
        ("headphones", ["headphones", "headphone", "earphones", "earphone", "neckband", "headset"]),
        ("smartwatch", ["smartwatch", "fitness band", "smart watch", "watch"]),
        ("camera", ["camera", "dslr", "mirrorless"]),
    ]

    for cat_name, aliases in known_cats:
        if any(re.search(r"\b" + re.escape(a) + r"\b", t) for a in aliases):
            category = cat_name
            break

    if not category:
        category_match = re.search(
            r"(?:find|buy|want|need|looking for|best|recommend|suggest|get|show)\s+(?:an?\s+|the\s+)?(.+?)(?:\s+(?:under|below|within|for|with)\b|$)",
            t,
        )
        if category_match:
            words = re.sub(r"[^a-z0-9 -]", " ", category_match.group(1)).split()
            category = " ".join(words[-2:]) or "product"
        else:
            category = "product"

    # 3. Extract atomic feature tokens
    hard_constraints = [f"price <= {budget}"] if budget else []
    soft_preferences = []

    ram = re.search(r"\b(\d{1,3}\s*GB)\s*(?:RAM)?\b", t, re.I)
    if ram:
        val = ram.group(1).upper().replace(" ", "")
        hard_constraints.append(f"{val} RAM")
    ssd = re.search(r"\b(\d{1,3}\s*(?:GB|TB))\s*(?:SSD|Storage)\b", t, re.I)
    if ssd:
        val = ssd.group(1).upper().replace(" ", "")
        hard_constraints.append(f"{val} SSD")
    hz = re.search(r"\b(\d{2,3}\s*Hz)\b", t, re.I)
    if hz:
        val = hz.group(1).upper().replace(" ", "")
        hard_constraints.append(val)
    screen = re.search(r"\b(\d{1,2}(?:\.\d{1,2})?)\s*(?:inch|\"|\-inch)\b", t, re.I)
    if screen:
        hard_constraints.append(f"{screen.group(1)} inch")

    # Keyword preferences
    if re.search(r"\b(?:anc|noise\s*cancel\w*)\b", t):
        soft_preferences.append("Active Noise Cancellation (ANC)")
    if re.search(r"\b(?:battery|battery\s*life)\b", t):
        soft_preferences.append("strong battery life")
    if re.search(r"\b(?:camera|photography)\b", t):
        soft_preferences.append("great camera quality")
    if re.search(r"\b(?:fast\s*charging|quick\s*charge)\b", t):
        soft_preferences.append("fast charging")
    if re.search(r"\b(?:cushion\w*|comfort)\b", t):
        soft_preferences.append("good cushioning")
    if re.search(r"\b(?:adjustable\s*stand|pivot|height\s*adjustable)\b", t):
        soft_preferences.append("adjustable stand")
    if re.search(r"\b(?:coding|programming|python|machine\s*learning|ml)\b", t):
        soft_preferences.append("coding and performance")
    if re.search(r"\b(?:gaming)\b", t):
        soft_preferences.append("gaming")
    if re.search(r"\b(?:travel)\b", t):
        soft_preferences.append("travel-friendly")
    if re.search(r"\b(?:road\s*running|5k|daily\s*runs?)\b", t):
        soft_preferences.append("road running")

    # 4. Priority order
    priorities = []
    prio_match = re.search(r"prioritize\s+([^,;.]+)", t)
    if prio_match:
        prio_word = prio_match.group(1).strip()
        priorities.append(prio_word)

    for p in (hard_constraints[1:] + soft_preferences):
        if p not in priorities:
            priorities.append(p)
    if budget:
        priorities.append("price")

    return {
        "category": category,
        "budget_max": float(budget) if budget else None,
        "use_case": f"{category} for {soft_preferences[0]}" if soft_preferences else category,
        "hard_constraints": hard_constraints,
        "soft_preferences": soft_preferences,
        "priority_order": priorities,
        "brand_preference": "",
        "auto_purchase_limit": float(auto) if auto else None,
        "purchase_intent": "auto_buy" if auto else "recommend",
    }


def extract_intent(user_goal: str) -> dict:
    data = call_structured(INTENT_SYSTEM_PROMPT, user_goal)
    return data if data and data.get("category") else _heuristic_fallback(user_goal)


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
