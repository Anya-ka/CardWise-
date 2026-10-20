"""
research_agent.py — TinyFish Research Agent wrapper.

Strategy (fast, ~20 seconds):
  1. TinyFish Search SDK  — instant, free, returns top results with snippets
  2. Gemini               — summarises snippets into a structured markdown answer
  3. cache.py             — persists result + extracts structured fields to JSON

Auth:  X-API-Key (via SDK)
Docs:  https://tinyfish.mintlify.app/search-api/reference
"""

import os
import re
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# Mapping of name fragments → card IDs in cards.json
# Used to auto-detect which card a free-text query is about
_CARD_ID_MAP = {
    "millennia":      "hdfc_millennia",
    "hdfc millennia": "hdfc_millennia",
    "simplysave":     "sbi_simplysave",
    "sbi simplysave": "sbi_simplysave",
    "ace":            "axis_ace",
    "axis ace":       "axis_ace",
    "membership rewards": "amex_mrcc",
    "amex mrcc":      "amex_mrcc",
    "american express membership": "amex_mrcc",
    "amazon pay icici": "icici_amazon_pay",
    "amazon pay":     "icici_amazon_pay",
}


def _detect_card_id(query: str) -> tuple[str, str]:
    """
    Return (card_id, card_name) if the query mentions a known card,
    else ("research__<slug>", <query[:40]>) as a generic key.
    """
    q = query.lower()
    for fragment, cid in _CARD_ID_MAP.items():
        if fragment in q:
            # Look up the canonical name from cards.json
            try:
                from src.card_loader import get_card_by_id
                card = get_card_by_id(cid)
                if card:
                    return cid, card["name"]
            except Exception:
                pass
            return cid, fragment.title()
    slug = re.sub(r"[^a-z0-9]+", "_", q)[:40].strip("_")
    return f"research__{slug}", query[:60]


def is_configured() -> bool:
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
    key = os.getenv("TINYFISH_API_KEY", "")
    return bool(key) and key != "your_tinyfish_api_key_here"


