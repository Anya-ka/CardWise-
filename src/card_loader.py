"""
card_loader.py — Load and query the local card database.
No external API calls; pure Python + JSON.

load_cards() merges live research data from data/research_cache.json on top
of the static data/cards.json when a cached entry exists for a card.
"""

import json
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).parent.parent / "data" / "cards.json"


def load_cards(use_cache: bool = True) -> list[dict[str, Any]]:
    """
    Return the full list of cards.

    If use_cache=True (default), any card that has a cached research entry
    in research_cache.json will have its rewards, eligibility, fees, and
    benefits fields enriched with the live research data.
    Unresearched cards are returned unchanged from cards.json.
    """
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        cards = json.load(f)

    if not use_cache:
        return cards

    try:
        from src.cache import apply_cache_to_card
        return [apply_cache_to_card(card) for card in cards]
    except Exception:
        # If cache loading fails for any reason, fall back to static data
        return cards


def get_card_by_id(card_id: str) -> dict[str, Any] | None:
    """Return a single card dict by its id, or None if not found."""
    for card in load_cards():
        if card["id"] == card_id:
            return card
    return None


def check_eligibility(card: dict, profile: dict) -> tuple[bool, list[str]]:
    """
    Deterministic eligibility check.

    profile keys (all optional — missing keys are skipped):
        age (int)
        employment_type (str): "salaried" | "self_employed" | "student" | "retired"
        monthly_income_inr (int)
        credit_score (int)

    Returns (eligible: bool, reasons: list[str])
    reasons is non-empty only when eligible is False.
    """
    elig = card.get("eligibility", {})
    reasons: list[str] = []

    age = profile.get("age")
    if age is not None:
        if "min_age" in elig and age < elig["min_age"]:
            reasons.append(f"Minimum age is {elig['min_age']} (yours: {age})")
        if "max_age" in elig and age > elig["max_age"]:
            reasons.append(f"Maximum age is {elig['max_age']} (yours: {age})")

    emp = profile.get("employment_type", "").lower()
    if emp and "employment_types" in elig:
        if emp not in elig["employment_types"]:
            allowed = ", ".join(elig["employment_types"])
            reasons.append(f"Employment type '{emp}' not accepted (allowed: {allowed})")

    income = profile.get("monthly_income_inr")
    if income is not None and "min_income_monthly_inr" in elig:
        if income < elig["min_income_monthly_inr"]:
            reasons.append(
                f"Minimum monthly income ₹{elig['min_income_monthly_inr']:,} "
                f"(yours: ₹{income:,})"
            )

    score = profile.get("credit_score")
    if score is not None and "credit_score_min" in elig:
        if score < elig["credit_score_min"]:
            reasons.append(
                f"Minimum credit score {elig['credit_score_min']} (yours: {score})"
            )

    return (len(reasons) == 0, reasons)


def calculate_rewards(card: dict, category: str, amount_inr: float) -> dict[str, Any]:
    """
    Deterministic reward calculation for a given spend.

    Returns a dict with:
        card_id, card_name, bank, category, amount_inr,
        reward_value_inr (float), reward_description (str),
        verified (bool), uncertainty_flag (bool), source_url (str | None)

    If reward data is missing or uncertain, reward_value_inr = 0.0 and
    reward_description explains why — never presents unverified values as fact.
    """
    rewards = card.get("rewards", {})
    verified = rewards.get("verified", False)
    uncertainty_flag = rewards.get("uncertainty_flag", True)
    source_url = rewards.get("source_url")
    unit = rewards.get("reward_unit", "")
    cat = category.lower().replace(" ", "_")

    reward_value_inr = 0.0
    description = "No reward data available."

    # ── Exclusion check — return ₹0 for documented excluded categories ────────
    excluded = [e.lower() for e in rewards.get("excluded_categories", [])]
    if cat in excluded:
        return {
            "card_id": card["id"],
            "card_name": card["name"],
            "bank": card["bank"],
            "category": category,
            "amount_inr": amount_inr,
            "reward_value_inr": 0.0,
            "reward_description": f"No reward — {category.replace('_', ' ')} is excluded for this card.",
            "verified": verified,
            "uncertainty_flag": uncertainty_flag,
            "source_url": source_url,
        }

    # ── Uncertainty fallback — cached data exists but key rates are unknown ──
    if uncertainty_flag and not rewards.get("cashback_rates") and not rewards.get("reward_points_per_100_inr"):
        return {
            "card_id": card["id"],
            "card_name": card["name"],
            "bank": card["bank"],
            "category": category,
            "amount_inr": amount_inr,
            "reward_value_inr": 0.0,
            "reward_description": "⚠️ Reward rates uncertain — verify with bank before applying.",
            "verified": False,
            "uncertainty_flag": True,
            "source_url": source_url,
        }

    if unit == "percent_cashback" or unit == "percent_cashback_amazon_pay_balance":
        rates: dict = rewards.get("cashback_rates") or {}
        # Use is-not-None so an explicit 0.0 rate is not treated as missing
        rate = rates[cat] if cat in rates and rates[cat] is not None else (
               rates["other"] if "other" in rates and rates["other"] is not None else 0.0)
        cap = rewards.get("monthly_cashback_cap_inr")
        raw = amount_inr * rate / 100
        if cap:
            raw = min(raw, cap)
        reward_value_inr = round(raw, 2)
        description = f"{rate}% cashback = ₹{reward_value_inr:,.2f}"
        if cap:
            description += f" (monthly cap ₹{cap:,})"

    elif unit in ("points_per_100_inr", "membership_rewards_points"):
        pts_map: dict = rewards.get("reward_points_per_100_inr") or {}
        # Use is-not-None so an explicit 0 pts rate is not treated as missing
        pts_per_100 = pts_map[cat] if cat in pts_map and pts_map[cat] is not None else (
                      pts_map["other"] if "other" in pts_map and pts_map["other"] is not None else 1)
        point_value = rewards.get("point_value_inr") or 0.25
        points_earned = int(amount_inr / 100) * pts_per_100
        reward_value_inr = round(points_earned * point_value, 2)
        description = (
            f"{pts_per_100} pts per ₹100 → {points_earned} pts "
            f"≈ ₹{reward_value_inr:,.2f} @ ₹{point_value}/pt"
        )

    return {
        "card_id": card["id"],
        "card_name": card["name"],
        "bank": card["bank"],
        "category": category,
        "amount_inr": amount_inr,
        "reward_value_inr": reward_value_inr,
        "reward_description": description,
        "verified": verified,
        "uncertainty_flag": uncertainty_flag,
        "source_url": source_url,
    }
