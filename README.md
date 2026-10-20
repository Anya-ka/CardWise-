# CardWise — AI-Powered Credit Card Intelligence

**Research smarter. Compare better. Maximize every reward.**

CardWise is an AI-powered credit card advisor and rewards optimization platform that helps users discover suitable credit cards, research card terms, and compare potential rewards in one place.

At its core, CardWise combines **TinyFish for automated web research** with **Google Gemini for information extraction and analysis**, transforming information scattered across bank websites into structured, actionable insights.

---

## Demo

**Video Demo:** Coming Soon

[Watch the CardWise Demo](YOUR_VIDEO_LINK_HERE)

---

## Features

### 🤖 AI-Powered Card Advisor

Get personalized credit card recommendations based on your profile, eligibility, spending patterns, and preferences.

- Matches user requirements with available card data.
- Explains why a card may be suitable.
- Helps users compare fees, benefits, and eligibility criteria.
- Highlights cards enriched with live TinyFish research data.

### 🔍 TinyFish Research Agent

**The research engine behind CardWise.**

Credit card information is spread across issuer websites, product pages, fee schedules, and reward program documentation. Manually comparing these sources is time-consuming and error-prone.

CardWise uses **[TinyFish](https://tinyfish.io/)** to automate web research and gather relevant information from official card issuer websites.

**The research workflow:**

1. **Query understanding** — Accepts natural-language questions about credit cards, fees, rewards, eligibility, and benefits.
2. **Automated web search** — TinyFish searches official bank and financial sources, tagging each result as official, aggregator, or third-party.
3. **Full-page fetch** — TinyFish fetches the top official source pages for richer content than search snippets alone.
4. **Information extraction** — Google Gemini interprets the collected information and organizes it into a structured response with typed fields.
5. **Source traceability** — Relevant source URLs are retained so users can verify information directly.
6. **Research caching** — Retrieved results are cached locally and reused to reduce unnecessary repeat requests. A force-refresh option fetches updated data.

### 📊 Rewards Comparison and Optimization

Compare potential rewards across supported credit cards for different purchase amounts and spending categories.

- Compare eligible cards using available, verified reward rates.
- Estimate cashback and reward-point earnings.
- Apply supported exclusions (e.g. fuel, insurance) and reward rules.
- Distinguish estimated benefits from verified card terms.
- Merchant-restricted rates (e.g. HDFC Millennia 5% on named partners only) are clearly labelled **✓ Selected merchants** rather than a plain verified tick.
- Reward calculations use structured card data and defined rules — not AI-generated answers.

---

## How It Works

```text
        User Query / Spending Profile
                    |
                    v
             CardWise Interface
                    |
          +---------+---------+
          |                   |
          v                   v
     TinyFish             Card Database
    Web Research          Structured Data
          |
          v
   Official Web Sources
          |
          v
     Google Gemini
  Extraction & Analysis
          |
          v
   Structured Card Insights
          |
          v
    +-----+------+
    |            |
    v            v
 AI Advisor   Rewards Engine
    |            |
    +-----+------+
          |
          v
 Recommendations & Comparisons
    with Supporting Source Links
```

### Why TinyFish?

Traditional comparison platforms rely on manually maintained information, while general-purpose chatbots may produce answers that are hard to verify.

TinyFish automates the web research process by gathering information from relevant sources. Gemini interprets and structures the findings, while CardWise's rewards engine performs calculations using defined rules. This separation of responsibilities makes the platform easier to extend as additional cards and issuers are added.

---

## Tech Stack

| Component | Technology |
|---|---|
| Frontend | [Streamlit](https://streamlit.io/) |
| Web Research | [TinyFish](https://tinyfish.io/) |
| LLM and Information Extraction | [Google Gemini](https://ai.google.dev/) |
| Backend | Python 3.11+ |
| Card Data | JSON |
| Research Cache | Local JSON files |
| Testing | pytest |

---

## Project Structure

```text
CardWise/
├── app.py                    # Streamlit application (3 tabs)
├── src/
│   ├── advisor.py            # Personalized recommendations
│   ├── card_loader.py        # Card data, eligibility checks, reward calculations
│   ├── cache.py              # Research caching, structured extraction, evidence summary
│   ├── llm_client.py         # Gemini API integration
│   └── research_agent.py     # TinyFish Search + Fetch integration
├── data/
│   ├── cards.json            # Static card database (5 cards, hand-verified)
│   └── research_cache.json   # Generated research cache (auto-created)
├── tests/
│   └── test_core.py          # Automated tests (66 tests)
├── .env.example              # Environment variable template
├── requirements.txt          # Python dependencies
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11 or later
- Google Gemini API key (free tier, no credit card required)
- TinyFish API key (free tier, 12,000 searches/day)

### 1. Clone the Repository

```bash
git clone https://github.com/Anya-ka/CardWise-.git
cd CardWise-
```

### 2. Create a Virtual Environment

```bash
python3 -m venv .venv
```

Activate it:

**macOS / Linux**

```bash
source .venv/bin/activate
```

**Windows**

```powershell
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` and add your API credentials:

```dotenv
LLM_API_KEY=your_gemini_api_key
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemini-3.5-flash-lite

TINYFISH_API_KEY=your_tinyfish_api_key
```

Get your credentials from:

- **Google Gemini** (free) → [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- **TinyFish** (free) → [tinyfish.io](https://tinyfish.io/)

> **Security:** Never commit `.env` or expose API keys in source code, screenshots, logs, or public repositories. The `.env` file is already excluded by `.gitignore`.

### 5. Run CardWise

```bash
.venv/bin/streamlit run app.py
```

Open the URL shown in your terminal — usually `http://localhost:8501`.

---

## Testing

```bash
.venv/bin/python -m pytest tests/ -v
```

The test suite contains **66 tests** covering:

- Reward calculations for all 5 supported cards.
- Safe merging of cached research with existing static card data.
- Null-safety: cached null values never overwrite verified static values.
- Enforcement of documented reward exclusions (fuel, insurance, etc.).
- Verification label logic: `✓ Verified`, `✓ Selected merchants`, `⚠ Unverified`.
- Source URL preservation through cache merge.
- Evidence summary generation and source quality classification.
- TinyFish pipeline source tagging (official / aggregator / third-party).
- Cache fallback behaviour for unresearched cards.

---

## Data Integrity and Transparency

CardWise is designed to distinguish researched information, static data, and calculated estimates.

| Signal | Meaning |
|---|---|
| ✓ Verified | Rate confirmed from a verified static source; applies to all eligible transactions |
| ✓ Selected merchants | Rate confirmed, but only applies to named partner merchants |
| ⚠ Unverified | Rate data is uncertain or not confirmed from an official source |
| 🔬 Live data | Card data has been enriched with live TinyFish research |
| ℹ️ Estimate | Value depends on assumptions (e.g. Amex point redemption value) |

Additional notes:

- **Source traceability** — Research responses retain source URLs tagged as official, aggregator, or third-party.
- **Safe data merging** — Missing or null cached values never overwrite existing verified static values.
- **Reward calculations** — Performed by deterministic Python logic using structured card data, not by the LLM.
- **Research caching** — Results are reused for efficiency, but cached information may become outdated. Use force-refresh to fetch fresh data.
- **Independent verification** — Important terms should always be confirmed against the issuer's latest official documentation.

---

## Card Database

Five cards included at launch, hand-verified from official sources:

| Card | Type | Annual Fee | Source |
|---|---|---|---|
| HDFC Millennia | Cashback | ₹1,000 (waivable) | HDFC Bank MITC PDF |
| SBI SimplySAVE | Reward Points | ₹499 (waivable) | sbicard.com |
| Axis Bank ACE | Cashback | ₹499 (waivable) | axisbank.com |
| American Express MRCC | Membership Rewards | ₹4,500 (waivable) | americanexpress.com/in |
| Amazon Pay ICICI | Cashback | Lifetime free | icicibank.com |

---

## Limitations

- The static database contains a limited selection of credit cards.
- Research coverage depends on the availability and accessibility of web sources.
- Reward rules, fees, exclusions, and promotional terms change over time.
- Some issuer-specific conditions may not be fully modelled.
- Cached research may need refreshing when source information changes.
- Recommendations depend on the completeness and accuracy of available data.
- Approval is always at the bank's sole discretion — CardWise never guarantees approval.

---

## Roadmap

- [ ] Expand supported card issuers and card coverage.
- [ ] Improve extraction of fees, reward caps, exclusions, and eligibility conditions.
- [ ] Add freshness indicators and automatic staleness detection for cached research.
- [ ] Improve conflicting-information handling across sources.
- [ ] Support more advanced spending scenarios and reward optimization.
- [ ] Enhance recommendation explanations and comparison reports.
- [ ] Explore persistent user profiles and spending summaries.

---

## Disclaimer

CardWise is an informational prototype and does not guarantee credit card approval, reward eligibility, or specific financial outcomes. Recommendations and reward calculations are estimates based on available data and supported rules. Users should verify current fees, terms, conditions, and eligibility requirements with the relevant card issuer before making financial decisions.

---

**CardWise — From scattered information to smarter spending.**
