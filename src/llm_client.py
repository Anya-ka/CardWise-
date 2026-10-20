"""
llm_client.py — Thin wrapper around any OpenAI-compatible LLM API.
Falls back gracefully when no API key is configured.

Client is intentionally NOT cached so that .env changes are picked up
without needing to restart the Streamlit process.
"""

import os
from pathlib import Path
from dotenv import load_dotenv  # type: ignore

# Always reload .env on import so changes are picked up
load_dotenv(Path(__file__).parent.parent / ".env", override=True)


def _get_client():
    """Create a fresh client on each call — reads env vars at call time."""
    try:
        from openai import OpenAI  # type: ignore

        api_key = os.getenv("LLM_API_KEY", "")
        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        if not api_key or api_key == "your_llm_api_key_here":
            return None
        return OpenAI(api_key=api_key, base_url=base_url)
    except Exception:
        return None


def is_configured() -> bool:
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
    return _get_client() is not None


def chat(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.4,
    max_tokens: int = 8000,  # Gemini 2.5 Flash is a thinking model — needs headroom
) -> str:
    """
    Send a chat request and return the assistant reply as a string.
    Returns an error message string if the client is not configured.
    """
    client = _get_client()
    if client is None:
        return (
            "⚠️ **LLM not configured.** "
            "Add your `LLM_API_KEY` (and optionally `LLM_BASE_URL` and `LLM_MODEL`) "
            "to the `.env` file and restart the app."
        )

    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        err = str(exc)
        if "401" in err or "API key" in err.lower() or "invalid" in err.lower():
            return (
                "⚠️ **Invalid or expired API key.** "
                "Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey), "
                "copy your **existing** key (don't create a new one), and update `.env`."
            )
        if "429" in err or "quota" in err.lower():
            return "⚠️ **Rate limit hit.** You've exceeded the free tier quota. Wait a minute and try again."
        return f"⚠️ **LLM error:** {exc}"
