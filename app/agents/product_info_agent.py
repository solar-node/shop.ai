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
    if result:
        return result
    return {"important_attributes": [], "evaluation_questions": []}
