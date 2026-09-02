"""LLM product-information researcher. It decides what attributes matter for the request."""
from app.agents.llm_client import call_structured

PROMPT = """You are Shop.ai's Product Information Research Agent.

Given the shopping plan below, determine which product attributes are useful for evaluating this category and use case.
Do NOT rely on a predefined category/attribute list. Infer the dimensions from the request.
Return JSON only:
{"important_attributes":["..."],"evaluation_questions":["..."]}
Keep the list practical (usually 4-8 items). Do not invent a product or specs.

SHOPPING PLAN:
"""


def research_product_attributes(requirements: dict, user_goal: str) -> dict:
    result = call_structured(PROMPT, f"{requirements}\nUSER GOAL: {user_goal}")
    if result and isinstance(result, dict) and result.get("important_attributes"):
        return result
    
    # Category-aware fallback attribute dimension planning
    cat = str(requirements.get("category") or "").lower()
    goal = (user_goal or "").lower()
    
    if any(k in cat or k in goal for k in ("laptop", "notebook", "macbook", "pc")):
        attrs = ["ram", "storage_ssd", "processor_cpu", "gpu_graphics", "battery_life", "display_resolution"]
    elif any(k in cat or k in goal for k in ("headphone", "earbud", "earphone", "audio", "tws")):
        attrs = ["noise_cancellation_anc", "battery_life_hours", "sound_quality_drivers", "comfort_fit", "microphone_calls"]
    elif any(k in cat or k in goal for k in ("monitor", "display", "screen")):
        attrs = ["refresh_rate_hz", "resolution_1440p_4k", "screen_size_inches", "panel_type_ips", "adjustable_stand"]
    elif any(k in cat or k in goal for k in ("phone", "smartphone", "mobile")):
        attrs = ["camera_ois_mp", "battery_capacity_mah", "fast_charging_wattage", "processor_chipset", "ram_storage"]
    elif any(k in cat or k in goal for k in ("shoe", "sneaker", "footwear", "running")):
        attrs = ["cushioning_technology", "running_surface_road_trail", "fit_width", "durability", "breathability"]
    else:
        attrs = [str(x).strip() for x in requirements.get("soft_preferences", []) if str(x).strip()] or ["specifications", "build_quality", "brand_reliability"]

    return {"important_attributes": attrs, "evaluation_questions": [f"Does the product satisfy {a}?" for a in attrs]}

