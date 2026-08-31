import json
import os
from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types

_client = None
MODEL = "gemini-2.5-flash"


def _get_client():
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        _client = genai.Client(api_key=key)
    return _client



def call_structured(system_prompt: str, user_message: str, max_tokens: int = 1000) -> dict:
    """Ask Gemini for JSON."""
    try:
        response = _get_client().models.generate_content(
            model=MODEL,
            contents=f"{system_prompt}\n\n{user_message}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=max_tokens,
            ),
        )
        return json.loads(response.text)
    except Exception as error:
        print(f"[Gemini] Structured call failed: {error}")
        return {}


def call_llm(prompt: str) -> str:
    """Ask Gemini for normal text."""
    try:
        response = _get_client().models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=300,
            ),
        )
        return response.text.strip() if response.text else ""
    except Exception as error:
        print(f"[Gemini] Call failed: {error}")
        return ""
