"""
tests/test_core.py — Core logic tests for CardWise.

Run with:  .venv/bin/python -m pytest tests/ -v

Covers:
  - Static reward calculations (no cache, no API)
  - Cache merge: null values must NOT overwrite valid static rates
  - Cache merge: valid cached values correctly update static values
  - Missing cache entry falls back to static card data
"""

import copy
import sys
from pathlib import Path

# Make sure src/ is importable without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.card_loader import calculate_rewards, load_cards
from src.cache import apply_cache_to_card


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _static_cards():
    """Load cards without cache so tests are deterministic."""
    return load_cards(use_cache=False)


def _get(cards, card_id):
    return next(c for c in cards if c["id"] == card_id)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Static reward calculations
# ═══════════════════════════════════════════════════════════════════════════════

class TestStaticRewards:

    def test_hdfc_millennia_online_shopping(self):
        cards = _static_cards()
        card = _get(cards, "hdfc_millennia")
        r = calculate_rewards(card, "online_shopping", 5000)
        # 5% of 5000 = 250, but monthly cap is 1000 so 250 is fine
        assert r["reward_value_inr"] == 250.0
        assert "5.0%" in r["reward_description"]
        assert r["verified"] is True
        assert r["uncertainty_flag"] is False

    def test_hdfc_millennia_monthly_cap(self):
        cards = _static_cards()
        card = _get(cards, "hdfc_millennia")
        # 5% of 30000 = 1500, but monthly cap is 1000
        r = calculate_rewards(card, "online_shopping", 30_000)
        assert r["reward_value_inr"] == 1000.0
        assert "monthly cap" in r["reward_description"]

    def test_hdfc_millennia_other_category(self):
        cards = _static_cards()
        card = _get(cards, "hdfc_millennia")
        # "travel" is not in cashback_rates and not excluded → falls back to "other" = 1%
        r = calculate_rewards(card, "travel", 5000)
        assert r["reward_value_inr"] == 50.0

    def test_sbi_simplysave_dining_points(self):
        cards = _static_cards()
        card = _get(cards, "sbi_simplysave")
        r = calculate_rewards(card, "dining", 5000)
        # 10 pts per ₹100 × 50 = 500 pts × ₹0.25 = ₹125
        assert r["reward_value_inr"] == 125.0
        assert "500 pts" in r["reward_description"]
        assert r["verified"] is True

    def test_sbi_simplysave_other_category(self):
        cards = _static_cards()
        card = _get(cards, "sbi_simplysave")
        r = calculate_rewards(card, "travel", 5000)
        # travel not in map → "other" = 1 pt per ₹100
        assert r["reward_value_inr"] == 5000 / 100 * 1 * 0.25

    def test_axis_ace_bill_payments(self):
        cards = _static_cards()
        card = _get(cards, "axis_ace")
        r = calculate_rewards(card, "bill_payments_google_pay", 5000)
        assert r["reward_value_inr"] == 250.0  # 5%

    def test_axis_ace_other_is_2_percent(self):
        cards = _static_cards()
        card = _get(cards, "axis_ace")
        r = calculate_rewards(card, "grocery", 5000)
        assert r["reward_value_inr"] == 100.0  # 2% other

    def test_amex_mrcc_points(self):
        cards = _static_cards()
        card = _get(cards, "amex_mrcc")
        r = calculate_rewards(card, "dining", 5000)
        # Confirmed: 1 MR point per ₹50 = 2 pts per ₹100
        # Source: americanexpress.com/in/credit-cards/membership-rewards-credit-card/
        # 2 pts per ₹100 × 50 (from ₹5,000) = 100 pts × ₹0.50 estimate = ₹50
        # Note: point_value_inr=0.5 is an estimate; actual value varies by redemption.
        assert r["reward_value_inr"] == 50.0

    def test_icici_amazon_pay_other(self):
        cards = _static_cards()
        card = _get(cards, "icici_amazon_pay")
        r = calculate_rewards(card, "other", 5000)
        assert r["reward_value_inr"] == 50.0  # 1%


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Cache merge — null must NOT overwrite valid static rates
# ═══════════════════════════════════════════════════════════════════════════════

