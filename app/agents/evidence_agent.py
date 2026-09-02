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

    from app.commerce.spec_extractor import extract_product_specs, match_requirements_against_product

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

    output = []
    category = str(requirements.get("category") or "")

    for raw in marketplace_data:
        pid = str(raw.get("product_id"))
        llm_item = dict(by_id.get(pid, {}))
        
        name = raw.get("name", llm_item.get("name", ""))
        delivery = raw.get("delivery", llm_item.get("delivery", ""))
        badge = raw.get("badge", llm_item.get("badge", ""))
        
        # 1. Deterministic evidence extraction
        raw_specs = raw.get("specs") or {}
        extracted_specs = extract_product_specs(name, snippet=delivery, category=category, badge=badge)
        merged_specs = {**raw_specs, **extracted_specs, **(llm_item.get("specs") or {})}
        
        # 2. Merge attributes
        merged_attributes = {**merged_specs, **(raw.get("attributes") or {}), **(llm_item.get("attributes") or {})}
        
        item = {
            "product_id": raw.get("product_id"),
            "name": name,
            "price": raw.get("price", llm_item.get("price", 0)),
            "source": raw.get("source", llm_item.get("source", "")),
            "seller": raw.get("seller", llm_item.get("seller", raw.get("source", ""))),
            "image_url": raw.get("image_url", llm_item.get("image_url", "")),
            "flipkart_url": raw.get("flipkart_url", llm_item.get("flipkart_url", "")),
            "delivery": delivery,
            "old_price": raw.get("old_price", llm_item.get("old_price")),
            "discount_pct": raw.get("discount_pct", llm_item.get("discount_pct")),
            "available_qty": raw.get("available_qty", llm_item.get("available_qty")),
            "availability": raw.get("availability", llm_item.get("availability", "in_stock")),
            "rating": raw.get("rating", llm_item.get("rating")),
            "review_count": raw.get("review_count", llm_item.get("review_count")),
            "specs": merged_specs,
            "attributes": merged_attributes,
        }

        # 3. Grounded requirement matching
        matched, contradicted, unknown, feat_score = match_requirements_against_product(item, requirements, user_goal)
        
        # Incorporate LLM matched requirements if supported by text
        llm_matched = [str(x).strip() for x in llm_item.get("matched_requirements", []) if str(x).strip()]
        for m in llm_matched:
            if m.lower() not in [x.lower() for x in matched]:
                matched.append(m)

        llm_missing = [str(x).strip() for x in llm_item.get("missing_requirements", []) if str(x).strip()]
        for mis in llm_missing:
            if mis.lower() not in [x.lower() for x in contradicted] and mis.lower() not in [x.lower() for x in matched]:
                contradicted.append(mis)

        item["matched_requirements"] = matched
        item["missing_requirements"] = contradicted
        item["unknown_requirements"] = unknown
        item["feature_match_score"] = feat_score
        output.append(item)


    return output

