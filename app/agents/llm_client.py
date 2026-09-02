"""LLM Client with Primary (Gemini) and Fallback (Groq) multi-provider architecture.
Supports structured JSON extraction across unseen domains with zero hardcoded heuristics.
"""
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

_client = None
PRIMARY_MODEL = "gemini-2.5-flash"
GROQ_MODELS = [
    os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
]



def _get_client():
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        _client = genai.Client(api_key=key)
    return _client


def _call_groq_structured(system_prompt: str, user_message: str, max_tokens: int = 1000) -> dict:
    """Fallback structured JSON call using Groq API with multi-model failover."""
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json",
    }

    last_error = None
    for model_name in GROQ_MODELS:
        try:
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
                "max_tokens": max_tokens,
            }
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
            else:
                last_error = f"Groq model {model_name} returned HTTP {resp.status_code}: {resp.text[:150]}"
        except Exception as exc:
            last_error = str(exc)

    raise RuntimeError(last_error or "Groq structured invocation failed across all configured models.")



@traceable(run_type="llm", name="Structured LLM (Gemini with Groq Fallback)")
def call_structured(system_prompt: str, user_message: str, max_tokens: int = 1000) -> dict:
    """Executes structured JSON completion via Primary (Gemini) with automatic Groq fallback."""
    data, _ = call_structured_with_provider(system_prompt, user_message, max_tokens)
    return data


def call_structured_with_provider(system_prompt: str, user_message: str, max_tokens: int = 1000) -> tuple[dict, str]:
    """Executes structured completion and returns (result_dict, provider_name)."""
    # 1. Primary Provider: Gemini
    try:
        response = _get_client().models.generate_content(
            model=PRIMARY_MODEL,
            contents=f"{system_prompt}\n\n{user_message}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=max_tokens,
            ),
        )
        if response and response.text:
            parsed = json.loads(response.text)
            if isinstance(parsed, dict) and parsed:
                return parsed, "gemini"
    except Exception as gemini_err:
        print(f"[LLM] Primary provider (Gemini) failed: {gemini_err}. Invoking Groq fallback...")

    # 2. Fallback Provider: Groq
    try:
        groq_parsed = _call_groq_structured(system_prompt, user_message, max_tokens)
        if isinstance(groq_parsed, dict) and groq_parsed:
            print(f"[LLM] Groq fallback successfully extracted structured response.")
            return groq_parsed, "groq"
    except Exception as groq_err:
        print(f"[LLM] Groq fallback failed: {groq_err}")

    # 3. Explicit failure state (no hardcoded guessing)
    return {}, "failed"


@traceable(run_type="llm", name="Text LLM (Gemini with Groq Fallback)")
def call_llm(prompt: str) -> str:
    """Executes text completion via Primary (Gemini) with Groq fallback."""
    try:
        response = _get_client().models.generate_content(
            model=PRIMARY_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=300,
            ),
        )
        if response and response.text:
            return response.text.strip()
    except Exception as gemini_err:
        print(f"[LLM] Primary text call (Gemini) failed: {gemini_err}. Invoking Groq fallback...")

    try:
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        if groq_key:
            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": os.getenv("GROQ_MODEL", GROQ_DEFAULT_MODEL),
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 300,
            }
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as groq_err:
        print(f"[LLM] Groq text fallback failed: {groq_err}")

    return ""

