"""
cache.py — Persistence layer for TinyFish research results.

Writes to data/research_cache.json.
Schema per entry:
{
  "card_id":          str,          # matches id in cards.json, or free-form key
  "card_name":        str,
  "query":            str,          # the original research query
  "raw_answer":       str,          # Gemini markdown summary from TinyFish snippets
  "sources":          [{title, url, snippet}],
  "retrieved_at":     str,          # ISO-8601 UTC timestamp
  "structured":       {             # Gemini-extracted fields; null means unknown
    "annual_fee_inr":           int | null,
    "joining_fee_inr":          int | null,
    "fee_waiver_condition":     str | null,
    "reward_unit":              str | null,  # "percent_cashback" | "points_per_100_inr" | null
    "cashback_rates":           {category: float} | null,
    "reward_points_per_100_inr":{category: int}   | null,
    "point_value_inr":          float | null,
    "monthly_cashback_cap_inr": int | null,
    "eligibility": {
      "min_age":                int | null,
      "max_age":                int | null,
      "min_income_monthly_inr": int | null,
      "credit_score_min":       int | null,
      "employment_types":       [str] | null
    },
    "exclusions":               [str] | null,
    "key_benefits":             [str] | null,
    "uncertainty_flags":        [str]         # list of fields that are uncertain
  }
}
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CACHE_PATH = Path(__file__).parent.parent / "data" / "research_cache.json"

# ── Gemini extraction prompt ───────────────────────────────────────────────────
_EXTRACT_SYSTEM = """You are a data extraction assistant for an Indian credit card database.

Given a research report about a credit card, extract factual information into a
strict JSON object. Follow these rules exactly:

1. Use null for any field you cannot find or are uncertain about.
2. NEVER invent numbers. If the snippet says "up to 5%" without confirming the exact
   rate, set the field to null and add the field name to uncertainty_flags.
3. For cashback_rates and reward_points_per_100_inr, use lowercase_underscore keys
   matching these categories: online_shopping, dining, grocery, travel, fuel, movies,
   bill_payments, entertainment, other. Only include categories actually mentioned.
4. reward_unit must be exactly one of: "percent_cashback", "points_per_100_inr",
   "membership_rewards_points", "percent_cashback_amazon_pay_balance", or null.
5. Return ONLY valid JSON — no markdown, no code fences, no explanation.
"""

_EXTRACT_USER_TMPL = """Card name: {card_name}

Research summary:
{raw_answer}

Raw source snippets (use these for specific numbers like fees and rates):
{snippets_text}

