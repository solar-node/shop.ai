"""
Recommendation Agent (LLM):
Synthesizes candidate specifications, user requirements, and pricing positioning
into personalized recommendations and grounded hardware/value reasons.
"""
import re
from app.agents.llm_client import call_structured, call_llm


RECOMMENDATION_SYSTEM_PROMPT = """You are the BudBuy Recommendation Agent.
Given the user's shopping request and all structured evidence collected for a candidate product (hardware specifications, price vs budget, category, user preferences), synthesize:
1. "recommendation": A concise 2-sentence personalized recommendation explaining why this product is suitable.
2. "recommendation_reasons": A list of 3-4 distinct, concise bullet reasons (under 14 words each) explaining specifically why this product fits the user's goal.

RULES FOR "recommendation_reasons":
- Ground each reason in specific hardware/product evidence (ANC dB, battery endurance, dynamic drivers, IPX rating, fast charging, multipoint/mic features, or budget savings).
- Do NOT repeat or duplicate review/sentiment feedback (as AI Review is presented separately).
- Do NOT use generic marketing filler or say "Ranked #1".
- Do NOT repeat the exact same sentence structure across reasons.
- Respond ONLY with valid JSON."""


def extract_specific_evidence_reasons(candidate: dict, reqs: dict, user_goal: str = "", rev_info: dict = None) -> list[str]:
    """
    Extracts 3-4 distinct, evidence-grounded reasons from actual product specifications,
    hardware capabilities, and pricing headroom (excluding review feedback).
    """
    name = candidate.get("name", "")
    t = name.lower()
    reasons = []

    budget_max = float(reqs.get("budget_max") or 3000)
    price = float(candidate.get("effective_price") or candidate.get("price") or 0)
    brand_pref = reqs.get("brand_preference", "")
    user_g = (user_goal or "").lower()

    # ── 1. Brand Alignment (if explicitly requested) ────────────────────────
    if brand_pref and brand_pref.lower() in t:
        reasons.append(f"Directly matches your brand preference for {brand_pref}")

    # ── 2. Feature & Hardware Specification Highlights ──────────────────────
    # A. Active Noise Cancellation (ANC) with specific dB if present in title
    anc_match = re.search(r'(\d{2,3}\s*db)\s*(?:hybrid\s*)?anc', t) or re.search(r'anc\s*(?:with\s*)?(\d{2,3}\s*db)', t)
    if anc_match:
        db_val = anc_match.group(1).upper().replace(" ", "")
        reasons.append(f"{db_val} Hybrid ANC provides high noise-isolation in this category")
    elif "anc" in t or "noise cancell" in t or "active noise" in t:
        if "gym" in user_g or "workout" in user_g:
            reasons.append("Active Noise Cancellation provides strong focus for gym and commute")
        else:
            reasons.append("Verified Active Noise Cancellation aligns with your noise-isolation preference")

    # B. Driver & Sound Spec (e.g. 12.4mm / 13mm / 40mm / Bass / Spatial)
    driver_match = re.search(r'(\d{1,2}(?:\.\d)?\s*mm)\s*(?:dynamic|bass|titanium|driver)', t)
    if driver_match:
        dr_val = driver_match.group(1).replace(" ", "")
        reasons.append(f"{dr_val} dynamic drivers deliver punchy bass and acoustic clarity")
    elif "spatial audio" in t or "360" in t:
        reasons.append("Spatial audio support creates an immersive soundstage")
    elif "hi-res" in t or "lhdc" in t or "ldac" in t:
        reasons.append("Hi-Res audio codec support delivers high-definition sound resolution")
    elif "dsee" in t:
        reasons.append("DSEE audio upscaling restores high-frequency fidelity in compressed tracks")
    elif "extra bass" in t or "deep bass" in t or "bass" in t:
        reasons.append("Tuned bass profile provides dynamic, high-energy audio response")

    # C. Battery & Fast Charging Highlights
    battery_match = re.search(r'(\d{2,3})\s*(?:hours?|hrs?|h)\s*(?:total\s*)?(?:battery|playtime|playback)', t) or re.search(r'(?:battery|playtime|playback)\s*(?:upto\s*|up to\s*)?(\d{2,3})\s*(?:hours?|hrs?|h)', t)
    if battery_match:
        hrs = battery_match.group(1)
        reasons.append(f"{hrs}-hour battery endurance provides extensive multi-day playback")
    elif "quick charge" in t or "fast charge" in t or "fast charging" in t:
        reasons.append("Fast charging support provides hours of playback from a quick top-up")

    # D. Ergonomics / Workout / Gym / Durability
    if "ip55" in t or "ipx5" in t or "ipx4" in t or "ip54" in t or "ip68" in t:
        ip_rating = re.search(r'(ip[x\d]{2,3})', t)
        rating_str = ip_rating.group(1).upper() if ip_rating else "IP-certified"
        reasons.append(f"{rating_str} water and sweat resistance suitable for active workout use")
    elif "gym" in user_g or "workout" in user_g or "sport" in user_g:
        if "tws" in t or "earbuds" in t or "in-ear" in t:
            reasons.append("Ergonomic in-ear fit designed for stability during movement")

    # E. Connectivity, Microphones & Gaming
    if "multipoint" in t or "dual pairing" in t:
        reasons.append("Multipoint connectivity allows seamless switching between phone and laptop")
    elif "quad mic" in t or "4 mic" in t or "ai enc" in t or "enc" in t:
        reasons.append("AI-enhanced multi-mic array filters background noise during calls")
    elif "beast mode" in t or "low latency" in t or "50ms" in t or "gaming" in t:
        reasons.append("Low-latency mode minimizes audio lag during videos and gaming")

    # ── 3. Budget & Price Positioning ───────────────────────────────────────
    if price > 0 and budget_max > 0:
        savings = budget_max - price
        if savings >= 500:
            reasons.append(f"Priced at ₹{int(price):,}, leaving ₹{int(savings):,} budget headroom under your ₹{int(budget_max):,} limit")
        elif savings >= 0:
            reasons.append(f"₹{int(price):,} price stays strictly within your ₹{int(budget_max):,} budget ceiling")
        elif price <= budget_max * 1.1:
            reasons.append(f"Close to your ₹{int(budget_max):,} target with premium feature return")

    # Deduplicate while preserving order
    seen = set()
    unique_reasons = []
    for r in reasons:
        r_clean = r.strip()
        if r_clean and r_clean not in seen:
            seen.add(r_clean)
            unique_reasons.append(r_clean)

    # Return between 2 and 4 strong reasons
    return unique_reasons[:4] if len(unique_reasons) >= 2 else (unique_reasons + ["Matches core audio and performance criteria"])[:3]