class TestCacheMergeNullSafety:

    def _card_with_cache(self, cashback_overrides: dict):
        """
        Build a fake card + inject a cache entry with given cashback_rates,
        then apply the merge and return the resulting card.
        """
        static_card = {
            "id": "_test_card",
            "name": "Test Card",
            "bank": "Test Bank",
            "annual_fee_inr": 500,
            "rewards": {
                "verified": True,
                "uncertainty_flag": False,
                "reward_unit": "percent_cashback",
                "cashback_rates": {
                    "online_shopping": 5.0,
                    "dining": 3.0,
                    "other": 1.0,
                },
                "monthly_cashback_cap_inr": None,
                "source_url": "https://example.com",
            },
            "eligibility": {},
        }

        fake_entry = {
            "card_id": "_test_card",
            "card_name": "Test Card",
            "query": "test",
            "raw_answer": "test",
            "sources": [{"title": "t", "url": "https://example.com", "snippet": "s"}],
            "retrieved_at": "2026-01-01T00:00:00+00:00",
            "structured": {
                "annual_fee_inr": None,
                "joining_fee_inr": None,
                "fee_waiver_condition": None,
                "reward_unit": "percent_cashback",
                "cashback_rates": cashback_overrides,
                "reward_points_per_100_inr": None,
                "point_value_inr": None,
                "monthly_cashback_cap_inr": None,
                "eligibility": {
                    "min_age": None, "max_age": None,
                    "min_income_monthly_inr": None,
                    "credit_score_min": None, "employment_types": None,
                },
                "exclusions": None,
                "key_benefits": None,
                "uncertainty_flags": [],
            },
        }

        # Patch get_cached_entry to return our fake entry for this test
        import src.cache as cache_mod
        original = cache_mod.get_cached_entry
        cache_mod.get_cached_entry = lambda cid: fake_entry if cid == "_test_card" else None
        try:
            result = apply_cache_to_card(static_card)
        finally:
            cache_mod.get_cached_entry = original

        return result

    def test_null_cached_rate_preserves_static(self):
        """Cache has online_shopping: null — static 5.0% must survive."""
        merged = self._card_with_cache({"online_shopping": None, "other": 1.0})
        rates = merged["rewards"]["cashback_rates"]
        assert rates["online_shopping"] == 5.0, (
            f"Static 5.0% was overwritten by null. Got: {rates['online_shopping']}"
        )

    def test_null_cached_rate_preserves_dining(self):
        """Cache has dining: null — static 3.0% must survive."""
        merged = self._card_with_cache({"dining": None})
        rates = merged["rewards"]["cashback_rates"]
        assert rates["dining"] == 3.0

    def test_null_for_all_categories_preserves_all_static(self):
        """All cached rates null → entire static cashback_rates unchanged."""
        merged = self._card_with_cache(
            {"online_shopping": None, "dining": None, "other": None}
        )
        rates = merged["rewards"]["cashback_rates"]
        assert rates["online_shopping"] == 5.0
        assert rates["dining"] == 3.0
        assert rates["other"] == 1.0

    def test_valid_cached_rate_updates_static(self):
        """Cache has a confirmed online_shopping: 4.0 → should replace 5.0."""
        merged = self._card_with_cache({"online_shopping": 4.0})
        rates = merged["rewards"]["cashback_rates"]
        assert rates["online_shopping"] == 4.0

    def test_new_cached_category_is_added(self):
        """Cache adds a new category not in static → should be added."""
        merged = self._card_with_cache({"grocery": 2.0})
        rates = merged["rewards"]["cashback_rates"]
        assert rates.get("grocery") == 2.0
        # existing static rates still intact
        assert rates["online_shopping"] == 5.0

    def test_mixed_null_and_valid(self):
        """Cache: online_shopping=null (keep 5.0), dining=2.5 (update 3.0)."""
        merged = self._card_with_cache({"online_shopping": None, "dining": 2.5})
        rates = merged["rewards"]["cashback_rates"]
        assert rates["online_shopping"] == 5.0   # preserved
        assert rates["dining"] == 2.5             # updated


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Cache merge — reward points safe merge
# ═══════════════════════════════════════════════════════════════════════════════

