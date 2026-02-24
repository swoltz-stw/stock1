import streamlit as st
import yfinance as yf
import anthropic
import requests
import json
import time
import random
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# ── Secrets helper (works locally via .env and on Streamlit Cloud via st.secrets)
def get_secret(key: str) -> str:
    try:
        val = st.secrets.get(key, "")
        if val:
            return val
    except Exception:
        pass
    return os.getenv(key, "")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Evaluator AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header { font-size:2.5rem; font-weight:800; background:linear-gradient(90deg,#1a73e8,#0d47a1);
        -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:0.2rem; }
    .sub-header  { color:#666; margin-bottom:2rem; font-size:1rem; }
    .rating-excellent { background:#d4edda; color:#155724; border-radius:6px; padding:4px 10px; font-weight:700; display:inline-block; }
    .rating-good      { background:#cce5ff; color:#004085; border-radius:6px; padding:4px 10px; font-weight:700; display:inline-block; }
    .rating-neutral   { background:#fff3cd; color:#856404; border-radius:6px; padding:4px 10px; font-weight:700; display:inline-block; }
    .rating-bad       { background:#f8d7da; color:#721c24; border-radius:6px; padding:4px 10px; font-weight:700; display:inline-block; }
    .metric-card { background:#f8f9fa; border-radius:10px; padding:1rem 1.2rem; border-left:4px solid #1a73e8; margin-bottom:1rem; }
    .section-divider { border-top:2px solid #e0e0e0; margin:2rem 0; }
    .news-card { background:#f8f9fa; border-radius:8px; padding:1rem; margin-bottom:0.8rem; border-left:3px solid #1a73e8; }
    .dividend-highlight { background:linear-gradient(135deg,#e8f5e9,#c8e6c9); border-radius:10px; padding:1.2rem; border:1px solid #81c784; }
    .price-target-card { background:#fff; border:1px solid #e0e0e0; border-radius:10px; padding:1rem; text-align:center; }
    .price-up   { color:#2e7d32; font-weight:700; }
    .price-down { color:#c62828; font-weight:700; }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">📈 Stock Evaluator AI</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Earnings analysis · Price targets · News · Dividends — powered by Claude AI</p>', unsafe_allow_html=True)

# ── API Keys ──────────────────────────────────────────────────────────────────
_ant  = get_secret("ANTHROPIC_API_KEY")
_news = get_secret("NEWS_API_KEY")

with st.expander("⚙️ API Keys (stored only for this session)", expanded=not _ant):
    col1, col2 = st.columns(2)
    with col1:
        anthropic_key = st.text_input("Anthropic API Key", value=_ant,  type="password", help="console.anthropic.com")
    with col2:
        news_key      = st.text_input("News API Key",      value=_news, type="password", help="newsapi.org (free)")

# ── Ticker input ──────────────────────────────────────────────────────────────
st.markdown("### Enter a Stock Ticker")
col_input, col_btn = st.columns([3, 1])
with col_input:
    ticker_input = st.text_input("Stock Ticker", placeholder="e.g. AAPL, MSFT, NVDA, TSLA", label_visibility="collapsed")
with col_btn:
    analyze_btn = st.button("🔍 Analyze", use_container_width=True, type="primary")


# ══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING — robust yfinance with browser-like headers + retry
# ══════════════════════════════════════════════════════════════════════════════

# Rotate user agents to avoid Yahoo Finance rate limiting
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def get_stock_data(ticker: str) -> dict:
    """Fetch stock data from Yahoo Finance with retry and rotating headers."""
    last_error = "Unknown error"
    for attempt in range(4):
        try:
            if attempt > 0:
                wait = 2 ** attempt + random.uniform(0, 2)
                time.sleep(wait)

            # Set a fresh session with browser-like headers each attempt
            session = requests.Session()
            session.headers.update({
                "User-Agent": USER_AGENTS[attempt % len(USER_AGENTS)],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            })

            stock = yf.Ticker(ticker, session=session)
            info  = stock.info

            # yfinance returns a minimal stub on rate limit — check we got real data
            price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("price")
            if not info or len(info) < 15 or price is None:
                last_error = f"Attempt {attempt+1}: Yahoo returned incomplete data ({len(info) if info else 0} fields). Retrying..."
                continue

            return {
                "info":                 info,
                "quarterly_financials": stock.quarterly_financials,
                "quarterly_income":     stock.quarterly_income_stmt,
                "cashflow":             stock.cashflow,
                "balance_sheet":        stock.balance_sheet,
                "source":               "Yahoo Finance",
            }

        except Exception as e:
            last_error = f"Attempt {attempt+1}: {str(e)}"
            continue

    raise RuntimeError(
        f"Yahoo Finance could not load data for **{ticker}** after 4 attempts.\n\n"
        f"Last error: {last_error}\n\n"
        f"This is usually a temporary rate limit. Please wait 30 seconds and try again."
    )


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def safe_val(val):
    try:
        if val is None: return None
        if hasattr(val, 'item'): return val.item()
        if hasattr(val, 'isoformat'): return val.isoformat()
        return val
    except Exception:
        return str(val)

def df_to_dict(df, cols=4):
    if df is None or (hasattr(df, 'empty') and df.empty):
        return {}
    try:
        sub = df.iloc[:, :cols]
        return {str(c)[:20]: {str(i): safe_val(v) for i, v in sub[c].items()} for c in sub.columns}
    except Exception:
        return {}

def fmt(v, prefix=""):
    if v is None: return "N/A"
    if isinstance(v, (int, float)) and abs(v) > 1_000_000:
        return f"{prefix}{v:,.0f}"
    return f"{prefix}{v}"

def build_context(data: dict, ticker: str) -> str:
    info = data["info"]
    parts = [
        f"STOCK: {ticker.upper()} — {info.get('longName', ticker)}",
        f"Sector: {info.get('sector','N/A')} | Industry: {info.get('industry','N/A')}",
        f"Current Price: ${info.get('currentPrice', info.get('regularMarketPrice','N/A'))}",
        f"52-Week Range: ${info.get('fiftyTwoWeekLow','N/A')} – ${info.get('fiftyTwoWeekHigh','N/A')}",
        f"Market Cap: {fmt(info.get('marketCap'),'$')}",
        f"P/E (TTM): {info.get('trailingPE','N/A')} | Forward P/E: {info.get('forwardPE','N/A')}",
        f"EPS (TTM): {info.get('trailingEps','N/A')} | Forward EPS: {info.get('forwardEps','N/A')}",
        f"Revenue (TTM): {fmt(info.get('totalRevenue'),'$')}",
        f"Gross Margins: {info.get('grossMargins','N/A')} | Operating Margins: {info.get('operatingMargins','N/A')} | Profit Margins: {info.get('profitMargins','N/A')}",
        f"Revenue Growth: {info.get('revenueGrowth','N/A')} | Earnings Growth: {info.get('earningsGrowth','N/A')}",
        f"Beta: {info.get('beta','N/A')}",
        f"Dividend Rate: {info.get('dividendRate','N/A')} | Yield: {info.get('dividendYield','N/A')}",
        f"Ex-Dividend Date: {info.get('exDividendDate','N/A')} | Payout Ratio: {info.get('payoutRatio','N/A')}",
        f"Analyst Target: {info.get('targetMeanPrice','N/A')} (Low: {info.get('targetLowPrice','N/A')}, High: {info.get('targetHighPrice','N/A')})",
        f"Recommendation: {info.get('recommendationKey','N/A')} | # Analysts: {info.get('numberOfAnalystOpinions','N/A')}",
        f"ROE: {info.get('returnOnEquity','N/A')} | ROA: {info.get('returnOnAssets','N/A')}",
        f"Debt/Equity: {info.get('debtToEquity','N/A')}",
        f"Free Cash Flow: {fmt(info.get('freeCashflow'),'$')}",
        f"Total Cash: {fmt(info.get('totalCash'),'$')} | Total Debt: {fmt(info.get('totalDebt'),'$')}",
        f"Short Ratio: {info.get('shortRatio','N/A')} | Short % Float: {info.get('shortPercentOfFloat','N/A')}",
        "\n--- QUARTERLY FINANCIALS ---",
        json.dumps(df_to_dict(data.get("quarterly_financials")), indent=2),
        "\n--- QUARTERLY INCOME ---",
        json.dumps(df_to_dict(data.get("quarterly_income")), indent=2),
        "\n--- ANNUAL CASHFLOW ---",
        json.dumps(df_to_dict(data.get("cashflow")), indent=2),
    ]
    return "\n".join(str(p) for p in parts)

def get_news(ticker: str, company: str, api_key: str) -> list:
    if not api_key:
        return []
    try:
        r = requests.get("https://newsapi.org/v2/everything",
            params={"q": company, "sortBy": "publishedAt", "pageSize": 10, "language": "en", "apiKey": api_key},
            timeout=10)
        if r.status_code == 200:
            return r.json().get("articles", [])
    except Exception:
        pass
    return []

def ask_claude(client, system: str, prompt: str) -> str:
    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text

def parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

def rating_cls(r: str) -> str:
    r = r.lower()
    return "rating-excellent" if "excellent" in r else "rating-good" if "good" in r else "rating-bad" if "bad" in r else "rating-neutral"

def display_rating(label: str, rating: str, commentary: str = ""):
    note = f"<br><small style='color:#555'>{commentary}</small>" if commentary else ""
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;margin-bottom:8px'>"
        f"<span style='min-width:220px;font-weight:600'>{label}</span>"
        f"<span class='{rating_cls(rating)}'>{rating}</span>{note}</div>",
        unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if analyze_btn and ticker_input:
    ticker = ticker_input.strip().upper()

    if not anthropic_key:
        st.error("Please enter your Anthropic API key above.")
        st.stop()

    client = anthropic.Anthropic(api_key=anthropic_key)

    with st.spinner(f"Fetching data for {ticker} from Yahoo Finance…"):
        try:
            data = get_stock_data(ticker)
        except Exception as e:
            st.error("❌ Could not load stock data")
            for line in str(e).split("\n"):
                if line.strip():
                    st.markdown(line)
            st.info("💡 Tip: Yahoo Finance occasionally rate-limits requests. Wait 30 seconds and try again.")
            st.stop()

    info          = data["info"]
    company_name  = info.get("longName", ticker)
    current_price = info.get("currentPrice", info.get("regularMarketPrice", "N/A"))

    st.markdown(f"## {company_name} ({ticker})")
    st.markdown(f"**Price:** ${current_price} &nbsp;|&nbsp; **Sector:** {info.get('sector','N/A')} &nbsp;|&nbsp; **Industry:** {info.get('industry','N/A')}", unsafe_allow_html=True)
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    context = build_context(data, ticker)
    tabs = st.tabs(["📊 Earnings Analysis", "💡 Insights & Price Targets", "📰 Stock in the News", "💰 Dividends"])

    # ── Tab 1: Earnings ───────────────────────────────────────────────────────
    with tabs[0]:
        st.markdown("### Earnings Report Scorecard")
        with st.spinner("Analyzing earnings with Claude AI…"):
            try:
                ed = parse_json(ask_claude(client,
                    "You are a financial analyst. Return only valid JSON, no markdown.",
                    f"""Evaluate the latest earnings data for {ticker} ({company_name}).

{context}

Respond ONLY with valid JSON:
{{
  "overall_rating": "Excellent|Good|Neutral|Bad",
  "overall_summary": "2-3 sentence assessment",
  "categories": [
    {{"name": "Revenue Growth",          "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Profitability & Margins", "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Earnings Per Share",      "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Cash Flow Generation",    "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Balance Sheet Health",    "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Valuation",               "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Analyst Sentiment",       "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Revenue vs Expectations", "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Cost Management",         "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Return on Capital",       "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}}
  ]
}}"""))
                overall = ed.get("overall_rating","Neutral")
                st.markdown(
                    f"<div class='metric-card'><strong>Overall Rating:</strong> "
                    f"<span class='{rating_cls(overall)}'>{overall}</span><br>"
                    f"<span style='color:#444'>{ed.get('overall_summary','')}</span></div>",
                    unsafe_allow_html=True)
                st.markdown("#### Category Breakdown")
                for cat in ed.get("categories", []):
                    display_rating(cat["name"], cat["rating"], cat.get("commentary",""))
            except Exception as e:
                st.error(f"Earnings analysis error: {e}")

    # ── Tab 2: Insights & Price Targets ───────────────────────────────────────
    with tabs[1]:
        st.markdown("### AI Insights & Price Targets")
        with st.spinner("Generating insights and price targets…"):
            try:
                ins = parse_json(ask_claude(client,
                    "You are a financial analyst. Return only valid JSON, no markdown.",
                    f"""Senior equity analyst perspective on {ticker} ({company_name}).

{context}
Current price: ${current_price}

Respond ONLY with valid JSON:
{{
  "what_doing_well": ["point 1","point 2","point 3","point 4"],
  "risks_concerns":  ["risk 1","risk 2","risk 3"],
  "overall_outlook": "Bullish|Cautiously Bullish|Neutral|Cautiously Bearish|Bearish",
  "outlook_rationale": "3-4 sentences",
  "price_targets": {{
    "next_day":     {{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"}},
    "next_week":    {{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"}},
    "next_month":   {{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"}},
    "next_quarter": {{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"}},
    "next_year":    {{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"}}
  }},
  "buy_sell_hold": "Buy|Sell|Hold",
  "conviction": "High|Medium|Low"
}}"""))

                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Outlook",        ins.get("overall_outlook","Neutral"))
                col_b.metric("Recommendation", ins.get("buy_sell_hold","Hold"))
                col_c.metric("Conviction",     ins.get("conviction","Medium"))
                st.markdown(f"<div class='metric-card'>{ins.get('outlook_rationale','')}</div>", unsafe_allow_html=True)

                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown("#### ✅ What the Company is Doing Well")
                    for pt in ins.get("what_doing_well",[]): st.markdown(f"• {pt}")
                with col_r:
                    st.markdown("#### ⚠️ Risks & Concerns")
                    for pt in ins.get("risks_concerns",[]): st.markdown(f"• {pt}")

                st.markdown("#### 🎯 Price Targets")
                periods = [("next_day","Next Day"),("next_week","Next Week"),("next_month","Next Month"),("next_quarter","Next Quarter"),("next_year","Next Year")]
                pt_cols = st.columns(5)
                for i,(key,label) in enumerate(periods):
                    pt  = ins.get("price_targets",{}).get(key,{})
                    tgt = pt.get("target",0)
                    dir = pt.get("direction","Flat")
                    arrow = "▲" if dir=="Up" else "▼" if dir=="Down" else "→"
                    cls   = "price-up" if dir=="Up" else "price-down" if dir=="Down" else ""
                    try:
                        pct = ((float(tgt)-float(current_price))/float(current_price))*100
                        pct_str = f"{pct:+.1f}%"
                    except: pct_str = ""
                    with pt_cols[i]:
                        st.markdown(
                            f"<div class='price-target-card'>"
                            f"<div style='font-size:0.8rem;color:#666;margin-bottom:4px'>{label}</div>"
                            f"<div style='font-size:1.4rem;font-weight:800'>${tgt:.2f}</div>"
                            f"<div class='{cls}'>{arrow} {pct_str}</div>"
                            f"<div style='font-size:0.7rem;color:#888;margin-top:6px'>{pt.get('rationale','')}</div>"
                            f"</div>", unsafe_allow_html=True)
                st.caption("⚠️ AI-generated estimates — not financial advice.")
            except Exception as e:
                st.error(f"Insights error: {e}")

    # ── Tab 3: News ───────────────────────────────────────────────────────────
    with tabs[2]:
        st.markdown("### Stock in the News")
        articles = get_news(ticker, company_name, news_key)
        if articles:
            with st.spinner("Analyzing news with Claude AI…"):
                headlines = "\n".join([f"- {a['title']} ({a.get('source',{}).get('name','')})" for a in articles[:10]])
                try:
                    nd = parse_json(ask_claude(client,
                        "You are a financial analyst. Return only valid JSON, no markdown.",
                        f"""News analysis for {ticker} ({company_name}):
{headlines}

Context: {context[:2000]}

Respond ONLY with valid JSON:
{{
  "exciting_things": ["thing 1","thing 2","thing 3"],
  "caution_flags":   ["flag 1","flag 2","flag 3"],
  "upcoming_earnings_estimate": {{
    "date_estimate":"approximate date",
    "eps_estimate":"EPS estimate",
    "revenue_estimate":"revenue estimate",
    "beat_miss_prediction":"Beat|Meet|Miss",
    "confidence":"High|Medium|Low",
    "rationale":"2-3 sentences"
  }},
  "overall_news_sentiment":"Positive|Neutral|Negative|Mixed",
  "key_themes":["theme 1","theme 2","theme 3"]
}}"""))
                    sentiment  = nd.get("overall_news_sentiment","Neutral")
                    sent_color = "#2e7d32" if sentiment=="Positive" else "#c62828" if sentiment=="Negative" else "#f57c00"
                    st.markdown(f"**Sentiment:** <span style='color:{sent_color};font-weight:700'>{sentiment}</span>", unsafe_allow_html=True)

                    col_e, col_c2 = st.columns(2)
                    with col_e:
                        st.markdown("#### 🚀 Things to Be Excited About")
                        for pt in nd.get("exciting_things",[]): st.markdown(f"✅ {pt}")
                    with col_c2:
                        st.markdown("#### 🚨 Things to Be Cautious Of")
                        for pt in nd.get("caution_flags",[]): st.markdown(f"⚠️ {pt}")

                    st.markdown("#### 📅 Upcoming Earnings Estimate")
                    ee = nd.get("upcoming_earnings_estimate",{})
                    c1,c2,c3,c4 = st.columns(4)
                    c1.metric("Est. Date",        ee.get("date_estimate","N/A"))
                    c2.metric("EPS Estimate",     ee.get("eps_estimate","N/A"))
                    c3.metric("Revenue Estimate", ee.get("revenue_estimate","N/A"))
                    pred = ee.get("beat_miss_prediction","N/A")
                    c4.markdown(f"**Beat/Meet/Miss**<br><span style='color:{'#2e7d32' if pred=='Beat' else '#c62828' if pred=='Miss' else '#f57c00'};font-size:1.3rem;font-weight:700'>{pred}</span>", unsafe_allow_html=True)
                    st.markdown(f"<div class='metric-card'>{ee.get('rationale','')}</div>", unsafe_allow_html=True)
                    st.markdown("#### 🔑 Key Themes")
                    for t in nd.get("key_themes",[]): st.markdown(f"• {t}")
                except Exception as e:
                    st.error(f"News analysis error: {e}")

            st.markdown("#### Recent Headlines")
            for a in articles[:8]:
                desc = a.get("description","") or ""
                st.markdown(
                    f"<div class='news-card'>"
                    f"<a href='{a.get('url','#')}' target='_blank' style='font-weight:600;color:#1a73e8;text-decoration:none'>{a.get('title','')}</a>"
                    f"<br><small style='color:#888'>{a.get('source',{}).get('name','')} · {a.get('publishedAt','')[:10]}</small>"
                    f"<br><small style='color:#555'>{desc[:150]}{'…' if len(desc)>150 else ''}</small>"
                    f"</div>", unsafe_allow_html=True)
        else:
            st.info("No news found. Add a News API key above to enable this section.")
            st.markdown("Free key at [newsapi.org](https://newsapi.org)")

    # ── Tab 4: Dividends ──────────────────────────────────────────────────────
    with tabs[3]:
        st.markdown("### Dividend Analysis")
        div_rate   = info.get("dividendRate")
        div_yield  = info.get("dividendYield")
        ex_div     = info.get("exDividendDate")
        payout     = info.get("payoutRatio")
        five_yr    = info.get("fiveYearAvgDividendYield")
        last_div   = info.get("lastDividendValue")

        if div_rate and float(div_rate) > 0:
            with st.spinner("Analyzing dividend with Claude AI…"):
                try:
                    dd = parse_json(ask_claude(client,
                        "You are a dividend investing expert. Return only valid JSON, no markdown.",
                        f"""Dividend analysis for {ticker} ({company_name}):
Current Price: ${current_price}
Annual Dividend Rate: ${div_rate}
Dividend Yield: {div_yield}
Ex-Dividend Date: {ex_div}
Payout Ratio: {payout}
5-Year Avg Yield: {five_yr}
Last Dividend: ${last_div}
{context[:1500]}

Respond ONLY with valid JSON:
{{
  "ex_dividend_date_human":"human readable date",
  "must_own_by":"date you must own shares by",
  "payment_date_estimate":"estimated payment date",
  "quarterly_dividend_per_share":"dollar amount",
  "annual_yield_pct":"e.g. 3.2%",
  "yield_vs_average":"Above Average|Average|Below Average",
  "dividend_safety_rating":"Very Safe|Safe|Moderate|At Risk",
  "dividend_safety_rationale":"2-3 sentences",
  "capture_recommendation":"Strong Buy for Dividend|Buy for Dividend|Neutral|Avoid for Dividend",
  "capture_rationale":"2-3 sentences",
  "dividend_growth_outlook":"Growing|Stable|At Risk of Cut",
  "key_insights":["insight 1","insight 2","insight 3"]
}}"""))

                    st.markdown(
                        f"<div class='dividend-highlight'><h4 style='margin:0 0 12px 0'>💰 Dividend Summary — {ticker}</h4>"
                        f"<table style='width:100%;border-collapse:collapse'>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Annual Rate:</td><td>${div_rate}/share</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Yield:</td><td>{dd.get('annual_yield_pct','N/A')}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Quarterly Per Share:</td><td>{dd.get('quarterly_dividend_per_share','N/A')}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Ex-Dividend Date:</td><td><strong>{dd.get('ex_dividend_date_human','N/A')}</strong></td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>⚡ Must Own By:</td><td><strong style='color:#c62828'>{dd.get('must_own_by','N/A')}</strong></td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Est. Payment Date:</td><td>{dd.get('payment_date_estimate','N/A')}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Payout Ratio:</td><td>{payout or 'N/A'}</td></tr>"
                        f"</table></div>", unsafe_allow_html=True)

                    c1,c2,c3 = st.columns(3)
                    c1.metric("Safety Rating",    dd.get("dividend_safety_rating","N/A"))
                    c2.metric("Yield vs Average", dd.get("yield_vs_average","N/A"))
                    c3.metric("Growth Outlook",   dd.get("dividend_growth_outlook","N/A"))
                    st.markdown(f"<div class='metric-card'><strong>Safety:</strong> {dd.get('dividend_safety_rationale','')}</div>", unsafe_allow_html=True)
                    rec = dd.get("capture_recommendation","Neutral")
                    st.markdown(
                        f"<div class='metric-card'><strong>Capture Recommendation:</strong> "
                        f"<span style='color:{'#2e7d32' if 'Buy' in rec else '#c62828' if 'Avoid' in rec else '#f57c00'};font-weight:700'>{rec}</span>"
                        f"<br>{dd.get('capture_rationale','')}</div>", unsafe_allow_html=True)
                    st.markdown("#### 💡 Key Insights")
                    for ins in dd.get("key_insights",[]): st.markdown(f"• {ins}")
                    st.caption("⚠️ Always verify ex-dividend date with your broker before trading.")
                except Exception as e:
                    st.error(f"Dividend analysis error: {e}")
        else:
            st.info(f"**{company_name} ({ticker})** does not currently pay a dividend.")

elif analyze_btn and not ticker_input:
    st.warning("Please enter a stock ticker symbol.")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
st.caption("⚠️ For informational purposes only. Not financial advice. Always do your own research.")
