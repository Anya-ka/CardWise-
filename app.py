"""
CardWise — AI-powered Credit Card Advisor for India
Hackathon demo | Streamlit frontend
"""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# ── Env setup ──────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env", override=True)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CardWise — AI Credit Card Advisor",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Palette tokens ───────────────────────────────────────────────────── */
    :root {
        --cw-navy:    #0f2344;
        --cw-teal:    #0d9488;
        --cw-surface: #f7f9fc;
        --cw-border:  #dde3ed;
    }

    /* ── Hero header ──────────────────────────────────────────────────────── */
    .cw-hero {
        background: linear-gradient(135deg, #0f2344 0%, #133060 55%, #0d4a6e 100%);
        border-radius: 14px;
        padding: 2rem 2.5rem;
        margin-bottom: 1.5rem;
        color: white;
    }
    .cw-hero h1 { font-size: 2.2rem; margin: 0 0 0.35rem 0; font-weight: 700; letter-spacing: -0.5px; }
    .cw-hero p  { font-size: 1rem; color: #c7d8f0; margin: 0; }

    /* ── Card tile ────────────────────────────────────────────────────────── */
    .card-tile {
        background: #f7f9fc;
        border: 1px solid #dde3ed;
        border-left: 3px solid #dde3ed;   /* default: neutral border */
        border-radius: 10px;
        padding: 0.85rem 1.1rem;
        margin-bottom: 0.75rem;
    }
    /* Teal left border = card has live researched data (not a verification claim) */
    .card-tile.has-research {
        border-left: 3px solid #0d9488;
    }
    .card-tile h4 { margin: 0 0 0.2rem 0; color: #0f2344; font-size: 1rem; }
    .card-tile p  { margin: 0; color: #4b5563; font-size: 0.88rem; line-height: 1.4; }

    /* ── Verification badges ──────────────────────────────────────────────── */
    .badge-teal {
        background: #ccfbf1; color: #0f766e;
        border-radius: 999px; padding: 2px 10px;
        font-size: 0.76rem; font-weight: 600;
    }
    .badge-yellow {
        background: #fef3c7; color: #92400e;
        border-radius: 999px; padding: 2px 10px;
        font-size: 0.76rem; font-weight: 600;
    }

    /* ── Disclaimer block ─────────────────────────────────────────────────── */
    .disclaimer {
        background: #fffbeb;
        border-left: 4px solid #f59e0b;
        border-radius: 0 8px 8px 0;
        padding: 0.65rem 1rem;
        font-size: 0.84rem;
        color: #78350f;
        margin-top: 1.1rem;
    }

    /* ── Hide Streamlit chrome for demo ───────────────────────────────────── */
    #MainMenu, footer { visibility: hidden; }

    /* ── Primary buttons — teal instead of Streamlit default red ─────────── */
    .stButton > button[kind="primaryFormSubmit"],
    .stButton > button[kind="primary"] {
        background-color: #0d9488 !important;
        border-color: #0d9488 !important;
        color: #ffffff !important;
    }
    .stButton > button[kind="primaryFormSubmit"]:hover,
    .stButton > button[kind="primary"]:hover {
        background-color: #0f766e !important;
        border-color: #0f766e !important;
        color: #ffffff !important;
    }
    .stButton > button[kind="primaryFormSubmit"]:active,
    .stButton > button[kind="primary"]:active {
        background-color: #115e59 !important;
        border-color: #115e59 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Hero header ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="cw-hero">
        <h1>💳 CardWise</h1>
        <p>AI-powered credit card advisor for India — find the right card for your life.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── API status sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")

    # Read env vars directly — avoids stale module-level cache
    _llm_key = os.getenv("LLM_API_KEY", "")
    _tf_key  = os.getenv("TINYFISH_API_KEY", "")

    llm_ready = bool(_llm_key) and _llm_key != "your_llm_api_key_here"
    tf_ready  = bool(_tf_key)  and _tf_key  != "your_tinyfish_api_key_here"

    llm_status = "🟢 Connected" if llm_ready else "🔴 Not configured"
    tf_status  = "🟢 Connected" if tf_ready  else "🔴 Not configured"

    st.markdown(f"**LLM API:** {llm_status}")
    st.markdown(f"**TinyFish:** {tf_status}")

    if not llm_ready or not tf_ready:
        st.info(
            "Copy `.env.example` → `.env` and fill in your API keys, "
            "then restart the app."
        )

    st.divider()
    st.caption("CardWise v0.1 — Hackathon demo")
    st.caption("Static card data included at launch.")
    st.caption("⚠️ Approval is at the bank's discretion.")

    # Show which cards have live research data
    st.divider()
    st.markdown("**🔬 Research Cache**")
    try:
        from src.cache import load_cache
        cache = load_cache()
        if cache:
            for cid, entry in cache.items():
                ts = entry.get("retrieved_at", "")[:10]
                st.caption(f"✅ {entry.get('card_name', cid)}")
                st.caption(f"   Researched: {ts}")
        else:
            st.caption("No cards researched yet.")
    except Exception:
        st.caption("Cache unavailable.")

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_advisor, tab_research, tab_compare = st.tabs(
    ["🤖 AI Advisor", "🔍 Research Agent", "📊 Rewards Comparison"]
)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — AI Advisor
# ══════════════════════════════════════════════════════════════════════════════
with tab_advisor:
    st.subheader("Tell us about yourself")
    st.caption(
        "The more details you share, the better we can match you. "
        "All fields are optional."
    )

    col1, col2 = st.columns(2)

    with col1:
        age = st.number_input("Your age", min_value=18, max_value=80, value=28, step=1)
        employment = st.selectbox(
            "Employment type",
            ["salaried", "self_employed", "student", "retired"],
            index=0,
        )
        income = st.number_input(
            "Monthly income (₹)",
            min_value=0,
            max_value=10_000_000,
            value=50_000,
            step=5_000,
            format="%d",
        )

    with col2:
        credit_score = st.slider(
            "Credit score (CIBIL / Experian)",
            min_value=300,
            max_value=900,
            value=720,
            step=10,
            help="Not sure? Leave at default. Score 750+ is generally good.",
        )
        fee_pref = st.selectbox(
            "Annual fee preference",
            [
                "Any — happy to pay for premium benefits",
                "Low (under ₹1,000/year)",
                "Lifetime free only",
            ],
        )
        credit_history = st.selectbox(
            "Credit history",
            ["No credit history (new to credit)", "Less than 1 year", "1–3 years", "3+ years"],
        )

    st.markdown("**Your top spending categories** (select all that apply)")
    spend_cols = st.columns(4)
    categories = [
        "Online shopping", "Dining", "Grocery", "Travel",
        "Fuel", "Movies", "Bill payments", "International",
    ]
    selected_categories = []
    for i, cat in enumerate(categories):
        with spend_cols[i % 4]:
            if st.checkbox(cat, key=f"cat_{i}"):
                selected_categories.append(cat)

    get_advice = st.button("✨ Get Personalised Advice", type="primary", use_container_width=True)

    if get_advice:
        profile = {
            "age": age,
            "employment_type": employment,
            "monthly_income_inr": income,
            "credit_score": credit_score,
            "fee_preference": fee_pref,
            "credit_history": credit_history,
            "spending_categories": selected_categories,
        }

        with st.spinner("Analysing your profile…"):
            from src.advisor import get_recommendations
            result = get_recommendations(profile)

        st.divider()

        # Show matched cards
        eligible = result["eligible_cards"]
        if eligible:
            st.success(f"Found **{len(eligible)} eligible card(s)** for your profile.")
            with st.expander("View matched cards", expanded=False):
                for card in eligible:
                    fee = card["annual_fee_inr"]
                    fee_str = "Lifetime free" if fee == 0 else f"₹{fee:,}/year"
                    has_research = bool(card.get("cache_retrieved_at"))
                    tile_class = "card-tile has-research" if has_research else "card-tile"
                    research_label = " &nbsp;<span style='color:#0d9488;font-size:0.78rem;font-weight:600'>🔬 Live data</span>" if has_research else ""
                    st.markdown(
                        f"""<div class="{tile_class}">
                        <h4>{card['name']}{research_label}</h4>
                        <p>{card['bank']} · {fee_str} · {card['card_type'].replace('_', ' ').title()}</p>
                        </div>""",
                        unsafe_allow_html=True,
                    )
        else:
            st.warning("No cards matched your eligibility criteria.")

        # LLM recommendation
        st.markdown("### 🤖 AI Recommendation")
        st.markdown(result["llm_response"])

        st.markdown(
            '<div class="disclaimer">⚠️ CardWise provides general information only. '
            'Approval is at the bank\'s sole discretion. Verify terms at the bank\'s official website '
            'before applying.</div>',
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Research Agent
# ══════════════════════════════════════════════════════════════════════════════
with tab_research:
    st.subheader("Live Research from Official Sources")
    st.caption(
        "TinyFish searches official bank websites to extract up-to-date "
        "eligibility criteria, fees, rewards and exclusions — with source URLs."
    )

    research_query = st.text_area(
        "What would you like to research?",
        placeholder=(
            "e.g. 'What are the eligibility criteria and reward rates for HDFC Regalia Credit Card?'\n"
            "or 'Compare SBI SimplySAVE and Axis ACE annual fees and cashback rates.'"
        ),
        height=100,
    )

    force_refresh = st.checkbox("🔄 Force refresh (ignore cache, fetch latest from web)", value=False)

    research_btn = st.button("🔍 Research Now", type="primary", use_container_width=True)

    if research_btn:
        if not research_query.strip():
            st.warning("Please enter a research query.")
        else:
            from src.research_agent import research_card

            # Check cache before showing the "searching" banner
            from src.cache import get_cached_entry
            from src.research_agent import _detect_card_id
            _cid, _ = _detect_card_id(research_query.strip())
            _cached = get_cached_entry(_cid) if (not _cid.startswith("research__") and not force_refresh) else None

            if _cached:
                st.info("⚡ **Loading from research cache…**")
            else:
                st.info("⏳ **Searching official bank sources with TinyFish…** (~20 seconds)")

            status_box = st.empty()
            log: list[str] = []

            def update_progress(msg: str):
                log.append(msg)
                status_box.markdown(
                    "\n".join(f"- {m}" for m in log[-5:])
                )

            with st.spinner("Researching…"):
                result = research_card(research_query.strip(), progress_callback=update_progress, force_refresh=force_refresh)

            status_box.empty()
            st.divider()

            if result["success"]:
                # Show save confirmation or cache hit
                if result.get("from_cache"):
                    st.success(
                        f"⚡ Loaded from cache · **{result['card_name']}** · "
                        f"Retrieved: {result['retrieved_at'][:19].replace('T', ' ')} UTC"
                    )
                elif result.get("retrieved_at"):
                    st.success(
                        f"✅ Research saved to database. "
                        f"Card: **{result['card_name']}** · "
                        f"Retrieved: {result['retrieved_at'][:19].replace('T', ' ')} UTC"
                    )

                st.markdown("### Research Results")
                st.markdown(result["answer"])

                if result["sources"]:
                    st.markdown("#### 📎 Sources")
                    for src in result["sources"]:
                        url = src.get("url", "")
                        title = src.get("title", url)
                        if url:
                            st.markdown(f"- [{title}]({url})")
                        else:
                            st.markdown(f"- {title}")

                if result.get("retrieved_at"):
                    st.info(
                        "💡 This card's data has been updated in the database. "
                        "Go to **🤖 AI Advisor** or **📊 Rewards Comparison** to see it reflected."
                    )
            else:
                st.error(result["answer"])

    # Show example queries for demo
    with st.expander("💡 Example research queries"):
        st.markdown(
            """
- *What are the exact reward rates for Amazon Pay ICICI Credit Card in 2024?*
- *What is the minimum income required for HDFC Regalia Credit Card?*
- *Compare Axis Magnus and HDFC Infinia reward rates for travel spending.*
- *What are the lounge access benefits of SBI Elite Credit Card?*
- *Is there a fuel surcharge waiver on Axis Bank ACE credit card?*
"""
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Rewards Comparison
# ══════════════════════════════════════════════════════════════════════════════
with tab_compare:
    st.subheader("Compare Rewards Across Your Cards")
    st.caption(
        "Enter a spending category and amount to see which card earns the most. "
        "Only verified reward rates are used."
    )

    col_a, col_b = st.columns(2)
    with col_a:
        compare_category = st.selectbox(
            "Spending category",
            [
                "online_shopping",
                "dining",
                "grocery",
                "bill_payments",
                "travel",
                "fuel",
                "movies",
                "other",
            ],
            format_func=lambda x: x.replace("_", " ").title(),
        )
    with col_b:
        compare_amount = st.number_input(
            "Amount to spend (₹)",
            min_value=100,
            max_value=1_000_000,
            value=5_000,
            step=500,
            format="%d",
        )

    compare_btn = st.button("📊 Compare Rewards", type="primary", use_container_width=True)

    if compare_btn:
        from src.card_loader import load_cards, calculate_rewards

        cards = load_cards()
        results = [calculate_rewards(c, compare_category, float(compare_amount)) for c in cards]
        # Sort by reward value descending
        results.sort(key=lambda r: r["reward_value_inr"], reverse=True)

        st.divider()
        st.markdown(
            f"### Rewards on ₹{compare_amount:,} spent on **{compare_category.replace('_', ' ').title()}**"
        )

        for rank, r in enumerate(results, 1):
            verified_badge = (
                '<span class="badge-teal">✓ Verified</span>'
                if r["verified"] and not r["uncertainty_flag"]
                else '<span class="badge-yellow">⚠ Unverified</span>'
            )
            medal = ["🥇", "🥈", "🥉"][rank - 1] if rank <= 3 else f"{rank}."

            # Look up if this card has live research data (for the teal border)
            card_obj = next((c for c in cards if c["id"] == r["card_id"]), {})
            tile_class = "card-tile has-research" if card_obj.get("cache_retrieved_at") else "card-tile"

            with st.container():
                st.markdown(
                    f"""<div class="{tile_class}">
                    <h4>{medal} {r['card_name']} &nbsp; {verified_badge}</h4>
                    <p><strong>Estimated reward:</strong> ₹{r['reward_value_inr']:,.2f} — {r['reward_description']}</p>
                    </div>""",
                    unsafe_allow_html=True,
                )
                if r["source_url"]:
                    st.caption(f"Source: [{r['source_url']}]({r['source_url']})")
                # MR points note — only for Amex MRCC
                if r["card_id"] == "amex_mrcc":
                    st.caption(
                        "ℹ️ Estimated reward value: 1 MR point per ₹50 spent = 100 pts on ₹5,000 "
                        "@ ₹0.50/pt (estimate only — actual value varies by redemption method). "
                        "Fuel, insurance, utilities, cash and EMI transactions earn no MR points; "
                        "monthly milestone bonus not included in this calculation."
                    )

        st.markdown(
            '<div class="disclaimer">⚠️ Reward calculations are estimates based on published rates. '
            'Actual rewards may vary based on merchant category codes, card variant, and bank policies. '
            'Always verify at the bank\'s official website.</div>',
            unsafe_allow_html=True,
        )