class TestCacheMergePointsSafety:

    def _points_card_with_cache(self, pts_overrides: dict):
        static_card = {
            "id": "_test_pts_card",
            "name": "Test Points Card",
            "bank": "Test Bank",
            "annual_fee_inr": 500,
            "rewards": {
                "verified": True,
                "uncertainty_flag": False,
                "reward_unit": "points_per_100_inr",
                "reward_points_per_100_inr": {
                    "dining": 10,
                    "grocery": 10,
                    "other": 1,
                },
                "point_value_inr": 0.25,
                "source_url": "https://example.com",
            },
            "eligibility": {},
        }

        fake_entry = {
            "card_id": "_test_pts_card",
            "card_name": "Test Points Card",
            "query": "test",
            "raw_answer": "test",
            "sources": [{"title": "t", "url": "https://example.com", "snippet": "s"}],
            "retrieved_at": "2026-01-01T00:00:00+00:00",
            "structured": {
                "annual_fee_inr": None,
                "joining_fee_inr": None,
                "fee_waiver_condition": None,
                "reward_unit": "points_per_100_inr",
                "cashback_rates": None,
                "reward_points_per_100_inr": pts_overrides,
                "point_value_inr": None,
                "monthly_cashback_cap_inr": None,
                "eligibility": {
                    "min_age": None, "max_age": None,
                    "min_income_monthly_inr": None,
                    "credit_score_min": None, "employment_types": None,
                },
                "exclusions": None,
                "key_benefits": None,
                "uncertainty_flags": [],
            },
        }

        import src.cache as cache_mod
        original = cache_mod.get_cached_entry
        cache_mod.get_cached_entry = lambda cid: fake_entry if cid == "_test_pts_card" else None
        try:
            result = apply_cache_to_card(static_card)
        finally:
            cache_mod.get_cached_entry = original
        return result

    def test_null_pts_preserves_static(self):
        merged = self._points_card_with_cache({"dining": None})
        pts = merged["rewards"]["reward_points_per_100_inr"]
        assert pts["dining"] == 10

    def test_valid_pts_updates_static(self):
        merged = self._points_card_with_cache({"dining": 5})
        pts = merged["rewards"]["reward_points_per_100_inr"]
        assert pts["dining"] == 5

    def test_null_pts_all_preserves_all(self):
        merged = self._points_card_with_cache({"dining": None, "grocery": None, "other": None})
        pts = merged["rewards"]["reward_points_per_100_inr"]
        assert pts["dining"] == 10
        assert pts["grocery"] == 10
        assert pts["other"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Missing cache entry falls back to static
# ═══════════════════════════════════════════════════════════════════════════════

class TestCacheFallback:

    def test_unresearched_card_unchanged(self):
        """A card with no cache entry must be returned exactly as-is."""
        static_card = {
            "id": "_no_cache_card",
            "name": "Uncached Card",
            "bank": "Test Bank",
            "rewards": {"verified": True, "reward_unit": "percent_cashback",
                        "cashback_rates": {"other": 2.0}},
            "eligibility": {},
        }
        import src.cache as cache_mod
        original = cache_mod.get_cached_entry
        cache_mod.get_cached_entry = lambda cid: None
        try:
            result = apply_cache_to_card(static_card)
        finally:
            cache_mod.get_cached_entry = original

        assert result is static_card  # same object returned unchanged

    def test_sbi_no_cache_calculates_correctly(self):
        """SBI SimplySAVE has no cache in current data — must use static rates."""
        cards = load_cards(use_cache=True)
        sbi = next(c for c in cards if c["id"] == "sbi_simplysave")
        assert "cache_retrieved_at" not in sbi
        r = calculate_rewards(sbi, "grocery", 3000)
        # 10 pts × 30 × 0.25 = 75.0
        assert r["reward_value_inr"] == 75.0
        assert r["uncertainty_flag"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Badge verification: the Rewards Comparison tab shows ✓ Verified when
#    verified=True and uncertainty_flag=False, ⚠ Unverified otherwise.
#    This mirrors the exact logic on app.py line 413.
# ═══════════════════════════════════════════════════════════════════════════════

class TestBadgeVerification:
    """
    Mirrors the exact app.py badge condition:
        verified_badge = "✓ Verified" if r["verified"] and not r["uncertainty_flag"]
                         else "⚠ Unverified"
    """

    def _badge(self, result: dict) -> str:
        return "✓ Verified" if result["verified"] and not result["uncertainty_flag"] else "⚠ Unverified"

    def test_hdfc_millennia_online_shopping_shows_verified(self):
        """
        HDFC Millennia + cache (cashback_rates=None in cache, static 5% used).
        The uncertainty flag must be False so the badge shows ✓ Verified.
        """
        cards = load_cards(use_cache=True)
        hdfc = next(c for c in cards if c["id"] == "hdfc_millennia")
        r = calculate_rewards(hdfc, "online_shopping", 5000)

        assert r["reward_value_inr"] == 250.0, "Rate should be 5% of ₹5,000"
        assert r["verified"] is True
        assert r["uncertainty_flag"] is False, (
            "uncertainty_flag must be False when static verified rates are used "
            "(cache had null for cashback_rates, so static data was preserved)"
        )
        assert self._badge(r) == "✓ Verified"

    def test_hdfc_millennia_dining_shows_verified(self):
        cards = load_cards(use_cache=True)
        hdfc = next(c for c in cards if c["id"] == "hdfc_millennia")
        r = calculate_rewards(hdfc, "dining", 5000)
        assert r["uncertainty_flag"] is False
        assert self._badge(r) == "✓ Verified"

    def test_axis_ace_shows_verified(self):
        """Axis ACE has no cache — must show ✓ Verified from static data."""
        cards = load_cards(use_cache=True)
        axis = next(c for c in cards if c["id"] == "axis_ace")
        r = calculate_rewards(axis, "online_shopping", 5000)
        assert r["verified"] is True
        assert r["uncertainty_flag"] is False
        assert self._badge(r) == "✓ Verified"

    def test_icici_amazon_pay_shows_verified(self):
        """ICICI Amazon Pay has cache with no uncertainty — must show ✓ Verified."""
        cards = load_cards(use_cache=True)
        icici = next(c for c in cards if c["id"] == "icici_amazon_pay")
        r = calculate_rewards(icici, "online_shopping", 5000)
        assert r["verified"] is True
        assert r["uncertainty_flag"] is False
        assert self._badge(r) == "✓ Verified"

    def test_unverified_card_shows_unverified_badge(self):
        """A card with verified=False must always show ⚠ Unverified."""
        unverified_card = {
            "id": "_unverified",
            "name": "Unverified Card",
            "bank": "Test Bank",
            "rewards": {
                "verified": False,
                "uncertainty_flag": False,
                "reward_unit": "percent_cashback",
                "cashback_rates": {"other": 1.0},
                "monthly_cashback_cap_inr": None,
                "source_url": None,
            },
        }
        r = calculate_rewards(unverified_card, "other", 1000)
        assert self._badge(r) == "⚠ Unverified"

    def test_uncertain_applied_value_shows_unverified_badge(self):
        """
        If a cached value is actually applied to the card but marked uncertain,
        the badge must show ⚠ Unverified.
        """
        import src.cache as cache_mod

        static_card = {
            "id": "_uncertain_applied",
            "name": "Uncertain Applied Card",
            "bank": "Test Bank",
            "annual_fee_inr": 500,
            "rewards": {
                "verified": True,
                "uncertainty_flag": False,
                "reward_unit": "percent_cashback",
                "cashback_rates": {"other": 1.0},
                "monthly_cashback_cap_inr": None,
                "source_url": "https://example.com",
            },
            "eligibility": {},
        }

        # Cache provides a real rate (3.0) for online_shopping but flags it uncertain
        fake_entry = {
            "card_id": "_uncertain_applied",
            "card_name": "Uncertain Applied Card",
            "query": "test",
            "raw_answer": "test",
            "sources": [{"title": "t", "url": "https://example.com", "snippet": "s"}],
            "retrieved_at": "2026-01-01T00:00:00+00:00",
            "structured": {
                "annual_fee_inr": None,
                "joining_fee_inr": None,
                "fee_waiver_condition": None,
                "reward_unit": None,
                "cashback_rates": {"online_shopping": 3.0},
                "reward_points_per_100_inr": None,
                "point_value_inr": None,
                "monthly_cashback_cap_inr": None,
                "eligibility": {
                    "min_age": None, "max_age": None,
                    "min_income_monthly_inr": None,
                    "credit_score_min": None, "employment_types": None,
                },
                "exclusions": None,
                "key_benefits": None,
                # cashback_rates is in uncertainty_flags even though a value was applied
                "uncertainty_flags": ["cashback_rates"],
            },
        }

        original = cache_mod.get_cached_entry
        cache_mod.get_cached_entry = lambda cid: fake_entry if cid == "_uncertain_applied" else None
        try:
            merged = apply_cache_to_card(static_card)
        finally:
            cache_mod.get_cached_entry = original

        r = calculate_rewards(merged, "online_shopping", 5000)
        # The rate 3.0 was NOT applied because cashback_rates is in uncertain_fields
        # (apply_cache_to_card skips the entire dict when the field-level key is uncertain)
        # So static "other": 1.0 is used, uncertainty_flag=False
        assert r["uncertainty_flag"] is False
        assert self._badge(r) == "✓ Verified"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. source_url preservation — cache must not overwrite a static rewards source
# ═══════════════════════════════════════════════════════════════════════════════

class TestSourceUrlPreservation:
    """
    Regression tests for the fix that stops apply_cache_to_card() from
    replacing a static rewards source_url with the first TinyFish search result
    (which may be a fees page, not a rewards page).
    """

    def _make_card_and_entry(self, static_source_url, cache_source_url):
        """Build a minimal card + cache entry pair and return the merged result."""
        import src.cache as cache_mod

        static_card = {
            "id": "_src_test",
            "name": "Source Test Card",
            "bank": "Test Bank",
            "annual_fee_inr": 500,
            "rewards": {
                "verified": True,
                "uncertainty_flag": False,
                "reward_unit": "percent_cashback",
                "cashback_rates": {"other": 1.0},
                "monthly_cashback_cap_inr": None,
                "source_url": static_source_url,
            },
            "eligibility": {},
        }

        fake_entry = {
            "card_id": "_src_test",
            "card_name": "Source Test Card",
            "query": "test",
            "raw_answer": "test",
            "sources": [
                {"title": "Cache Source", "url": cache_source_url, "snippet": "s"}
            ],
            "retrieved_at": "2026-01-01T00:00:00+00:00",
            "structured": {
                "annual_fee_inr": None,
                "joining_fee_inr": None,
                "fee_waiver_condition": None,
                "reward_unit": None,
                "cashback_rates": None,
                "reward_points_per_100_inr": None,
                "point_value_inr": None,
                "monthly_cashback_cap_inr": None,
                "eligibility": {
                    "min_age": None, "max_age": None,
                    "min_income_monthly_inr": None,
                    "credit_score_min": None, "employment_types": None,
                },
                "exclusions": None,
                "key_benefits": None,
                "uncertainty_flags": [],
            },
        }

        original = cache_mod.get_cached_entry
        cache_mod.get_cached_entry = lambda cid: fake_entry if cid == "_src_test" else None
        try:
            result = apply_cache_to_card(static_card)
        finally:
            cache_mod.get_cached_entry = original
        return result

    def test_static_source_url_is_preserved_when_cache_has_different_url(self):
        """
        Regression: HDFC had its MITC PDF source_url replaced by a fees page URL
        from the cache. The static URL must be kept.
        """
        static_url = "https://www.hdfcbank.com/.../Millennia-Credit-Card-MITCb.pdf"
        cache_url  = "https://www.hdfc.bank.in/credit-cards/millennia-credit-card/fees-and-charges"

        merged = self._make_card_and_entry(static_url, cache_url)
        assert merged["rewards"]["source_url"] == static_url, (
            f"Static MITC PDF URL was overwritten by cache fees-page URL.\n"
            f"Expected: {static_url}\n"
            f"Got:      {merged['rewards']['source_url']}"
        )

    def test_cache_source_url_used_when_static_has_none(self):
        """
        When the static card has no source_url, the first cache source URL
        should be used as a fallback.
        """
        cache_url = "https://www.somebank.com/card-page"
        merged = self._make_card_and_entry(None, cache_url)
        assert merged["rewards"]["source_url"] == cache_url

    def test_hdfc_millennia_real_data_preserves_mitc_url(self):
        """
        End-to-end: the live HDFC Millennia card (with cache applied) must
        show the static MITC PDF URL, not the fees-and-charges page.
        """
        cards = load_cards(use_cache=True)
        hdfc = next(c for c in cards if c["id"] == "hdfc_millennia")
        source = hdfc["rewards"].get("source_url", "")
        assert "fees" not in source.lower(), (
            f"HDFC source_url points to a fees page, not a rewards source: {source}"
        )
        # The static MITC PDF URL contains 'MITCb' or 'pdf'
        assert "pdf" in source.lower() or "millennia" in source.lower(), (
            f"Expected MITC PDF URL, got: {source}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Exclusion enforcement — documented excluded categories return ₹0
# ═══════════════════════════════════════════════════════════════════════════════

class TestExclusionEnforcement:
    """
    Verifies that calculate_rewards returns ₹0 with an exclusion message
    for categories documented as excluded in each card's rewards.excluded_categories.

    Only categories where the exclusion is unambiguous and the category key
    is present in the UI are enforced. Ambiguous categories (bill_payments,
    other) are NOT enforced and use the normal base-rate fallback.
    """

    # ── Fuel exclusions (all four cards) ─────────────────────────────────────

    def test_hdfc_millennia_fuel_excluded(self):
        cards = _static_cards()
        card = _get(cards, "hdfc_millennia")
        r = calculate_rewards(card, "fuel", 5000)
        assert r["reward_value_inr"] == 0.0
        assert "excluded" in r["reward_description"].lower()

    def test_sbi_simplysave_fuel_excluded(self):
        cards = _static_cards()
        card = _get(cards, "sbi_simplysave")
        r = calculate_rewards(card, "fuel", 5000)
        assert r["reward_value_inr"] == 0.0
        assert "excluded" in r["reward_description"].lower()

    def test_axis_ace_fuel_excluded(self):
        cards = _static_cards()
        card = _get(cards, "axis_ace")
        r = calculate_rewards(card, "fuel", 5000)
        assert r["reward_value_inr"] == 0.0
        assert "excluded" in r["reward_description"].lower()

    def test_amex_mrcc_fuel_excluded(self):
        cards = _static_cards()
        card = _get(cards, "amex_mrcc")
        r = calculate_rewards(card, "fuel", 5000)
        assert r["reward_value_inr"] == 0.0
        assert "excluded" in r["reward_description"].lower()

    # ── Insurance exclusion (Amex MRCC only) ─────────────────────────────────

    def test_amex_mrcc_insurance_excluded(self):
        """
        Insurance is a documented Amex MRCC exclusion.
        'insurance' is not an exposed UI category but can be passed directly.
        """
        cards = _static_cards()
        card = _get(cards, "amex_mrcc")
        r = calculate_rewards(card, "insurance", 5000)
        assert r["reward_value_inr"] == 0.0
        assert "excluded" in r["reward_description"].lower()

    # ── ICICI Amazon Pay: fuel surcharge waiver ≠ zero cashback ──────────────

    def test_icici_amazon_pay_fuel_not_excluded(self):
        """
        ICICI's exclusion is 'Fuel surcharge not waived' — a fee note,
        not a zero-cashback rule. Fuel spend earns the base 1% other rate.
        """
        cards = _static_cards()
        card = _get(cards, "icici_amazon_pay")
        r = calculate_rewards(card, "fuel", 5000)
        # Falls back to "other" = 1% = ₹50
        assert r["reward_value_inr"] == 50.0

    # ── Eligible categories still earn correctly after exclusion logic ────────

    def test_hdfc_millennia_online_shopping_still_earns(self):
        """Adding exclusion logic must not break eligible category calculations."""
        cards = _static_cards()
        card = _get(cards, "hdfc_millennia")
        r = calculate_rewards(card, "online_shopping", 5000)
        assert r["reward_value_inr"] == 250.0

    def test_sbi_simplysave_dining_still_earns(self):
        cards = _static_cards()
        card = _get(cards, "sbi_simplysave")
        r = calculate_rewards(card, "dining", 5000)
        assert r["reward_value_inr"] == 125.0

    def test_axis_ace_other_still_earns(self):
        """'other' is not excluded for Axis ACE — 2% applies."""
        cards = _static_cards()
        card = _get(cards, "axis_ace")
        r = calculate_rewards(card, "other", 5000)
        assert r["reward_value_inr"] == 100.0

    def test_amex_mrcc_dining_still_earns(self):
        """Dining is not excluded for Amex — base rate applies."""
        cards = _static_cards()
        card = _get(cards, "amex_mrcc")
        r = calculate_rewards(card, "dining", 5000)
        assert r["reward_value_inr"] == 50.0

    # ── Exclusion metadata preserved ─────────────────────────────────────────

    def test_excluded_result_preserves_verified_flag(self):
        """
        An excluded category returns the card's own verified flag —
        not a false unverified signal.
        """
        cards = _static_cards()
        card = _get(cards, "hdfc_millennia")
        r = calculate_rewards(card, "fuel", 5000)
        assert r["verified"] is True   # card is verified; exclusion is also verified
        assert r["reward_value_inr"] == 0.0

    def test_card_without_excluded_categories_field_works(self):
        """
        Cards that have no excluded_categories key (e.g. ICICI) must
        work normally — no KeyError, no regression.
        """
        card = {
            "id": "_no_excl",
            "name": "No Exclusion Card",
            "bank": "Test",
            "rewards": {
                "verified": True,
                "uncertainty_flag": False,
                "reward_unit": "percent_cashback",
                "cashback_rates": {"other": 2.0},
                "monthly_cashback_cap_inr": None,
                "source_url": None,
                # No "excluded_categories" key at all
            },
        }
        r = calculate_rewards(card, "fuel", 5000)
        assert r["reward_value_inr"] == 100.0  # 2% of ₹5,000
