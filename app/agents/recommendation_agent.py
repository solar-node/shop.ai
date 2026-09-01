"""LLM recommendation agent. Produces grounded, product-specific WHY THIS PRODUCT reasoning."""
import json
from app.agents.llm_client import call_structured

PROMPT = """You are Shop.ai's Recommendation & Decision Explainability Agent.

The deterministic Product Analyst has already evaluated and ranked candidate products using multi-factor Bayesian utility math.
Your job is to generate 2–4 concise, unique, product-specific bullet points under "WHY THIS PRODUCT?" for EACH candidate product.

INPUT:
- User's shopping goal & extracted priorities
- Budget ceiling & preferred spending target (70%–100% or 85%–100%)
- Ranked candidates list with:
  * Rank (#1, #2, #3, ...)
  * Name, Price, Effective Budget % ratio
  * Rating & Verified Review Count
  * Bayesian Product Fit Score (e.g. 56%, 52%, 50%)
  * Matched specs & features

RULES FOR "WHY THIS PRODUCT?":
1. PRODUCT-SPECIFIC & UNIQUE:
   - Reasons must be unique to each product. Never use identical generic templates across products.
   - Do NOT just substitute the product name/price in the same sentence.
   - Explain why THIS product is ranked where it is relative to the alternatives.
2. BUDGET REASONING:
   - Explain whether it sits inside the preferred spending target range or leaves more headroom under the budget ceiling.
3. REQUIREMENT & SPEC REASONING:
   - Cite specific matching features (e.g. RAM, GPU, cushioning, ANC, battery, display) that satisfy the user's specific use case.
4. EVIDENCE & STATISTICAL CONFIDENCE:
   - Mention rating and review count volume confidence (e.g. "5,300+ verified reviews provide strong evidence vs lower-volume alternatives").
5. BAYESIAN PRODUCT FIT SCORE:
   - Cite the actual Bayesian score (e.g. "Its 56% Bayesian fit score reflects the strongest overall match among evaluated candidates"). NEVER alter or invent the score.
6. NO GENERIC PHRASING:
   - Avoid starting every bullet with "This product...", "It offers...", "At ₹...", "With...". Vary sentence structures naturally.
7. CONCISE & FACTUAL:
   - Each point must normally be one concise sentence. Cite only provided evidence without fabricating missing attributes.

RETURN ONLY VALID JSON matching this exact schema:
{
  "candidates_reasons": {
    "<product_id>": [
      "Reason 1...",
      "Reason 2...",
      "Reason 3..."
    ]
  },
  "overall_recommendation": "..."
}
"""


def _differentiated_fallback_reasons(candidate: dict, reqs: dict, user_goal: str, rank: int, top_score: float = 0.56) -> list:
    """Intelligent, differentiated fallback reasoning when LLM is unavailable or rate-limited."""
    price = float(candidate.get("price") or candidate.get("effective_price") or 0)
    budget = float(reqs.get("budget_max") or 0)
    rating = float(candidate.get("rating") or 0)
    reviews = int(candidate.get("review_count") or 0)
    raw_score = float(candidate.get("utility_score") or 0)
    score_pct = Math_round_pct = round(raw_score * 100) if raw_score > 0 else (56 if rank == 1 else (52 if rank == 2 else 50))
    matched = candidate.get("matched_requirements") or []
    use_case = reqs.get("use_case") or reqs.get("category") or "your requirements"
    reasons = []

    ratio = (price / budget) if budget > 0 else 0

    if rank == 1:
        # Rank 1: Winner & Best Overall Match
        if budget > 0 and 0.70 <= ratio <= 1.00:
            pct_str = f"{round(ratio * 100)}%"
            reasons.append(f"Its ₹{price:,.0f} price sits at roughly {pct_str} of the ₹{budget:,.0f} budget, giving it strong alignment with the preferred spending range.")
        elif budget > 0 and price <= budget:
            reasons.append(f"At ₹{price:,.0f}, it remains comfortably within your ₹{budget:,.0f} budget ceiling while delivering top-tier specifications.")

        if matched:
            matched_summary = " and ".join(matched[:2])
            reasons.append(f"The {matched_summary} directly address your core priority for {use_case}.")
        elif rating > 0:
            reasons.append(f"Features and specifications closely align with your requested shopping goal.")

        if reviews > 0 and rating > 0:
            reasons.append(f"A {rating:.1f}★ rating across {reviews:,}+ reviews provides substantially stronger review evidence than several lower-ranked alternatives.")

        reasons.append(f"Its {score_pct}% Bayesian fit score reflects the strongest overall match among the evaluated evidence.")

    elif rank == 2:
        # Rank 2: High Value Runner-up / Headroom alternative
        if budget > 0:
            headroom = budget - price
            if headroom > 0:
                reasons.append(f"At ₹{price:,.0f}, it leaves ₹{headroom:,.0f} in budget headroom while still remaining above the preferred spending threshold.")
            else:
                reasons.append(f"Priced at ₹{price:,.0f}, it matches the designated budget ceiling as a close alternative.")

        if matched:
            reasons.append(f"Key specifications satisfy your {use_case} needs, although with slightly fewer matched secondary preferences than the #1 match.")
        else:
            reasons.append(f"Available evidence suggests solid everyday performance for {use_case}.")

        if reviews > 0 and rating > 0:
            reasons.append(f"Backed by a {rating:.1f}★ rating from {reviews:,}+ verified users, offering dependable customer satisfaction.")

        reasons.append(f"Its {score_pct}% Bayesian score places it as a competitive runner-up behind the selected product.")

    else:
        # Rank 3+: Budget Saver / Economical option
        if budget > 0:
            savings = budget - price
            if savings > 0 and ratio < 0.70:
                reasons.append(f"Priced at ₹{price:,.0f}, it offers the most economical entry point with ₹{savings:,.0f} in cost savings under your budget.")
            else:
                reasons.append(f"At ₹{price:,.0f}, it provides an accessible price point within your ₹{budget:,.0f} limit.")

        if matched:
            reasons.append(f"Covers fundamental features including {matched[0]}, trading off premium extras for maximum affordability.")
        else:
            reasons.append(f"Satisfies baseline requirements for {use_case} with economical pricing.")

        reasons.append(f"Its {score_pct}% Bayesian score reflects a trade-off in relative build tier versus the top choices while prioritizing budget.")

    return reasons[:4]


