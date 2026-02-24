import streamlit as st
import anthropic
import requests
import json
import time
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ── Secrets helper ────────────────────────────────────────────────────────────
def get_secret(key: str) -> str:
    try:
        val = st.secrets.get(key, "")
        if val: return val
    except Exception:
        pass
    return os.getenv(key, "")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Stock Evaluator AI", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

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
    .data-badge { font-size:0.72rem; padding:2px 10px; border-radius:10px; background:#e8f0fe; color:#1a73e8; font-weight:600; display:inline-block; margin-left:8px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">📈 Stock Evaluator AI</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Earnings analysis · Price targets · News · Dividends — powered by Claude AI</p>', unsafe_allow_html=True)

# ── API Keys ──────────────────────────────────────────────────────────────────
_ant = get_secret("ANTHROPIC_API_KEY")
_av  = get_secret("ALPHA_VANTAGE_API_KEY")
_nws = get_secret("NEWS_API_KEY")

with st.expander("⚙️ API Keys (stored only for this session)", expanded=not _ant):
    c1, c2, c3 = st.columns(3)
    with c1: anthropic_key = st.text_input("Anthropic API Key",       value=_ant, type="password", help="console.anthropic.com")
    with c2: av_key        = st.text_input("Alpha Vantage API Key",   value=_av,  type="password", help="alphavantage.co — free, 25 req/day")
    with c3: news_key      = st.text_input("News API Key (optional)", value=_nws, type="password", help="newsapi.org — free")

st.markdown("### Enter a Stock Ticker")
ci, cb = st.columns([3, 1])
with ci: ticker_input = st.text_input("Stock Ticker", placeholder="e.g. AAPL, MSFT, NVDA, TSLA", label_visibility="collapsed")
with cb: analyze_btn  = st.button("🔍 Analyze", use_container_width=True, type="primary")


# ══════════════════════════════════════════════════════════════════════════════
# ALPHA VANTAGE DATA LAYER
# ══════════════════════════════════════════════════════════════════════════════

AV_BASE = "https://www.alphavantage.co/query"

def av_get(params: dict, api_key: str) -> dict | None:
    """Call Alpha Vantage API. Returns dict or None on error."""
    try:
        p = {**params, "apikey": api_key}
        r = requests.get(AV_BASE, params=p, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        # AV returns {"Note": "..."} on rate limit, {"Information": "..."} on bad key
        if "Note" in data or "Information" in data:
            msg = data.get("Note") or data.get("Information","")
            raise RuntimeError(f"Alpha Vantage API issue: {msg[:200]}")
        return data
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Alpha Vantage request failed: {e}")


def get_stock_data(ticker: str, api_key: str) -> dict:
    """Fetch all needed data from Alpha Vantage. Returns unified data dict."""

    PAUSE = 13  # Alpha Vantage free tier: max 5 requests/min = 1 per 12s to be safe

    # 1. Company overview (the main data source — has almost everything)
    overview = av_get({"function": "OVERVIEW", "symbol": ticker}, api_key)
    if not overview or not overview.get("Symbol"):
        raise RuntimeError(
            f"Could not find data for **{ticker}**. "
            f"Please check the ticker symbol is correct (e.g. NVDA, AAPL, TSLA).\n\n"
            f"Note: Alpha Vantage free tier allows 25 requests/day and 5 per minute. "
            f"If you searched recently, wait 1 minute and try again."
        )

    # 2. Global quote (real-time price)
    time.sleep(PAUSE)
    quote_data = av_get({"function": "GLOBAL_QUOTE", "symbol": ticker}, api_key)
    quote = quote_data.get("Global Quote", {}) if quote_data else {}

    # 3. Income statement
    time.sleep(PAUSE)
    income_data = av_get({"function": "INCOME_STATEMENT", "symbol": ticker}, api_key)
    annual_reports    = income_data.get("annualReports", [])[:4]    if income_data else []
    quarterly_reports = income_data.get("quarterlyReports", [])[:4] if income_data else []

    # 4. Cash flow statement
    time.sleep(PAUSE)
    cashflow_data = av_get({"function": "CASH_FLOW", "symbol": ticker}, api_key)
    annual_cashflow    = cashflow_data.get("annualReports", [])[:2]    if cashflow_data else []
    quarterly_cashflow = cashflow_data.get("quarterlyReports", [])[:2] if cashflow_data else []

    # 5. Balance sheet
    time.sleep(PAUSE)
    balance_data = av_get({"function": "BALANCE_SHEET", "symbol": ticker}, api_key)
    annual_balance = balance_data.get("annualReports", [])[:2] if balance_data else []

    # 6. Earnings (EPS history + estimates)
    time.sleep(PAUSE)
    earnings_data = av_get({"function": "EARNINGS", "symbol": ticker}, api_key)
    annual_earnings    = earnings_data.get("annualEarnings", [])[:4]    if earnings_data else []
    quarterly_earnings = earnings_data.get("quarterlyEarnings", [])[:4] if earnings_data else []

    # Derive current price from quote or overview
    current_price = (
        quote.get("05. price") or
        overview.get("AnalystTargetPrice") and None or  # don't use target as price
        None
    )
    if not current_price:
        # fallback: use 52-week range midpoint
        hi = overview.get("52WeekHigh")
        lo = overview.get("52WeekLow")
        if hi and lo:
            current_price = str(round((float(hi) + float(lo)) / 2, 2))

    return {
        "overview":            overview,
        "quote":               quote,
        "annual_income":       annual_reports,
        "quarterly_income":    quarterly_reports,
        "annual_cashflow":     annual_cashflow,
        "quarterly_cashflow":  quarterly_cashflow,
        "annual_balance":      annual_balance,
        "annual_earnings":     annual_earnings,
        "quarterly_earnings":  quarterly_earnings,
        "current_price":       current_price,
        "source":              "Alpha Vantage",
    }


# ══════════════════════════════════════════════════════════════════════════════
# CONTEXT BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_context(data: dict, ticker: str) -> str:
    o  = data["overview"]
    q  = data["quote"]
    cp = data["current_price"] or "N/A"

    def ov(key): return o.get(key, "N/A")

    lines = [
        f"STOCK: {ticker.upper()} — {ov('Name')}",
        f"Sector: {ov('Sector')} | Industry: {ov('Industry')}",
        f"Description: {ov('Description')[:300]}",
        f"",
        f"── PRICE & VALUATION ──",
        f"Current Price: ${cp}",
        f"52-Week Range: ${ov('52WeekLow')} – ${ov('52WeekHigh')}",
        f"50-Day MA: ${ov('50DayMovingAverage')} | 200-Day MA: ${ov('200DayMovingAverage')}",
        f"Market Cap: ${ov('MarketCapitalization')}",
        f"P/E (TTM): {ov('PERatio')} | Forward P/E: {ov('ForwardPE')} | PEG: {ov('PEGRatio')}",
        f"Price/Sales: {ov('PriceToSalesRatioTTM')} | Price/Book: {ov('PriceToBookRatio')}",
        f"EV/EBITDA: {ov('EVToEBITDA')} | EV/Revenue: {ov('EVToRevenue')}",
        f"",
        f"── EARNINGS & REVENUE ──",
        f"EPS (TTM): {ov('EPS')} | Diluted EPS (TTM): {ov('DilutedEPSTTM')}",
        f"Revenue (TTM): ${ov('RevenueTTM')}",
        f"Gross Profit (TTM): ${ov('GrossProfitTTM')}",
        f"EBITDA: ${ov('EBITDA')}",
        f"Revenue/Share: {ov('RevenuePerShareTTM')}",
        f"Quarterly Revenue Growth (YoY): {ov('QuarterlyRevenueGrowthYOY')}",
        f"Quarterly Earnings Growth (YoY): {ov('QuarterlyEarningsGrowthYOY')}",
        f"",
        f"── PROFITABILITY ──",
        f"Profit Margin: {ov('ProfitMargin')} | Operating Margin: {ov('OperatingMarginTTM')}",
        f"Return on Assets: {ov('ReturnOnAssetsTTM')} | Return on Equity: {ov('ReturnOnEquityTTM')}",
        f"",
        f"── BALANCE SHEET & CASH ──",
        f"Total Cash (MRQ): ${ov('CashAndCashEquivalentsAtCarryingValue') or 'N/A'}",
        f"Total Debt (MRQ): {ov('TotalDebt') or 'N/A'}",  
        f"Book Value/Share: {ov('BookValue')}",
        f"Beta: {ov('Beta')}",
        f"",
        f"── DIVIDENDS ──",
        f"Dividend/Share: {ov('DividendPerShare')} | Dividend Yield: {ov('DividendYield')}",
        f"Ex-Dividend Date: {ov('ExDividendDate')} | Dividend Date: {ov('DividendDate')}",
        f"",
        f"── ANALYST COVERAGE ──",
        f"Analyst Target Price: ${ov('AnalystTargetPrice')}",
        f"Strong Buy: {ov('AnalystRatingStrongBuy')} | Buy: {ov('AnalystRatingBuy')} | Hold: {ov('AnalystRatingHold')} | Sell: {ov('AnalystRatingSell')} | Strong Sell: {ov('AnalystRatingStrongSell')}",
        f"",
        f"── RECENT QUARTERLY INCOME (last 4 quarters) ──",
    ]

    for r in data["quarterly_income"][:4]:
        lines.append(
            f"  {r.get('fiscalDateEnding','?')}: Revenue=${r.get('totalRevenue','N/A')}, "
            f"Net Income=${r.get('netIncome','N/A')}, "
            f"Gross Profit=${r.get('grossProfit','N/A')}, "
            f"Operating Income=${r.get('operatingIncome','N/A')}"
        )

    lines.append(f"\n── RECENT QUARTERLY EPS ──")
    for r in data["quarterly_earnings"][:4]:
        lines.append(
            f"  {r.get('fiscalDateEnding','?')}: Reported EPS={r.get('reportedEPS','N/A')}, "
            f"Estimated EPS={r.get('estimatedEPS','N/A')}, "
            f"Surprise={r.get('surprise','N/A')} ({r.get('surprisePercentage','N/A')}%)"
        )

    lines.append(f"\n── ANNUAL INCOME (last 4 years) ──")
    for r in data["annual_income"][:4]:
        lines.append(
            f"  {r.get('fiscalDateEnding','?')}: Revenue=${r.get('totalRevenue','N/A')}, "
            f"Net Income=${r.get('netIncome','N/A')}"
        )

    lines.append(f"\n── ANNUAL FREE CASH FLOW ──")
    for r in data["annual_cashflow"][:2]:
        lines.append(
            f"  {r.get('fiscalDateEnding','?')}: Operating CF=${r.get('operatingCashflow','N/A')}, "
            f"CapEx=${r.get('capitalExpenditures','N/A')}"
        )

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# MISC HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_news(company: str, api_key: str) -> list:
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
        model="claude-opus-4-6", max_tokens=4096,
        system=system, messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text

def parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    return json.loads(raw.strip())

def rcls(r: str) -> str:
    r = r.lower()
    return "rating-excellent" if "excellent" in r else "rating-good" if "good" in r else "rating-bad" if "bad" in r else "rating-neutral"

def display_rating(label: str, rating: str, commentary: str = ""):
    note = f"<br><small style='color:#555'>{commentary}</small>" if commentary else ""
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;margin-bottom:8px'>"
        f"<span style='min-width:220px;font-weight:600'>{label}</span>"
        f"<span class='{rcls(rating)}'>{rating}</span>{note}</div>",
        unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if analyze_btn and ticker_input:
    ticker = ticker_input.strip().upper()

    if not anthropic_key:
        st.error("Please enter your Anthropic API key above.")
        st.stop()
    if not av_key:
        st.error("Please enter your Alpha Vantage API key above. Get a free one at alphavantage.co")
        st.stop()

    client = anthropic.Anthropic(api_key=anthropic_key)

    with st.spinner(f"Fetching data for {ticker} from Alpha Vantage… (this takes ~60 seconds on the free plan)"):
        try:
            data = get_stock_data(ticker, av_key)
        except Exception as e:
            st.error("❌ Could not load stock data")
            for line in str(e).split("\n"):
                if line.strip(): st.markdown(line)
            st.stop()

    o             = data["overview"]
    company_name  = o.get("Name", ticker)
    current_price = data["current_price"] or "N/A"
    sector        = o.get("Sector", "N/A")
    industry      = o.get("Industry", "N/A")

    st.markdown(f"## {company_name} ({ticker}) <span class='data-badge'>Alpha Vantage</span>", unsafe_allow_html=True)
    st.markdown(f"**Price:** ${current_price} &nbsp;|&nbsp; **Sector:** {sector} &nbsp;|&nbsp; **Industry:** {industry}", unsafe_allow_html=True)
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
                    f"""Evaluate the latest earnings for {ticker} ({company_name}).

{context}

Respond ONLY with valid JSON:
{{
  "overall_rating": "Excellent|Good|Neutral|Bad",
  "overall_summary": "2-3 sentence assessment",
  "categories": [
    {{"name": "Revenue Growth",          "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Profitability & Margins", "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Earnings Per Share",      "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Earnings Surprises",      "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Cash Flow Generation",    "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Balance Sheet Health",    "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Valuation",               "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Analyst Sentiment",       "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Cost Management",         "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Return on Capital",       "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}}
  ]
}}"""))
                overall = ed.get("overall_rating", "Neutral")
                st.markdown(
                    f"<div class='metric-card'><strong>Overall Rating:</strong> "
                    f"<span class='{rcls(overall)}'>{overall}</span><br>"
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
                    f"""Senior equity analyst view on {ticker} ({company_name}).

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

                ca, cb2, cc = st.columns(3)
                ca.metric("Outlook",        ins.get("overall_outlook","Neutral"))
                cb2.metric("Recommendation", ins.get("buy_sell_hold","Hold"))
                cc.metric("Conviction",     ins.get("conviction","Medium"))
                st.markdown(f"<div class='metric-card'>{ins.get('outlook_rationale','')}</div>", unsafe_allow_html=True)

                cl, cr = st.columns(2)
                with cl:
                    st.markdown("#### ✅ What the Company is Doing Well")
                    for pt in ins.get("what_doing_well",[]): st.markdown(f"• {pt}")
                with cr:
                    st.markdown("#### ⚠️ Risks & Concerns")
                    for pt in ins.get("risks_concerns",[]): st.markdown(f"• {pt}")

                st.markdown("#### 🎯 Price Targets")
                periods = [("next_day","Next Day"),("next_week","Next Week"),("next_month","Next Month"),("next_quarter","Next Quarter"),("next_year","Next Year")]
                pt_cols = st.columns(5)
                for i,(key,label) in enumerate(periods):
                    pt  = ins.get("price_targets",{}).get(key,{})
                    tgt = pt.get("target",0)
                    d   = pt.get("direction","Flat")
                    arrow = "▲" if d=="Up" else "▼" if d=="Down" else "→"
                    cls   = "price-up" if d=="Up" else "price-down" if d=="Down" else ""
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
        articles = get_news(company_name, news_key)
        if articles:
            with st.spinner("Analyzing news with Claude AI…"):
                headlines = "\n".join([f"- {a['title']} ({a.get('source',{}).get('name','')})" for a in articles[:10]])
                try:
                    nd = parse_json(ask_claude(client,
                        "You are a financial analyst. Return only valid JSON, no markdown.",
                        f"""News analysis for {ticker} ({company_name}):
{headlines}

Financial context: {context[:2000]}

Respond ONLY with valid JSON:
{{
  "exciting_things": ["thing 1","thing 2","thing 3"],
  "caution_flags":   ["flag 1","flag 2","flag 3"],
  "upcoming_earnings_estimate": {{
    "date_estimate":"approximate date or quarter",
    "eps_estimate":"your EPS estimate",
    "revenue_estimate":"your revenue estimate",
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

                    ce, cc2 = st.columns(2)
                    with ce:
                        st.markdown("#### 🚀 Things to Be Excited About")
                        for pt in nd.get("exciting_things",[]): st.markdown(f"✅ {pt}")
                    with cc2:
                        st.markdown("#### 🚨 Things to Be Cautious Of")
                        for pt in nd.get("caution_flags",[]): st.markdown(f"⚠️ {pt}")

                    st.markdown("#### 📅 Upcoming Earnings Estimate")
                    ee = nd.get("upcoming_earnings_estimate",{})
                    e1,e2,e3,e4 = st.columns(4)
                    e1.metric("Est. Date",        ee.get("date_estimate","N/A"))
                    e2.metric("EPS Estimate",     ee.get("eps_estimate","N/A"))
                    e3.metric("Revenue Estimate", ee.get("revenue_estimate","N/A"))
                    pred = ee.get("beat_miss_prediction","N/A")
                    e4.markdown(f"**Beat/Meet/Miss**<br><span style='color:{'#2e7d32' if pred=='Beat' else '#c62828' if pred=='Miss' else '#f57c00'};font-size:1.3rem;font-weight:700'>{pred}</span>", unsafe_allow_html=True)
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
        div_per_share = o.get("DividendPerShare","0")
        div_yield     = o.get("DividendYield","0")
        ex_div_date   = o.get("ExDividendDate","N/A")
        div_date      = o.get("DividendDate","N/A")

        try:
            has_dividend = float(div_per_share or 0) > 0
        except:
            has_dividend = False

        if has_dividend:
            with st.spinner("Analyzing dividend with Claude AI…"):
                try:
                    dd = parse_json(ask_claude(client,
                        "You are a dividend investing expert. Return only valid JSON, no markdown.",
                        f"""Dividend analysis for {ticker} ({company_name}):
Current Price: ${current_price}
Annual Dividend/Share: ${div_per_share}
Dividend Yield: {div_yield}
Ex-Dividend Date: {ex_div_date}
Dividend Payment Date: {div_date}
P/E Ratio: {o.get('PERatio','N/A')}
Payout Ratio: {o.get('PayoutRatio','N/A')}
EPS (TTM): {o.get('EPS','N/A')}
Free Cash Flow: {data['annual_cashflow'][0].get('operatingCashflow','N/A') if data['annual_cashflow'] else 'N/A'}

{context[:1500]}

Respond ONLY with valid JSON:
{{
  "ex_dividend_date_human":"human readable date",
  "must_own_by":"date you must own by (day before ex-div)",
  "payment_date_estimate":"estimated payment date",
  "quarterly_dividend_per_share":"dollar amount",
  "annual_yield_pct":"e.g. 3.2%",
  "yield_vs_average":"Above Average|Average|Below Average",
  "dividend_safety_rating":"Very Safe|Safe|Moderate|At Risk",
  "dividend_safety_rationale":"2-3 sentences on payout ratio and cash flow coverage",
  "capture_recommendation":"Strong Buy for Dividend|Buy for Dividend|Neutral|Avoid for Dividend",
  "capture_rationale":"2-3 sentences on whether capturing the dividend makes sense",
  "dividend_growth_outlook":"Growing|Stable|At Risk of Cut",
  "key_insights":["insight 1","insight 2","insight 3"]
}}"""))

                    st.markdown(
                        f"<div class='dividend-highlight'><h4 style='margin:0 0 12px 0'>💰 Dividend Summary — {ticker}</h4>"
                        f"<table style='width:100%;border-collapse:collapse'>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Annual Dividend/Share:</td><td>${div_per_share}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Dividend Yield:</td><td>{dd.get('annual_yield_pct','N/A')}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Quarterly Per Share:</td><td>{dd.get('quarterly_dividend_per_share','N/A')}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Ex-Dividend Date:</td><td><strong>{dd.get('ex_dividend_date_human', ex_div_date)}</strong></td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>⚡ Must Own By:</td><td><strong style='color:#c62828'>{dd.get('must_own_by','N/A')}</strong></td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Payment Date:</td><td>{dd.get('payment_date_estimate', div_date)}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Payout Ratio:</td><td>{o.get('PayoutRatio','N/A')}</td></tr>"
                        f"</table></div>", unsafe_allow_html=True)

                    d1,d2,d3 = st.columns(3)
                    d1.metric("Safety Rating",    dd.get("dividend_safety_rating","N/A"))
                    d2.metric("Yield vs Average", dd.get("yield_vs_average","N/A"))
                    d3.metric("Growth Outlook",   dd.get("dividend_growth_outlook","N/A"))
                    st.markdown(f"<div class='metric-card'><strong>Safety Analysis:</strong> {dd.get('dividend_safety_rationale','')}</div>", unsafe_allow_html=True)
                    rec = dd.get("capture_recommendation","Neutral")
                    st.markdown(
                        f"<div class='metric-card'><strong>Dividend Capture Recommendation:</strong> "
                        f"<span style='color:{'#2e7d32' if 'Buy' in rec else '#c62828' if 'Avoid' in rec else '#f57c00'};font-weight:700'>{rec}</span>"
                        f"<br>{dd.get('capture_rationale','')}</div>", unsafe_allow_html=True)
                    st.markdown("#### 💡 Key Dividend Insights")
                    for ins in dd.get("key_insights",[]): st.markdown(f"• {ins}")
                    st.caption("⚠️ Always verify ex-dividend date with your broker before trading.")
                except Exception as e:
                    st.error(f"Dividend analysis error: {e}")
        else:
            st.info(f"**{company_name} ({ticker})** does not currently pay a dividend.")
            st.markdown("This company reinvests earnings for growth rather than paying dividends.")

elif analyze_btn and not ticker_input:
    st.warning("Please enter a stock ticker symbol.")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
st.caption("⚠️ For informational purposes only. Not financial advice. Always do your own research.")
