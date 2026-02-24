import streamlit as st
import yfinance as yf
import anthropic
import requests
import json
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Evaluator AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(90deg, #1a73e8, #0d47a1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #666;
        margin-bottom: 2rem;
        font-size: 1rem;
    }
    .rating-excellent { background:#d4edda; color:#155724; border-radius:6px; padding:4px 10px; font-weight:700; display:inline-block; }
    .rating-good      { background:#cce5ff; color:#004085; border-radius:6px; padding:4px 10px; font-weight:700; display:inline-block; }
    .rating-neutral   { background:#fff3cd; color:#856404; border-radius:6px; padding:4px 10px; font-weight:700; display:inline-block; }
    .rating-bad       { background:#f8d7da; color:#721c24; border-radius:6px; padding:4px 10px; font-weight:700; display:inline-block; }
    .metric-card { background:#f8f9fa; border-radius:10px; padding:1rem 1.2rem; border-left:4px solid #1a73e8; margin-bottom:1rem; }
    .section-divider { border-top: 2px solid #e0e0e0; margin: 2rem 0; }
    .news-card { background:#f8f9fa; border-radius:8px; padding:1rem; margin-bottom:0.8rem; border-left:3px solid #1a73e8; }
    .dividend-highlight { background: linear-gradient(135deg, #e8f5e9, #c8e6c9); border-radius:10px; padding:1.2rem; border:1px solid #81c784; }
    .price-target-card { background:#fff; border:1px solid #e0e0e0; border-radius:10px; padding:1rem; text-align:center; }
    .price-up { color: #2e7d32; font-weight: 700; }
    .price-down { color: #c62828; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-header">📈 Stock Evaluator AI</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Earnings analysis · Price targets · News · Dividends — powered by Claude AI</p>', unsafe_allow_html=True)

# ── API Key inputs ─────────────────────────────────────────────────────────────
with st.expander("⚙️ API Keys (required — stored only for this session)", expanded=not os.getenv("ANTHROPIC_API_KEY")):
    col1, col2 = st.columns(2)
    with col1:
        anthropic_key = st.text_input("Anthropic API Key", value=os.getenv("ANTHROPIC_API_KEY",""), type="password", help="Get at console.anthropic.com")
    with col2:
        news_key = st.text_input("News API Key", value=os.getenv("NEWS_API_KEY",""), type="password", help="Get at newsapi.org (free)")

# ── Ticker input ──────────────────────────────────────────────────────────────
st.markdown("### Enter a Stock Ticker")
col_input, col_btn = st.columns([3, 1])
with col_input:
    ticker_input = st.text_input("", placeholder="e.g. AAPL, MSFT, NVDA, TSLA", label_visibility="collapsed")
with col_btn:
    analyze_btn = st.button("🔍 Analyze", use_container_width=True, type="primary")


# ── Helper functions ──────────────────────────────────────────────────────────

def get_stock_data(ticker: str):
    stock = yf.Ticker(ticker)
    info = stock.info
    financials = stock.financials
    quarterly_financials = stock.quarterly_financials
    income_stmt = stock.income_stmt
    quarterly_income = stock.quarterly_income_stmt
    cashflow = stock.cashflow
    quarterly_cashflow = stock.quarterly_cashflow
    balance_sheet = stock.balance_sheet
    earnings_dates = stock.earnings_dates
    history = stock.history(period="1y")
    calendar = stock.calendar
    return {
        "info": info,
        "financials": financials,
        "quarterly_financials": quarterly_financials,
        "income_stmt": income_stmt,
        "quarterly_income": quarterly_income,
        "cashflow": cashflow,
        "quarterly_cashflow": quarterly_cashflow,
        "balance_sheet": balance_sheet,
        "earnings_dates": earnings_dates,
        "history": history,
        "calendar": calendar,
    }


def safe_val(val):
    """Convert pandas / numpy types to plain Python for JSON."""
    try:
        if val is None:
            return None
        if hasattr(val, 'item'):
            return val.item()
        if hasattr(val, 'isoformat'):
            return val.isoformat()
        return val
    except Exception:
        return str(val)


def df_to_dict(df, rows=4):
    """Convert a DataFrame to a serialisable dict."""
    if df is None or df.empty:
        return {}
    try:
        subset = df.iloc[:, :rows]
        result = {}
        for col in subset.columns:
            col_key = str(col)[:20]
            result[col_key] = {str(idx): safe_val(v) for idx, v in subset[col].items()}
        return result
    except Exception:
        return {}


def build_context(data: dict, ticker: str) -> str:
    info = data["info"]
    context_parts = [
        f"STOCK: {ticker.upper()} — {info.get('longName', ticker)}",
        f"Sector: {info.get('sector','N/A')} | Industry: {info.get('industry','N/A')}",
        f"Current Price: ${info.get('currentPrice', info.get('regularMarketPrice','N/A'))}",
        f"52-Week Range: ${info.get('fiftyTwoWeekLow','N/A')} – ${info.get('fiftyTwoWeekHigh','N/A')}",
        f"Market Cap: ${info.get('marketCap','N/A'):,}" if isinstance(info.get('marketCap'), int) else f"Market Cap: {info.get('marketCap','N/A')}",
        f"P/E (TTM): {info.get('trailingPE','N/A')} | Forward P/E: {info.get('forwardPE','N/A')}",
        f"EPS (TTM): {info.get('trailingEps','N/A')} | Forward EPS: {info.get('forwardEps','N/A')}",
        f"Revenue (TTM): {info.get('totalRevenue','N/A')}",
        f"Gross Margins: {info.get('grossMargins','N/A')} | Operating Margins: {info.get('operatingMargins','N/A')} | Profit Margins: {info.get('profitMargins','N/A')}",
        f"Revenue Growth (YoY): {info.get('revenueGrowth','N/A')} | Earnings Growth: {info.get('earningsGrowth','N/A')}",
        f"Beta: {info.get('beta','N/A')}",
        f"Dividend Rate: {info.get('dividendRate','N/A')} | Dividend Yield: {info.get('dividendYield','N/A')}",
        f"Ex-Dividend Date: {info.get('exDividendDate','N/A')}",
        f"Payout Ratio: {info.get('payoutRatio','N/A')}",
        f"Analyst Target Price: {info.get('targetMeanPrice','N/A')} (Low: {info.get('targetLowPrice','N/A')}, High: {info.get('targetHighPrice','N/A')})",
        f"Recommendation: {info.get('recommendationKey','N/A')}",
        f"Number of Analyst Opinions: {info.get('numberOfAnalystOpinions','N/A')}",
        f"Return on Equity: {info.get('returnOnEquity','N/A')} | Return on Assets: {info.get('returnOnAssets','N/A')}",
        f"Debt to Equity: {info.get('debtToEquity','N/A')}",
        f"Free Cash Flow: {info.get('freeCashflow','N/A')}",
        f"Total Cash: {info.get('totalCash','N/A')} | Total Debt: {info.get('totalDebt','N/A')}",
        f"Short Ratio: {info.get('shortRatio','N/A')} | Short % of Float: {info.get('shortPercentOfFloat','N/A')}",
        "\n--- QUARTERLY FINANCIALS (recent) ---",
        json.dumps(df_to_dict(data["quarterly_financials"]), indent=2),
        "\n--- QUARTERLY INCOME STATEMENT ---",
        json.dumps(df_to_dict(data["quarterly_income"]), indent=2),
        "\n--- CASHFLOW (annual, recent) ---",
        json.dumps(df_to_dict(data["cashflow"]), indent=2),
    ]
    return "\n".join(str(p) for p in context_parts)


def get_news(ticker: str, company_name: str, api_key: str):
    if not api_key:
        return []
    try:
        url = (
            f"https://newsapi.org/v2/everything?"
            f"q={company_name}&sortBy=publishedAt&pageSize=10&language=en&apiKey={api_key}"
        )
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json().get("articles", [])
    except Exception:
        pass
    return []


def ask_claude(client, system_prompt: str, user_prompt: str) -> str:
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )
    return message.content[0].text


def display_rating(label: str, rating: str, commentary: str = ""):
    rating_lower = rating.lower()
    cls = "rating-excellent" if "excellent" in rating_lower else \
          "rating-good"      if "good"      in rating_lower else \
          "rating-bad"       if "bad"        in rating_lower else \
          "rating-neutral"
    commentary_html = f"<br><small style='color:#555'>{commentary}</small>" if commentary else ""
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;margin-bottom:8px'>"
        f"<span style='min-width:220px;font-weight:600'>{label}</span>"
        f"<span class='{cls}'>{rating}</span>{commentary_html}</div>",
        unsafe_allow_html=True,
    )


# ── Main analysis ─────────────────────────────────────────────────────────────

if analyze_btn and ticker_input:
    ticker = ticker_input.strip().upper()

    if not anthropic_key:
        st.error("Please enter your Anthropic API key above.")
        st.stop()

    client = anthropic.Anthropic(api_key=anthropic_key)

    with st.spinner(f"Fetching data for {ticker}…"):
        try:
            data = get_stock_data(ticker)
        except Exception as e:
            st.error(f"Could not fetch data for {ticker}. Check the ticker symbol. Error: {e}")
            st.stop()

    info = data["info"]
    company_name = info.get("longName", ticker)
    current_price = info.get("currentPrice", info.get("regularMarketPrice", "N/A"))

    st.markdown(f"## {company_name} ({ticker})")
    st.markdown(f"**Current Price:** ${current_price} &nbsp;|&nbsp; **Sector:** {info.get('sector','N/A')} &nbsp;|&nbsp; **Industry:** {info.get('industry','N/A')}", unsafe_allow_html=True)
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    context = build_context(data, ticker)
    tabs = st.tabs(["📊 Earnings Analysis", "💡 Insights & Price Targets", "📰 Stock in the News", "💰 Dividends"])

    # ── Tab 1: Earnings Analysis ──────────────────────────────────────────────
    with tabs[0]:
        st.markdown("### Earnings Report Scorecard")
        with st.spinner("Running earnings analysis with Claude AI…"):
            earnings_prompt = f"""
You are a professional equity analyst. Based on the following financial data for {ticker} ({company_name}), 
provide a structured earnings report evaluation.

{context}

Respond ONLY with a valid JSON object (no markdown fences) with this exact structure:
{{
  "overall_rating": "Excellent|Good|Neutral|Bad",
  "overall_summary": "2-3 sentence overall assessment",
  "categories": [
    {{
      "name": "Revenue Growth",
      "rating": "Excellent|Good|Neutral|Bad",
      "commentary": "one sentence explanation"
    }},
    {{
      "name": "Profitability & Margins",
      "rating": "Excellent|Good|Neutral|Bad",
      "commentary": "one sentence explanation"
    }},
    {{
      "name": "Earnings Per Share (EPS)",
      "rating": "Excellent|Good|Neutral|Bad",
      "commentary": "one sentence explanation"
    }},
    {{
      "name": "Cash Flow Generation",
      "rating": "Excellent|Good|Neutral|Bad",
      "commentary": "one sentence explanation"
    }},
    {{
      "name": "Balance Sheet Health",
      "rating": "Excellent|Good|Neutral|Bad",
      "commentary": "one sentence explanation"
    }},
    {{
      "name": "Valuation",
      "rating": "Excellent|Good|Neutral|Bad",
      "commentary": "one sentence explanation"
    }},
    {{
      "name": "Analyst Sentiment",
      "rating": "Excellent|Good|Neutral|Bad",
      "commentary": "one sentence explanation"
    }},
    {{
      "name": "Revenue vs Expectations",
      "rating": "Excellent|Good|Neutral|Bad",
      "commentary": "one sentence explanation"
    }},
    {{
      "name": "Cost Management",
      "rating": "Excellent|Good|Neutral|Bad",
      "commentary": "one sentence explanation"
    }},
    {{
      "name": "Return on Capital",
      "rating": "Excellent|Good|Neutral|Bad",
      "commentary": "one sentence explanation"
    }}
  ]
}}
"""
            try:
                raw = ask_claude(client, "You are a financial analyst. Return only valid JSON, no markdown.", earnings_prompt)
                # strip potential markdown fences
                raw = raw.strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                earnings_data = json.loads(raw)

                overall = earnings_data.get("overall_rating", "Neutral")
                overall_cls = "rating-excellent" if "excellent" in overall.lower() else \
                              "rating-good"      if "good"      in overall.lower() else \
                              "rating-bad"       if "bad"       in overall.lower() else "rating-neutral"

                st.markdown(
                    f"<div class='metric-card'><strong>Overall Earnings Rating:</strong> "
                    f"<span class='{overall_cls}'>{overall}</span><br>"
                    f"<span style='color:#444'>{earnings_data.get('overall_summary','')}</span></div>",
                    unsafe_allow_html=True,
                )
                st.markdown("#### Category Breakdown")
                for cat in earnings_data.get("categories", []):
                    display_rating(cat["name"], cat["rating"], cat.get("commentary",""))

            except Exception as e:
                st.error(f"Could not parse earnings analysis: {e}")
                st.text(raw[:500] if 'raw' in locals() else "No response")

    # ── Tab 2: Insights & Price Targets ───────────────────────────────────────
    with tabs[1]:
        st.markdown("### AI Insights & Price Targets")
        with st.spinner("Generating insights and price targets…"):
            insights_prompt = f"""
You are a senior equity analyst with 20 years of experience.

Here is the financial data for {ticker} ({company_name}):

{context}

Current price: ${current_price}

Respond ONLY with a valid JSON object (no markdown fences):
{{
  "what_doing_well": ["point 1", "point 2", "point 3", "point 4"],
  "risks_concerns": ["risk 1", "risk 2", "risk 3"],
  "overall_outlook": "Bullish|Cautiously Bullish|Neutral|Cautiously Bearish|Bearish",
  "outlook_rationale": "3-4 sentence explanation of your outlook",
  "price_targets": {{
    "next_day":     {{"target": 0.0, "direction": "Up|Down|Flat", "rationale": "brief reason"}},
    "next_week":    {{"target": 0.0, "direction": "Up|Down|Flat", "rationale": "brief reason"}},
    "next_month":   {{"target": 0.0, "direction": "Up|Down|Flat", "rationale": "brief reason"}},
    "next_quarter": {{"target": 0.0, "direction": "Up|Down|Flat", "rationale": "brief reason"}},
    "next_year":    {{"target": 0.0, "direction": "Up|Down|Flat", "rationale": "brief reason"}}
  }},
  "buy_sell_hold": "Buy|Sell|Hold",
  "conviction": "High|Medium|Low"
}}
"""
            try:
                raw2 = ask_claude(client, "You are a financial analyst. Return only valid JSON, no markdown.", insights_prompt)
                raw2 = raw2.strip()
                if raw2.startswith("```"):
                    raw2 = raw2.split("```")[1]
                    if raw2.startswith("json"):
                        raw2 = raw2[4:]
                insights_data = json.loads(raw2)

                # Outlook
                outlook = insights_data.get("overall_outlook","Neutral")
                bsh = insights_data.get("buy_sell_hold","Hold")
                conviction = insights_data.get("conviction","Medium")
                bsh_color = "#2e7d32" if bsh=="Buy" else "#c62828" if bsh=="Sell" else "#f57c00"

                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Outlook", outlook)
                col_b.metric("Recommendation", bsh)
                col_c.metric("Conviction", conviction)

                st.markdown(f"<div class='metric-card'>{insights_data.get('outlook_rationale','')}</div>", unsafe_allow_html=True)

                col_left, col_right = st.columns(2)
                with col_left:
                    st.markdown("#### ✅ What the Company is Doing Well")
                    for pt in insights_data.get("what_doing_well", []):
                        st.markdown(f"• {pt}")

                with col_right:
                    st.markdown("#### ⚠️ Risks & Concerns")
                    for pt in insights_data.get("risks_concerns", []):
                        st.markdown(f"• {pt}")

                st.markdown("#### 🎯 Price Targets")
                pt_data = insights_data.get("price_targets", {})
                periods = [
                    ("next_day", "Next Day"),
                    ("next_week", "Next Week"),
                    ("next_month", "Next Month"),
                    ("next_quarter", "Next Quarter"),
                    ("next_year", "Next Year"),
                ]
                pt_cols = st.columns(5)
                for i, (key, label) in enumerate(periods):
                    pt = pt_data.get(key, {})
                    target = pt.get("target", 0)
                    direction = pt.get("direction", "Flat")
                    rationale = pt.get("rationale", "")
                    arrow = "▲" if direction == "Up" else "▼" if direction == "Down" else "→"
                    color_cls = "price-up" if direction == "Up" else "price-down" if direction == "Down" else ""
                    try:
                        pct = ((float(target) - float(current_price)) / float(current_price)) * 100
                        pct_str = f"{pct:+.1f}%"
                    except Exception:
                        pct_str = ""
                    with pt_cols[i]:
                        st.markdown(
                            f"<div class='price-target-card'>"
                            f"<div style='font-size:0.8rem;color:#666;margin-bottom:4px'>{label}</div>"
                            f"<div style='font-size:1.4rem;font-weight:800'>${target:.2f}</div>"
                            f"<div class='{color_cls}' style='font-size:1rem'>{arrow} {pct_str}</div>"
                            f"<div style='font-size:0.7rem;color:#888;margin-top:6px'>{rationale}</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                st.caption("⚠️ Price targets are AI-generated estimates for informational purposes only and are not financial advice.")

            except Exception as e:
                st.error(f"Could not parse insights: {e}")
                st.text(raw2[:500] if 'raw2' in locals() else "No response")

    # ── Tab 3: Stock in the News ───────────────────────────────────────────────
    with tabs[2]:
        st.markdown("### Stock in the News")
        articles = get_news(ticker, company_name, news_key)

        if articles:
            with st.spinner("Analyzing news with Claude AI…"):
                headlines = "\n".join([f"- {a['title']} ({a.get('source',{}).get('name','')})" for a in articles[:10]])
                news_prompt = f"""
You are a financial analyst. Here are recent news headlines for {ticker} ({company_name}):

{headlines}

Also here is the company's financial context:
{context[:2000]}

Respond ONLY with a valid JSON object (no markdown fences):
{{
  "exciting_things": ["thing 1", "thing 2", "thing 3"],
  "caution_flags": ["flag 1", "flag 2", "flag 3"],
  "upcoming_earnings_estimate": {{
    "date_estimate": "approximate date or quarter",
    "eps_estimate": "your EPS estimate with rationale",
    "revenue_estimate": "your revenue estimate",
    "beat_miss_prediction": "Beat|Meet|Miss",
    "confidence": "High|Medium|Low",
    "rationale": "2-3 sentences"
  }},
  "overall_news_sentiment": "Positive|Neutral|Negative|Mixed",
  "key_themes": ["theme 1", "theme 2", "theme 3"]
}}
"""
                try:
                    raw3 = ask_claude(client, "You are a financial analyst. Return only valid JSON, no markdown.", news_prompt)
                    raw3 = raw3.strip()
                    if raw3.startswith("```"):
                        raw3 = raw3.split("```")[1]
                        if raw3.startswith("json"):
                            raw3 = raw3[4:]
                    news_data = json.loads(raw3)

                    sentiment = news_data.get("overall_news_sentiment","Neutral")
                    sent_color = "#2e7d32" if sentiment == "Positive" else "#c62828" if sentiment == "Negative" else "#f57c00"
                    st.markdown(f"**News Sentiment:** <span style='color:{sent_color};font-weight:700'>{sentiment}</span>", unsafe_allow_html=True)

                    col_e, col_c2 = st.columns(2)
                    with col_e:
                        st.markdown("#### 🚀 Things to Be Excited About")
                        for pt in news_data.get("exciting_things", []):
                            st.markdown(f"✅ {pt}")
                    with col_c2:
                        st.markdown("#### 🚨 Things to Be Cautious Of")
                        for pt in news_data.get("caution_flags", []):
                            st.markdown(f"⚠️ {pt}")

                    st.markdown("#### 📅 Upcoming Earnings Estimate")
                    ee = news_data.get("upcoming_earnings_estimate", {})
                    col_ee1, col_ee2, col_ee3, col_ee4 = st.columns(4)
                    col_ee1.metric("Est. Date", ee.get("date_estimate","N/A"))
                    col_ee2.metric("EPS Estimate", ee.get("eps_estimate","N/A"))
                    col_ee3.metric("Revenue Estimate", ee.get("revenue_estimate","N/A"))
                    pred = ee.get("beat_miss_prediction","N/A")
                    pred_color = "#2e7d32" if pred=="Beat" else "#c62828" if pred=="Miss" else "#f57c00"
                    col_ee4.markdown(f"**Beat/Meet/Miss**<br><span style='color:{pred_color};font-size:1.3rem;font-weight:700'>{pred}</span>", unsafe_allow_html=True)
                    st.markdown(f"<div class='metric-card'>{ee.get('rationale','')}</div>", unsafe_allow_html=True)

                    st.markdown("#### 🔑 Key Themes")
                    for theme in news_data.get("key_themes", []):
                        st.markdown(f"• {theme}")

                except Exception as e:
                    st.error(f"Could not parse news analysis: {e}")

            st.markdown("#### Recent Headlines")
            for a in articles[:8]:
                url = a.get("url","#")
                title = a.get("title","")
                source = a.get("source",{}).get("name","")
                pub = a.get("publishedAt","")[:10]
                desc = a.get("description","") or ""
                st.markdown(
                    f"<div class='news-card'>"
                    f"<a href='{url}' target='_blank' style='font-weight:600;color:#1a73e8;text-decoration:none'>{title}</a>"
                    f"<br><small style='color:#888'>{source} · {pub}</small>"
                    f"<br><small style='color:#555'>{desc[:150]}{'…' if len(desc)>150 else ''}</small>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No news articles found. Add a News API key above to enable this section.")
            st.markdown("You can get a free key at [newsapi.org](https://newsapi.org)")

    # ── Tab 4: Dividends ──────────────────────────────────────────────────────
    with tabs[3]:
        st.markdown("### Dividend Analysis")

        dividend_rate = info.get("dividendRate")
        dividend_yield = info.get("dividendYield")
        ex_div_date = info.get("exDividendDate")
        payout_ratio = info.get("payoutRatio")
        five_yr_avg_yield = info.get("fiveYearAvgDividendYield")
        last_dividend = info.get("lastDividendValue")

        if dividend_rate and dividend_rate > 0:
            with st.spinner("Analyzing dividend with Claude AI…"):
                div_prompt = f"""
You are a dividend investing expert. Here is data for {ticker} ({company_name}):

Current Price: ${current_price}
Dividend Rate (annual): ${dividend_rate}
Dividend Yield: {dividend_yield}
Ex-Dividend Date (unix): {ex_div_date}
Payout Ratio: {payout_ratio}
5-Year Average Yield: {five_yr_avg_yield}
Last Dividend Value: ${last_dividend}

Financial context:
{context[:1500]}

Respond ONLY with a valid JSON object (no markdown fences):
{{
  "ex_dividend_date_human": "human readable date or 'Check broker for latest date'",
  "must_own_by": "date you must own shares by (day before ex-div date)",
  "payment_date_estimate": "estimated payment date",
  "quarterly_dividend_per_share": "dollar amount",
  "annual_yield_pct": "percentage string",
  "yield_vs_average": "Above Average|Average|Below Average",
  "dividend_safety_rating": "Very Safe|Safe|Moderate|At Risk",
  "dividend_safety_rationale": "2-3 sentences on payout ratio and cash flow coverage",
  "capture_recommendation": "Strong Buy for Dividend|Buy for Dividend|Neutral|Avoid for Dividend",
  "capture_rationale": "2-3 sentences explaining whether capturing the dividend makes sense",
  "dividend_growth_outlook": "Growing|Stable|At Risk of Cut",
  "key_insights": ["insight 1", "insight 2", "insight 3"]
}}
"""
                try:
                    raw4 = ask_claude(client, "You are a dividend investing expert. Return only valid JSON, no markdown.", div_prompt)
                    raw4 = raw4.strip()
                    if raw4.startswith("```"):
                        raw4 = raw4.split("```")[1]
                        if raw4.startswith("json"):
                            raw4 = raw4[4:]
                    div_data = json.loads(raw4)

                    st.markdown(
                        f"<div class='dividend-highlight'>"
                        f"<h4 style='margin:0 0 12px 0'>💰 Dividend Summary for {ticker}</h4>"
                        f"<table style='width:100%;border-collapse:collapse'>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Annual Dividend Rate:</td><td>${dividend_rate}/share</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Dividend Yield:</td><td>{div_data.get('annual_yield_pct','N/A')}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Quarterly Per Share:</td><td>{div_data.get('quarterly_dividend_per_share','N/A')}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Ex-Dividend Date:</td><td><strong>{div_data.get('ex_dividend_date_human','N/A')}</strong></td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>⚡ Must Own By:</td><td><strong style='color:#c62828'>{div_data.get('must_own_by','N/A')}</strong></td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Est. Payment Date:</td><td>{div_data.get('payment_date_estimate','N/A')}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>5-Year Avg Yield:</td><td>{five_yr_avg_yield or 'N/A'}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Payout Ratio:</td><td>{payout_ratio or 'N/A'}</td></tr>"
                        f"</table></div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown("#### Dividend Quality Assessment")
                    col_d1, col_d2, col_d3 = st.columns(3)
                    col_d1.metric("Safety Rating", div_data.get("dividend_safety_rating","N/A"))
                    col_d2.metric("Yield vs Average", div_data.get("yield_vs_average","N/A"))
                    col_d3.metric("Growth Outlook", div_data.get("dividend_growth_outlook","N/A"))

                    st.markdown(f"<div class='metric-card'><strong>Safety Analysis:</strong> {div_data.get('dividend_safety_rationale','')}</div>", unsafe_allow_html=True)

                    rec = div_data.get("capture_recommendation","Neutral")
                    rec_color = "#2e7d32" if "Buy" in rec else "#c62828" if "Avoid" in rec else "#f57c00"
                    st.markdown(
                        f"<div class='metric-card'>"
                        f"<strong>Dividend Capture Recommendation:</strong> "
                        f"<span style='color:{rec_color};font-weight:700'>{rec}</span>"
                        f"<br>{div_data.get('capture_rationale','')}</div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown("#### 💡 Key Dividend Insights")
                    for ins in div_data.get("key_insights", []):
                        st.markdown(f"• {ins}")

                    st.caption("⚠️ Dividend dates can change. Always verify ex-dividend date with your broker before trading.")

                except Exception as e:
                    st.error(f"Could not parse dividend analysis: {e}")
        else:
            st.info(f"**{company_name} ({ticker})** does not currently pay a dividend.")
            st.markdown("This may be because the company reinvests earnings for growth rather than distributing them to shareholders.")

elif analyze_btn and not ticker_input:
    st.warning("Please enter a stock ticker symbol.")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
st.caption("⚠️ This tool is for informational and educational purposes only. Nothing here constitutes financial advice. Always do your own research before making investment decisions.")
