# 💳 CardWise — AI-Powered Credit Card Advisor for India

CardWise is a hackathon MVP that helps Indian consumers find the right credit card, compare rewards, and research live card terms — powered by TinyFish web search and Google Gemini.

---

## Features

### 🤖 AI Advisor
Fill in your profile (age, income, employment, credit score, spending habits) and get personalised card recommendations. Gemini explains which cards suit you and why, grounded in real card data.

### 🔍 Research Agent
Ask any question about a credit card in plain English. TinyFish searches official bank websites (HDFC, SBI, Axis, ICICI, Amex) and Gemini synthesises a structured answer with source URLs. Results are saved to a local cache so repeat queries load instantly.

### 📊 Rewards Comparison
Pick a spending category and amount to see which card earns the most. Calculations use only verified reward rates. Excluded categories (e.g. fuel) return ₹0 with a clear message. Estimated values are labelled as estimates.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | [Streamlit](https://streamlit.io) |
| LLM | Google Gemini via OpenAI-compatible API |
| Web Research | [TinyFish Search API](https://tinyfish.mintlify.app) |
| Data | JSON files (no database required) |
| Language | Python 3.11+ |

---

## Project Structure

```
CardWise/
├── app.py                    # Streamlit frontend — 3 tabs
├── src/
│   ├── advisor.py            # Eligibility filtering + LLM recommendations
│   ├── card_loader.py        # Card data loading, eligibility checks, reward calculations
│   ├── cache.py              # TinyFish result persistence + structured extraction
│   ├── llm_client.py         # Gemini wrapper (OpenAI-compatible)
│   └── research_agent.py     # TinyFish Search integration
├── data/
│   ├── cards.json            # Static card database (5 cards, hand-verified)
│   └── research_cache.json   # Live research results (auto-generated)
├── tests/
│   └── test_core.py          # 41 automated tests
├── .env.example              # API key template
└── requirements.txt
```

---

## Card Database

Five cards included at launch, with verified reward rates, eligibility criteria, fees, and exclusions:

| Card | Type | Annual Fee |
|---|---|---|
| HDFC Millennia | Cashback | ₹1,000 (waivable) |
| SBI SimplySAVE | Reward Points | ₹499 (waivable) |
| Axis Bank ACE | Cashback | ₹499 (waivable) |
| American Express MRCC | Membership Rewards Points | ₹4,500 (waivable) |
| Amazon Pay ICICI | Cashback | Lifetime free |

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Anya-ka/CardWise-.git
cd CardWise-
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure API keys

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
# Google Gemini (free tier — get key at aistudio.google.com/apikey)
LLM_API_KEY=your_gemini_api_key
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemini-3.5-flash-lite

# TinyFish Search API (free tier — get key at tinyfish.io)
TINYFISH_API_KEY=your_tinyfish_api_key
```

### 4. Run the app

```bash
.venv/bin/streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## API Keys

| Service | Free Tier | Get Key |
|---|---|---|
| Google Gemini | Yes — no credit card needed | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| TinyFish Search | Yes — 12,000 searches/day | [tinyfish.io](https://tinyfish.io) |

Neither key requires a credit card for the free tier.

---

## Running Tests

```bash
.venv/bin/python -m pytest tests/ -v
```

41 tests covering:
- Static reward calculations for all 5 cards
- Cache merge safety (null values never overwrite verified static data)
- Exclusion enforcement (fuel, insurance return ₹0 with clear messaging)
- Verification badge logic
- Source URL preservation
- Cache fallback behaviour

---

## Data Integrity

- **Reward rates** are sourced from official bank websites and PDFs, cited with source URLs in `cards.json`.
- **Excluded categories** (e.g. fuel for all cards, insurance for Amex) return ₹0 — not silently estimated.
- **Amex point values** are labelled as estimates (₹0.50/pt) since Amex does not publish a fixed rupee value per point.
- **TinyFish research results** are cached in `data/research_cache.json`. Cached data merges into the advisor and rewards comparison automatically. Use "Force refresh" in the Research tab to fetch updated data.
- `.env` is excluded from version control. Never commit API keys.

---

## Limitations

- **5 cards** in the static database at launch. More can be added to `data/cards.json` or researched via the Research Agent.
- **Reward exclusions** for ambiguous categories (e.g. `bill_payments` vs utilities) are documented but not enforced — the UI shows a disclaimer.
- **Amex point value** varies by redemption method. The ₹0.50/pt figure is an estimate for comparison purposes.
- **Approval is always at the bank's discretion.** CardWise provides general information only.

---

## Disclaimer

CardWise is a hackathon prototype. All reward rates and eligibility criteria should be verified directly with the respective bank before applying for any credit card. Approval is at the bank's sole discretion.