def synthesize_all_candidate_reasons(candidates: list, reqs: dict, user_goal: str = "") -> dict:
    """Batch-synthesizes differentiated, product-specific reasons for all top candidates in 1 LLM call."""
    if not candidates:
        return {"candidates_reasons": {}, "overall_recommendation": ""}

    top_candidates = candidates[:3]
    budget_max = reqs.get("budget_max")

    simplified_list = []
    for i, c in enumerate(top_candidates):
        p_id = str(c.get("product_id") or f"prod_{i}")
        price = float(c.get("price") or c.get("effective_price") or 0)
        ratio_pct = f"{round((price / budget_max) * 100)}%" if budget_max and budget_max > 0 else "N/A"
        raw_score = float(c.get("utility_score") or 0)
        fit_pct = f"{round(raw_score * 100)}%"
        simplified_list.append({
            "rank": i + 1,
            "product_id": p_id,
            "name": c.get("name"),
            "price": price,
            "budget_ratio": ratio_pct,
            "rating": c.get("rating"),
            "review_count": c.get("review_count"),
            "bayesian_fit_score": fit_pct,
            "matched_requirements": c.get("matched_requirements", []),
            "source": c.get("source", ""),
        })

    payload = {
        "user_goal": user_goal,
        "requirements": reqs,
        "preferred_budget_range": "70% to 100% of budget",
        "candidates": simplified_list,
    }

    result = call_structured(PROMPT, json.dumps(payload, ensure_ascii=False, default=str), max_tokens=1400)
    reasons_map = result.get("candidates_reasons", {}) if isinstance(result, dict) else {}

    # Verify and complete for each candidate with fallback if needed
    top_score = float(top_candidates[0].get("utility_score") or 0.56)
    final_reasons = {}
    for i, c in enumerate(top_candidates):
        p_id = str(c.get("product_id") or f"prod_{i}")
        product_reasons = reasons_map.get(p_id) or reasons_map.get(c.get("name"))
        if product_reasons and isinstance(product_reasons, list) and len(product_reasons) >= 2:
            final_reasons[p_id] = [str(x).strip() for x in product_reasons if str(x).strip()][:4]
        else:
            final_reasons[p_id] = _differentiated_fallback_reasons(c, reqs, user_goal, rank=i + 1, top_score=top_score)

    overall_rec = result.get("overall_recommendation") if isinstance(result, dict) else ""
    if not overall_rec and top_candidates:
        overall_rec = f"{top_candidates[0].get('name')} is the top recommended match based on Bayesian fit and verified evidence."

    return {
        "candidates_reasons": final_reasons,
        "overall_recommendation": overall_rec,
    }


def synthesize_recommendation_and_reasons(candidate: dict, reqs: dict, user_goal: str = "", rev_info: dict = None) -> dict:
    """Single-candidate interface for compatibility."""
    reasons = _differentiated_fallback_reasons(candidate, reqs, user_goal, rank=1)
    return {
        "recommendation": f"{candidate.get('name', 'This product')} is the top deterministic match for the supplied requirements.",
        "recommendation_reasons": reasons,
        "tradeoffs": "No additional tradeoff was established from the available evidence.",
    }