def research_card(query: str, progress_callback=None, force_refresh: bool = False) -> dict[str, Any]:
    """
    Research a credit card query using TinyFish Search + Gemini summarisation.
    Persists successful results to data/research_cache.json.

    Returns:
        success (bool)
        answer (str)            — markdown research summary
        sources (list)          — list of {title, url, snippet} dicts
        card_id (str)           — detected or generated card identifier
        card_name (str)         — detected card name
        retrieved_at (str|None) — ISO timestamp if saved successfully
        error (str | None)
    """
    if not is_configured():
        return {
            "success": False,
            "answer": (
                "⚠️ **TinyFish not configured.**\n\n"
                "Add your `TINYFISH_API_KEY` to the `.env` file and restart the app."
            ),
            "sources": [],
            "card_id": "",
            "card_name": "",
            "retrieved_at": None,
            "error": "TINYFISH_API_KEY not set",
        }

    def _progress(msg: str):
        if progress_callback:
            progress_callback(msg)

    card_id, card_name = _detect_card_id(query)

    # ── Check cache first — skip API if already researched ────────────────────
    try:
        from src.cache import get_cached_entry
        existing = get_cached_entry(card_id)
        if existing and not card_id.startswith("research__") and not force_refresh:
            _progress("✅ Found in research cache — skipping API call.")
            return {
                "success": True,
                "answer": existing["raw_answer"],
                "sources": existing["sources"],
                "card_id": card_id,
                "card_name": existing["card_name"],
                "retrieved_at": existing["retrieved_at"],
                "from_cache": True,
                "error": None,
            }
    except Exception:
        pass  # if cache check fails, just proceed with live search

    # ── Step 1: TinyFish Search ────────────────────────────────────────────────
    _progress("🔍 Searching official bank sources…")

    # Official bank domains — sources from these are tagged "official"
    _OFFICIAL_DOMAINS = {
        "hdfcbank.com", "sbicard.com", "axisbank.com", "icicibank.com",
        "americanexpress.com", "kotak.com", "idfcfirstbank.com", "rbi.org.in",
    }
    # Trusted financial aggregators — tagged "aggregator"
    _AGGREGATOR_DOMAINS = {"bankbazaar.com", "paisabazaar.com"}

    def _source_type(url: str) -> str:
        """Return 'official', 'aggregator', or 'third_party' based on domain."""
        from urllib.parse import urlparse
        try:
            host = urlparse(url).hostname or ""
            # strip www.
            host = host.removeprefix("www.")
            if any(host == d or host.endswith("." + d) for d in _OFFICIAL_DOMAINS):
                return "official"
            if any(host == d or host.endswith("." + d) for d in _AGGREGATOR_DOMAINS):
                return "aggregator"
        except Exception:
            pass
        return "third_party"

    try:
        import tinyfish
        client = tinyfish.TinyFish(api_key=os.getenv("TINYFISH_API_KEY"))

        response = client.search.query(
            query=query,
            purpose=(
                "Find official information about credit card reward rates, "
                "eligibility, fees, and benefits from Indian bank websites."
            ),
            include_domains=(
                "hdfcbank.com,sbicard.com,axisbank.com,icicibank.com,"
                "americanexpress.com,kotak.com,idfcfirstbank.com,"
                "bankbazaar.com,paisabazaar.com,rbi.org.in"
            ),
            location="IN",
            language="en",
        )
        results = response.results or []

        # If domain-restricted search returns nothing, retry broadly
        if not results:
            _progress("Broadening search…")
            response = client.search.query(
                query=query,
                purpose="Find Indian credit card reward rates, fees, and eligibility.",
                location="IN",
                language="en",
            )
            results = response.results or []

    except Exception as exc:
        return {
            "success": False,
            "answer": f"⚠️ Search failed: {exc}",
            "sources": [],
            "card_id": card_id,
            "card_name": card_name,
            "retrieved_at": None,
            "error": str(exc),
        }

    if not results:
        return {
            "success": False,
            "answer": "⚠️ No results found. Try rephrasing your query.",
            "sources": [],
            "card_id": card_id,
            "card_name": card_name,
            "retrieved_at": None,
            "error": "no_results",
        }

    _progress(f"✅ Found {len(results)} sources. Fetching top official pages…")

    # ── Step 2: Build source list with quality tags ───────────────────────────
    sources = [
        {
            "title":       getattr(r, "title",   "") or getattr(r, "url", ""),
            "url":         getattr(r, "url",     ""),
            "snippet":     getattr(r, "snippet", "") or "",
            "source_type": _source_type(getattr(r, "url", "")),
        }
        for r in results[:8]
    ]

    # ── Step 2b: TinyFish Fetch — enrich top official sources ────────────────
    # Fetch full content from the top 2 official-domain URLs to get richer
    # text than search snippets alone. Falls back gracefully if fetch fails.
    official_urls = [
        s["url"] for s in sources
        if s["source_type"] == "official" and s["url"]
    ][:2]  # cap at 2 to stay within free tier and keep latency low

    fetched_content: dict[str, str] = {}  # url → extracted text
    if official_urls:
        try:
            fetch_resp = client.fetch.get_contents(
                urls=official_urls,
                purpose=(
                    "Extract credit card reward rates, cashback percentages, "
                    "annual fees, eligibility criteria, and exclusions."
                ),
                format="markdown",
            )
            for item in (fetch_resp if isinstance(fetch_resp, list) else [fetch_resp]):
                url = getattr(item, "url", "") or getattr(item, "requested_url", "")
                content = getattr(item, "content", "") or getattr(item, "markdown", "") or ""
                if url and content:
                    # Cap per-page content to avoid overwhelming the LLM
                    fetched_content[url] = content[:3000]
            if fetched_content:
                _progress(f"📄 Fetched full content from {len(fetched_content)} official page(s).")
        except Exception as fetch_exc:
            # Non-fatal — fall back to snippets only
            _progress(f"ℹ️ Fetch step skipped ({fetch_exc.__class__.__name__}), using snippets only.")

    # ── Step 3: Gemini summarisation ───────────────────────────────────────────
    # Build snippets text — search snippets first, then fetched content
    snippets_text = "\n\n".join(
        f"**[{s['source_type'].upper()} SOURCE]** [{s['title']}]({s['url']})\n{s['snippet']}"
        for s in sources
        if s["snippet"]
    )

    fetched_text = ""
    if fetched_content:
        fetched_text = "\n\n---\n**Full page content from official sources:**\n\n" + "\n\n".join(
            f"**{url}**\n{content}"
            for url, content in fetched_content.items()
        )

    system_prompt = """You are CardWise Research, an expert credit card analyst for India.
You are given web search snippets and (where available) full page content from official bank websites.
Synthesise them into a clear, structured markdown report answering the user's question.

Rules:
- Only state facts supported by the provided evidence. Do not invent numbers or rates.
- Prefer facts from OFFICIAL SOURCE over AGGREGATOR or THIRD_PARTY sources.
- If a fact comes only from a third-party source, flag it with ⚠️ (third-party only).
- If a fact is uncertain or vague, flag it with ⚠️.
- Cite the source URL inline for each key claim.
- Use clear markdown headings and bullet points.
- Keep it concise — 200 to 400 words max.
- End with a one-line disclaimer about verifying with the bank directly."""

    user_message = f"""User question: {query}

Search results (tagged by source quality):
{snippets_text}{fetched_text}

Write a concise, structured answer in markdown."""

    from src.llm_client import chat
    answer = chat(system_prompt, user_message, temperature=0.2)

    # ── Step 4: Persist to research_cache.json ────────────────────────────────
    retrieved_at = None
    if answer and not answer.startswith("⚠️"):
        _progress("💾 Saving research result…")
        try:
            from src.cache import save_research_result
            entry = save_research_result(
                card_id=card_id,
                card_name=card_name,
                query=query,
                raw_answer=answer,
                sources=sources,
                extract_structured=True,
            )
            retrieved_at = entry["retrieved_at"]
            _progress("✅ Research saved and structured data extracted.")
        except Exception as exc:
            # Non-fatal — still return the answer even if save fails
            _progress(f"⚠️ Could not save result: {exc}")

    return {
        "success": True,
        "answer": answer,
        "sources": sources,
        "card_id": card_id,
        "card_name": card_name,
        "retrieved_at": retrieved_at,
        "error": None,
    }
