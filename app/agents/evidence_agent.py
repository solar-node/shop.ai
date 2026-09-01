"""LLM evidence synthesizer: joins independent research outputs into usable evidence."""
import json
from app.agents.llm_client import call_structured

PROMPT = """You are Shop.ai's Evidence Synthesis Agent.

Combine the marketplace listings, product-information research, and review/trust research into normalized evidence.
This is a synthesis task, not a ranking task.

For every marketplace product, return:
- product_id, name, price, seller/source, availability
- attributes: only attributes supported by the supplied evidence
- matched_requirements: requirements actually supported by the evidence
- missing_requirements: requirements that are contradicted or not supported
- review_evidence: rating, review_count, and an objective evidence summary

Rules:
1. Never invent a specification, merchant, price, rating, review, or stock status.
2. If a fact is unavailable, omit it or mark it unknown.
3. Do not choose a winner and do not calculate a utility score.
4. Review counts are statistical evidence, not proof of sentiment.
5. Keep the schema category-agnostic. The attributes dictionary may contain any keys.
6. Use the product-information research to decide which fields deserve attention; do not use a hardcoded attribute taxonomy.
7. Return ONLY JSON: {"normalized_products": [...]}.

FEW-SHOT REASONING PATTERN:
Input evidence: a listing says "16GB RAM / 512GB SSD" and the plan asks for 16GB RAM.
Correct: attributes include the supplied RAM/storage; matched_requirements includes 16GB RAM.
Incorrect: adding a GPU because laptops often have GPUs.

Input evidence: rating 4.0 with 12000 reviews.
Correct: preserve 4.0 and 12000 as separate facts.
Incorrect: calling it "excellent sentiment" or inventing review comments.
"""


def synthesize_evidence(
    marketplace_data: list,
    product_info_data: dict,
    review_trust_data: dict,
    requirements: dict,
    user_goal: str = "",
) -> list[dict]:
    if not marketplace_data:
        return []

    payload = {
        "user_goal": user_goal,
        "requirements": requirements,
        "product_information_research": product_info_data,
        "review_trust_research": review_trust_data,
        "marketplace_listings": marketplace_data,
    }
    result = call_structured(PROMPT, json.dumps(payload, ensure_ascii=False, default=str), max_tokens=4000)
    normalized = result.get("normalized_products", []) if isinstance(result, dict) else []
    by_id = {str(x.get("product_id")): x for x in normalized if isinstance(x, dict) and x.get("product_id")}

    # Safe merge: raw marketplace facts remain authoritative if the LLM omitted them.
    output = []
    for raw in marketplace_data:
        pid = str(raw.get("product_id"))
        item = dict(by_id.get(pid, {}))
        item["product_id"] = raw.get("product_id")
        item["name"] = raw.get("name", item.get("name", ""))
        item["price"] = raw.get("price", item.get("price", 0))
        item["source"] = raw.get("source", item.get("source", ""))
        item["seller"] = raw.get("seller", item.get("seller", raw.get("source", "")))
        item["image_url"] = raw.get("image_url", item.get("image_url", ""))
        item["flipkart_url"] = raw.get("flipkart_url", item.get("flipkart_url", ""))
        item["delivery"] = raw.get("delivery", item.get("delivery", ""))
        item["old_price"] = raw.get("old_price", item.get("old_price"))
        item["discount_pct"] = raw.get("discount_pct", item.get("discount_pct"))
        item["available_qty"] = raw.get("available_qty", item.get("available_qty", 0))
        item["rating"] = raw.get("rating", item.get("rating"))
        item["review_count"] = raw.get("review_count", item.get("review_count"))
        item["specs"] = raw.get("specs", item.get("specs", {})) or {}
        item["attributes"] = item.get("attributes", {}) or {}
        item["matched_requirements"] = item.get("matched_requirements", []) or []
        item["missing_requirements"] = item.get("missing_requirements", []) or []
        output.append(item)
    return output
