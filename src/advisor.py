"""
advisor.py — AI Credit Card Advisor logic.
Combines deterministic eligibility filtering with LLM explanation.
"""

import json
from typing import Any

from src.card_loader import load_cards, check_eligibility
from src.llm_client import chat, is_configured

_SYSTEM_PROMPT = """You are CardWise, an expert, unbiased credit card advisor for India.

Your job is to help users find the right credit card based on their profile and spending habits.

Rules you MUST follow:
1. Never guarantee credit card approval — banks have their own criteria.
2. Only reference cards from the provided JSON data. Do not invent cards or rewards.
3. When reward rates have an uncertainty flag, say so explicitly.
4. Keep answers grounded, friendly and concise — this is a hackathon demo audience.
5. Always mention the annual fee and how to waive it.
6. End with a brief disclaimer: "Approval is at the bank's discretion."
"""


def build_advisor_prompt(profile: dict, cards: list[dict]) -> str:
    profile_text = json.dumps(profile, ensure_ascii=False, indent=2)

    # Strip large cache_sources blobs before sending to LLM — keeps prompt lean
    slim_cards = []
    for card in cards:
        c = {k: v for k, v in card.items() if k != "cache_sources"}
        slim_cards.append(c)

    cards_text = json.dumps(slim_cards, ensure_ascii=False, indent=2)

    # Note which cards have live research data so Gemini can mention it
    researched = [c["name"] for c in cards if c.get("cache_retrieved_at")]
    research_note = (
        f"\n\nNote: Live research data (from TinyFish web search) is available for: "
        f"{', '.join(researched)}. These cards have up-to-date verified information."
        if researched else ""
    )

    return f"""User profile:
{profile_text}

Available cards (filtered for basic eligibility):{research_note}
{cards_text}

Based on the profile, recommend the 2-3 best cards. For each:
- Name and bank
- Why it suits this user
- Key rewards relevant to their spending
- Annual fee and waiver condition
- Any caveats or exclusions to be aware of
- If the card has live research data, mention it was recently verified from official sources

Format your response in clear Markdown with one section per card.
"""


def get_recommendations(profile: dict) -> dict[str, Any]:
    """
    Returns:
        eligible_cards: list of card dicts that pass basic eligibility
        llm_response: markdown string from the LLM (or fallback message)
        llm_available: bool
    """
    all_cards = load_cards()

    eligible_cards = []
    for card in all_cards:
        ok, _ = check_eligibility(card, profile)
        if ok:
            eligible_cards.append(card)

    if not eligible_cards:
        return {
            "eligible_cards": [],
            "llm_response": "No cards matched your eligibility criteria. Try adjusting your profile.",
            "llm_available": False,
        }

    prompt = build_advisor_prompt(profile, eligible_cards)
    response = chat(_SYSTEM_PROMPT, prompt)

    return {
        "eligible_cards": eligible_cards,
        "llm_response": response,
        "llm_available": is_configured(),
    }