Return a JSON object with exactly these keys:
{{
  "annual_fee_inr": <int or null>,
  "joining_fee_inr": <int or null>,
  "fee_waiver_condition": <str or null>,
  "reward_unit": <str or null>,
  "cashback_rates": <object or null>,
  "reward_points_per_100_inr": <object or null>,
  "point_value_inr": <float or null>,
  "monthly_cashback_cap_inr": <int or null>,
  "eligibility": {{
    "min_age": <int or null>,
    "max_age": <int or null>,
    "min_income_monthly_inr": <int or null>,
    "credit_score_min": <int or null>,
    "employment_types": <array of strings or null>
  }},
  "exclusions": <array of strings or null>,
  "key_benefits": <array of strings or null>,
  "uncertainty_flags": <array of field-name strings>
}}"""


# ── Load / save helpers ────────────────────────────────────────────────────────

def load_cache() -> dict[str, Any]:
    """Return the full cache dict keyed by card_id. Empty dict if no file."""
    if not _CACHE_PATH.exists():
        return {}
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ── Structured extraction ──────────────────────────────────────────────────────

def _extract_structured(card_name: str, raw_answer: str, sources: list[dict] | None = None) -> dict:
    """
    Ask Gemini to extract typed fields from the raw markdown research answer
    and the original TinyFish source snippets.
    Returns the structured dict, or a minimal fallback dict on failure.
    """
    from src.llm_client import chat  # local import to avoid circular dependency

    # Build a compact snippets block so Gemini has the raw evidence for fees
    snippets_text = ""
    if sources:
        snippets_text = "\n\n".join(
            f"[{s.get('title', s.get('url', ''))}] ({s.get('url', '')})\n{s.get('snippet', '')}"
            for s in sources[:6]
            if s.get("snippet")
        )

    user_msg = _EXTRACT_USER_TMPL.format(
        card_name=card_name,
        raw_answer=raw_answer[:4000],     # cap summary
        snippets_text=snippets_text[:2000] if snippets_text else "(no raw snippets available)",
    )
    raw = chat(_EXTRACT_SYSTEM, user_msg, temperature=0.0, max_tokens=2000)

    # Strip markdown code fences if Gemini adds them despite instructions
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Partial parse — try to extract the JSON object with a regex
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group())
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

    # Guarantee the required keys exist (fill with None/[] if missing)
    defaults: dict[str, Any] = {
        "annual_fee_inr": None,
        "joining_fee_inr": None,
        "fee_waiver_condition": None,
        "reward_unit": None,
        "cashback_rates": None,
        "reward_points_per_100_inr": None,
        "point_value_inr": None,
        "monthly_cashback_cap_inr": None,
        "eligibility": {
            "min_age": None,
            "max_age": None,
            "min_income_monthly_inr": None,
            "credit_score_min": None,
            "employment_types": None,
        },
        "exclusions": None,
        "key_benefits": None,
        "uncertainty_flags": [],
    }
    for k, v in defaults.items():
        if k not in data:
            data[k] = v

    if not isinstance(data.get("eligibility"), dict):
        data["eligibility"] = defaults["eligibility"]
    else:
        for ek, ev in defaults["eligibility"].items():
            if ek not in data["eligibility"]:
                data["eligibility"][ek] = ev

    if not isinstance(data.get("uncertainty_flags"), list):
        data["uncertainty_flags"] = []

    return data


# ── Public API ─────────────────────────────────────────────────────────────────

def save_research_result(
    card_id: str,
    card_name: str,
    query: str,
    raw_answer: str,
    sources: list[dict],
    extract_structured: bool = True,
) -> dict[str, Any]:
    """
    Persist a successful TinyFish result.

    - Loads existing cache so other cards' data is preserved.
    - Extracts structured fields via Gemini if extract_structured=True.
    - Writes back to data/research_cache.json atomically.
    - Returns the saved entry.
    """
    cache = load_cache()

    structured: dict = {}
    if extract_structured:
        structured = _extract_structured(card_name, raw_answer, sources=sources)

    entry: dict[str, Any] = {
        "card_id":      card_id,
        "card_name":    card_name,
        "query":        query,
        "raw_answer":   raw_answer,
        "sources":      sources,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "structured":   structured,
    }

    cache[card_id] = entry
    _save_cache(cache)
    return entry


def get_cached_entry(card_id: str) -> dict[str, Any] | None:
    """Return the cached entry for a card_id, or None."""
    return load_cache().get(card_id)


def apply_cache_to_card(card: dict) -> dict:
    """
    Merge cached structured data on top of a static card dict.

    - Fields that are non-null in the cache override the static card.
    - Marks rewards.verified=True, rewards.uncertainty_flag based on cache flags.
    - Adds a 'cache_retrieved_at' field for display.
    - Never removes fields that exist in the static card.
    - Returns a shallow-copy — does not mutate the original.
    """
    entry = get_cached_entry(card["id"])
    if not entry:
        return card

    merged = dict(card)  # shallow copy
    s = entry.get("structured", {})
    if not s:
        return merged

    uncertain_fields = set(s.get("uncertainty_flags", []))

    # ── Top-level fee fields ──────────────────────────────────────────────────
    for field in ("annual_fee_inr", "joining_fee_inr", "fee_waiver_condition"):
        if s.get(field) is not None and field not in uncertain_fields:
            merged[field] = s[field]

    # ── Rewards ───────────────────────────────────────────────────────────────
    rewards = dict(card.get("rewards", {}))  # shallow copy

    if s.get("reward_unit") and "reward_unit" not in uncertain_fields:
        rewards["reward_unit"] = s["reward_unit"]

    # ── Safe per-category merge — a cached null never overwrites a valid static value ──
    cached_cb = s.get("cashback_rates")
    cb_was_applied = False
    if isinstance(cached_cb, dict) and "cashback_rates" not in uncertain_fields:
        static_cb = dict(rewards.get("cashback_rates") or {})
        for cat, rate in cached_cb.items():
            if rate is not None:
                static_cb[cat] = rate
                cb_was_applied = True
        rewards["cashback_rates"] = static_cb

    cached_pts = s.get("reward_points_per_100_inr")
    pts_was_applied = False
    if isinstance(cached_pts, dict) and "reward_points_per_100_inr" not in uncertain_fields:
        static_pts = dict(rewards.get("reward_points_per_100_inr") or {})
        for cat, pts in cached_pts.items():
            if pts is not None:
                static_pts[cat] = pts
                pts_was_applied = True
        rewards["reward_points_per_100_inr"] = static_pts

    # uncertainty_flag: True only when a field that was actually APPLIED to the card
    # is flagged as uncertain. Fields that fell back to static are NOT uncertain.
    applied_uncertain = uncertain_fields & {
        f for f in uncertain_fields
        if (f == "cashback_rates" and cb_was_applied)
        or (f == "reward_points_per_100_inr" and pts_was_applied)
        or f in ("reward_unit", "point_value_inr", "monthly_cashback_cap_inr",
                 "annual_fee_inr", "joining_fee_inr")
    }
    rewards["uncertainty_flag"] = bool(applied_uncertain)

    if s.get("point_value_inr") is not None and "point_value_inr" not in uncertain_fields:
        rewards["point_value_inr"] = s["point_value_inr"]

    if "monthly_cashback_cap_inr" in s and "monthly_cashback_cap_inr" not in uncertain_fields:
        rewards["monthly_cashback_cap_inr"] = s["monthly_cashback_cap_inr"]

    # Mark verified only when the cache actually contributed rate data.
    # If the cache had no usable rates (all null), the static card's own
    # verified flag is already correct — do not upgrade it.
    cache_contributed_rates = cb_was_applied or pts_was_applied
    if cache_contributed_rates:
        rewards["verified"] = True
    # else: leave rewards["verified"] as it was from the static card

    if not rewards.get("source_url") and entry["sources"]:
        rewards["source_url"] = entry["sources"][0]["url"]

    merged["rewards"] = rewards

    # ── Eligibility ───────────────────────────────────────────────────────────
    cached_elig = s.get("eligibility", {}) or {}
    if any(v is not None for v in cached_elig.values()):
        elig = dict(card.get("eligibility", {}))
        for field in ("min_age", "max_age", "min_income_monthly_inr", "credit_score_min", "employment_types"):
            val = cached_elig.get(field)
            if val is not None and field not in uncertain_fields:
                elig[field] = val
        merged["eligibility"] = elig

    # ── Benefits / exclusions ─────────────────────────────────────────────────
    if s.get("key_benefits") and "key_benefits" not in uncertain_fields:
        merged["key_benefits"] = s["key_benefits"]

    if s.get("exclusions") and "exclusions" not in uncertain_fields:
        merged["exclusions"] = s["exclusions"]

    # ── Provenance ────────────────────────────────────────────────────────────
    merged["cache_retrieved_at"] = entry["retrieved_at"]
    merged["cache_sources"] = entry["sources"]

    return merged