def synthesize_recommendation_and_reasons(
    candidate: dict,
    reqs: dict,
    user_goal: str = "",
    rev_info: dict = None
) -> dict:
    """
    Synthesizes personalized recommendation text and structured recommendation reasons
    via Gemini LLM, with resilient evidence-grounded fallback.
    """
    rev_info = rev_info or {}
    name = candidate.get("name", "Product")
    price = float(candidate.get("effective_price") or candidate.get("price") or 2199.0)
    budget_max = float(reqs.get("budget_max") or 3000.0)

    # 1. First extract verified candidate-specific evidence
    grounded_evidence_reasons = extract_specific_evidence_reasons(candidate, reqs, user_goal, rev_info)

    user_prompt = (
        f"User Shopping Goal: {user_goal}\n"
        f"Target Budget: ₹{budget_max:,.0f}\n"
        f"Category: {reqs.get('category', 'earbuds')}\n"
        f"User Preferences: {', '.join(reqs.get('soft_preferences', [])) or 'General'}\n"
        f"Candidate Product: {name}\n"
        f"Price: ₹{price:,.0f}\n"
        f"Verified Hardware & Value Facts:\n" + "\n".join(f"- {r}" for r in grounded_evidence_reasons)
    )

    # 2. Attempt LLM structured generation
    data = call_structured(RECOMMENDATION_SYSTEM_PROMPT, user_prompt, max_tokens=600)
    
    recommendation = ""
    recommendation_reasons = []

    if data and isinstance(data, dict):
        recommendation = data.get("recommendation", "")
        reasons_list = data.get("recommendation_reasons") or data.get("why_this_product") or []
        if isinstance(reasons_list, list) and len(reasons_list) >= 2:
            cleaned_reasons = [str(r).strip().lstrip("•-*✓ ") for r in reasons_list if str(r).strip()]
            if len(cleaned_reasons) >= 2:
                recommendation_reasons = cleaned_reasons[:4]

    # 3. Fallback to evidence-grounded synthesis if LLM returned empty or was rate-limited
    if not recommendation:
        recommendation = (
            f"I recommend {name} at ₹{price:,.0f}. "
            f"It directly satisfies your requirements with verified hardware specifications and strong build quality."
        )

    if not recommendation_reasons:
        recommendation_reasons = grounded_evidence_reasons

    return {
        "recommendation": recommendation,
        "recommendation_reasons": recommendation_reasons,
        "why_this_product": recommendation_reasons,
    }
