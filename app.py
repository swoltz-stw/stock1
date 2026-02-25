import streamlit as st
import anthropic
import requests
import json
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
_ant  = get_secret("ANTHROPIC_API_KEY")
_tii  = get_secret("TIINGO_API_KEY")
_nws  = get_secret("NEWS_API_KEY")

with st.expander("⚙️ API Keys (stored only for this session)", expanded=not _ant):
    c1, c2, c3 = st.columns(3)
    with c1: anthropic_key = st.text_input("Anthropic API Key",       value=_ant, type="password", help="console.anthropic.com")
    with c2: tiingo_key    = st.text_input("Tiingo API Key",          value=_tii, type="password", help="api.tiingo.com — free, 500 req/day")
    with c3: news_key      = st.text_input("News API Key (optional)", value=_nws, type="password", help="newsapi.org — free")

st.markdown("### Enter a Stock Ticker")
ci, cb = st.columns([3, 1])
with ci: ticker_input = st.text_input("Stock Ticker", placeholder="e.g. AAPL, MSFT, NVDA, TSLA", label_visibility="collapsed")
with cb: analyze_btn  = st.button("🔍 Analyze", use_container_width=True, type="primary")


# ══════════════════════════════════════════════════════════════════════════════
# TIINGO DATA LAYER
# ══════════════════════════════════════════════════════════════════════════════

TIINGO_BASE = "https://api.tiingo.com"

def tiingo_get(path: str, api_key: str, params: dict = None) -> dict | list | None:
    """Call Tiingo API."""
    try:
        headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}
        p = params or {}
        r = requests.get(f"{TIINGO_BASE}{path}", headers=headers, params=p, timeout=15)
        if r.status_code == 401:
            raise RuntimeError("Tiingo API key is invalid. Please check your key at api.tiingo.com → Account → API.")
        if r.status_code == 404:
            return None  # ticker not found
        if r.status_code == 429:
            raise RuntimeError("Tiingo rate limit reached. You have 500 requests/day on the free tier. Try again tomorrow.")
        if r.status_code != 200:
            raise RuntimeError(f"Tiingo returned HTTP {r.status_code}: {r.text[:200]}")
        return r.json()
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Tiingo request failed: {e}")


def get_stock_data(ticker: str, api_key: str) -> dict:
    """Fetch all needed data from Tiingo."""
    ticker_lower = ticker.lower()

    # 1. Ticker metadata (company name, description, exchange)
    meta = tiingo_get(f"/tiingo/daily/{ticker_lower}", api_key)
    if not meta:
        raise RuntimeError(
            f"Could not find **{ticker}** on Tiingo. "
            f"Please check the ticker symbol is correct (e.g. NVDA, AAPL, TSLA)."
        )

    # 2. Latest price data
    prices = tiingo_get(f"/tiingo/daily/{ticker_lower}/prices", api_key, {
        "startDate": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
        "endDate":   datetime.now().strftime("%Y-%m-%d"),
    })
    latest_price = prices[-1] if prices else {}

    # 3. Fundamentals — overview (P/E, market cap, EPS, margins etc.)
    fundamentals = tiingo_get(f"/tiingo/fundamentals/{ticker_lower}/statements", api_key, {
        "startDate": (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d"),
        "filter":    "quarterlyIncomeStatement,annualIncomeStatement,quarterlyBalanceSheet,annualCashFlow",
    })

    # 4. Fundamentals meta (shares outstanding, market cap etc.)
    fund_meta = tiingo_get(f"/tiingo/fundamentals/{ticker_lower}/daily", api_key, {
        "startDate": (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"),
    })
    fund_latest = fund_meta[-1] if fund_meta else {}

    # 5. News from Tiingo
    news = tiingo_get("/tiingo/news", api_key, {
        "tickers": ticker_lower,
        "limit":   10,
        "sortBy":  "publishedDate",
    })

    current_price = latest_price.get("adjClose") or latest_price.get("close")
    if current_price:
        current_price = str(round(float(current_price), 2))
    else:
        current_price = "N/A"

    # Parse financial statements
    quarterly_income = []
    annual_income    = []
    quarterly_balance = []
    annual_cashflow  = []

    if fundamentals and isinstance(fundamentals, list):
        for stmt in fundamentals:
            period_type = stmt.get("quarter")  # 0 = annual, 1-4 = quarterly
            stmt_type   = stmt.get("statementType", "")
            data_rows   = stmt.get("dataEntries", [])

            # Convert list of {name, value} to dict
            d = {row["name"]: row["value"] for row in data_rows if "name" in row and "value" in row}
            d["_date"]   = stmt.get("date", "")
            d["_quarter"] = period_type

            if "incomeStatement" in stmt_type.lower() and period_type and period_type > 0:
                quarterly_income.append(d)
            elif "incomeStatement" in stmt_type.lower() and period_type == 0:
                annual_income.append(d)
            elif "balanceSheet" in stmt_type.lower() and period_type and period_type > 0:
                quarterly_balance.append(d)
            elif "cashFlow" in stmt_type.lower() and period_type == 0:
                annual_cashflow.append(d)

    return {
        "meta":              meta,
        "latest_price":      latest_price,
        "fund_latest":       fund_latest,
        "quarterly_income":  quarterly_income[:4],
        "annual_income":     annual_income[:4],
        "quarterly_balance": quarterly_balance[:4],
        "annual_cashflow":   annual_cashflow[:2],
        "news":              news or [],
        "current_price":     current_price,
        "source":            "Tiingo",
    }


# ══════════════════════════════════════════════════════════════════════════════
# CONTEXT BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def fmt_num(v, prefix="$"):
    try:
        v = float(v)
        if abs(v) >= 1e12: return f"{prefix}{v/1e12:.2f}T"
        if abs(v) >= 1e9:  return f"{prefix}{v/1e9:.2f}B"
        if abs(v) >= 1e6:  return f"{prefix}{v/1e6:.2f}M"
        return f"{prefix}{v:,.2f}"
    except: return str(v) if v not in (None, "") else "N/A"

def build_context(data: dict, ticker: str) -> str:
    meta  = data["meta"]
    lp    = data["latest_price"]
    fl    = data["fund_latest"]
    cp    = data["current_price"]

    prev_close = lp.get("adjClose") or lp.get("close", "N/A")
    high_52w   = lp.get("adjHigh") or "N/A"
    low_52w    = lp.get("adjLow")  or "N/A"

    lines = [
        f"STOCK: {ticker.upper()} — {meta.get('name', ticker)}",
        f"Description: {(meta.get('description',''))[:400]}",
        f"Exchange: {meta.get('exchangeCode','N/A')}",
        f"",
        f"── PRICE ──",
        f"Current Price: ${cp}",
        f"Previous Close: ${prev_close}",
        f"Market Cap: {fmt_num(fl.get('marketCap'))}",
        f"EPS (TTM): {fl.get('trailingEps12m', 'N/A')}",
        f"P/E (TTM): {fl.get('peRatio', 'N/A')}",
        f"Shares Outstanding: {fmt_num(fl.get('sharesOutstanding',''), '')}",
        f"",
    ]

    # Quarterly income
    lines.append("── QUARTERLY INCOME (recent 4) ──")
    for d in data["quarterly_income"]:
        lines.append(
            f"  {d.get('_date','?')[:10]}: "
            f"Revenue={fmt_num(d.get('revenue'))} "
            f"NetIncome={fmt_num(d.get('netIncome'))} "
            f"GrossProfit={fmt_num(d.get('grossProfit'))} "
            f"OperatingIncome={fmt_num(d.get('operatingIncome'))} "
            f"EPS={d.get('eps','N/A')}"
        )

    lines.append("\n── ANNUAL INCOME (recent 4) ──")
    for d in data["annual_income"]:
        lines.append(
            f"  {d.get('_date','?')[:10]}: "
            f"Revenue={fmt_num(d.get('revenue'))} "
            f"NetIncome={fmt_num(d.get('netIncome'))} "
            f"EPS={d.get('eps','N/A')}"
        )

    lines.append("\n── ANNUAL CASH FLOW (recent 2) ──")
    for d in data["annual_cashflow"]:
        lines.append(
            f"  {d.get('_date','?')[:10]}: "
            f"OperatingCF={fmt_num(d.get('netCashFromOperatingActivities'))} "
            f"CapEx={fmt_num(d.get('capitalExpenditures'))} "
            f"FreeCF={fmt_num(d.get('freeCashFlow'))}"
        )

    lines.append("\n── BALANCE SHEET (recent) ──")
    for d in data["quarterly_balance"][:2]:
        lines.append(
            f"  {d.get('_date','?')[:10]}: "
            f"TotalAssets={fmt_num(d.get('totalAssets'))} "
            f"TotalDebt={fmt_num(d.get('totalDebt'))} "
            f"Cash={fmt_num(d.get('cashAndEquivalents'))} "
            f"Equity={fmt_num(d.get('totalEquity'))}"
        )

    return "\n".join(str(x) for x in lines)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_newsapi_articles(company: str, api_key: str) -> list:
    if not api_key: return []
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
    if not tiingo_key:
        st.error("Please enter your Tiingo API key. Get a free one at api.tiingo.com → Sign Up → Account → API.")
        st.stop()

    client = anthropic.Anthropic(api_key=anthropic_key)

    with st.spinner(f"Fetching data for {ticker} from Tiingo…"):
        try:
            data = get_stock_data(ticker, tiingo_key)
        except Exception as e:
            st.error("❌ Could not load stock data")
            for line in str(e).split("\n"):
                if line.strip(): st.markdown(line)
            st.stop()

    meta         = data["meta"]
    company_name = meta.get("name", ticker)
    cp           = data["current_price"]

    st.markdown(f"## {company_name} ({ticker}) <span class='data-badge'>Tiingo</span>", unsafe_allow_html=True)
    st.markdown(f"**Price:** ${cp} &nbsp;|&nbsp; **Exchange:** {meta.get('exchangeCode','N/A')}", unsafe_allow_html=True)
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
                    f"<span class='{rcls(overall)}'>{overall}</span><br>"
                    f"<span style='color:#444'>{ed.get('overall_summary','')}</span></div>",
                    unsafe_allow_html=True)
                st.markdown("#### Category Breakdown")
                for cat in ed.get("categories",[]):
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
Current price: ${cp}

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
                ca.metric("Outlook",         ins.get("overall_outlook","Neutral"))
                cb2.metric("Recommendation", ins.get("buy_sell_hold","Hold"))
                cc.metric("Conviction",      ins.get("conviction","Medium"))
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
                    pt    = ins.get("price_targets",{}).get(key,{})
                    tgt   = pt.get("target",0)
                    d     = pt.get("direction","Flat")
                    arrow = "▲" if d=="Up" else "▼" if d=="Down" else "→"
                    cls   = "price-up" if d=="Up" else "price-down" if d=="Down" else ""
                    try:
                        pct = ((float(tgt)-float(cp))/float(cp))*100
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

        # Tiingo news (already fetched, no extra API call)
        articles = []
        for a in data.get("news", []):
            articles.append({
                "title":       a.get("title",""),
                "url":         a.get("url","#"),
                "description": a.get("description",""),
                "publishedAt": (a.get("publishedDate","") or "")[:10],
                "source":      {"name": a.get("source","")},
            })

        # Supplement with NewsAPI if key provided
        if news_key:
            extra = get_newsapi_articles(company_name, news_key)
            articles = (articles + extra)[:12]

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
            st.info("No news found for this ticker.")

    # ── Tab 4: Dividends ──────────────────────────────────────────────────────
    with tabs[3]:
        st.markdown("### Dividend Analysis")

        # Fetch dividend data from Tiingo
        try:
            today    = datetime.now().strftime("%Y-%m-%d")
            past_2yr = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
            div_data = tiingo_get(f"/tiingo/daily/{ticker.lower()}/dividends", tiingo_key, {
                "startDate": past_2yr, "endDate": today
            })
        except Exception:
            div_data = []

        recent_divs = sorted(div_data or [], key=lambda x: x.get("exDate",""), reverse=True)[:8]
        has_dividend = len(recent_divs) > 0 and any(float(d.get("divCash",0)) > 0 for d in recent_divs)

        if has_dividend:
            # Calculate annualized dividend from recent payments
            last_4 = [float(d.get("divCash",0)) for d in recent_divs[:4]]
            annual_div = sum(last_4)
            div_yield  = round((annual_div / float(cp)) * 100, 2) if cp != "N/A" and annual_div > 0 else 0
            next_div   = recent_divs[0]

            with st.spinner("Analyzing dividend with Claude AI…"):
                try:
                    div_history_str = "\n".join([
                        f"  Ex-Date: {d.get('exDate','N/A')} | Amount: ${d.get('divCash','N/A')}"
                        for d in recent_divs[:6]
                    ])

                    dd = parse_json(ask_claude(client,
                        "You are a dividend investing expert. Return only valid JSON, no markdown.",
                        f"""Dividend analysis for {ticker} ({company_name}):
Current Price: ${cp}
Estimated Annual Dividend: ${annual_div:.4f}
Estimated Yield: {div_yield}%
Most recent ex-dividend date: {next_div.get('exDate','N/A')}
Most recent dividend amount: ${next_div.get('divCash','N/A')}
Recent dividend history:
{div_history_str}

{context[:1500]}

Respond ONLY with valid JSON:
{{
  "ex_dividend_date_human":"most recent or next expected ex-div date in plain English",
  "must_own_by":"date you must own shares by",
  "payment_date_estimate":"estimated next payment date",
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
                        f"<tr><td style='padding:6px 0;font-weight:600'>Est. Annual Dividend:</td><td>${annual_div:.4f}/share</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Est. Dividend Yield:</td><td>{dd.get('annual_yield_pct','N/A')}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Quarterly Per Share:</td><td>{dd.get('quarterly_dividend_per_share','N/A')}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Next Ex-Dividend Date:</td><td><strong>{dd.get('ex_dividend_date_human','N/A')}</strong></td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>⚡ Must Own By:</td><td><strong style='color:#c62828'>{dd.get('must_own_by','N/A')}</strong></td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Est. Payment Date:</td><td>{dd.get('payment_date_estimate','N/A')}</td></tr>"
                        f"</table></div>", unsafe_allow_html=True)

                    d1,d2,d3 = st.columns(3)
                    d1.metric("Safety Rating",    dd.get("dividend_safety_rating","N/A"))
                    d2.metric("Yield vs Average", dd.get("yield_vs_average","N/A"))
                    d3.metric("Growth Outlook",   dd.get("dividend_growth_outlook","N/A"))
                    st.markdown(f"<div class='metric-card'><strong>Safety Analysis:</strong> {dd.get('dividend_safety_rationale','')}</div>", unsafe_allow_html=True)
                    rec = dd.get("capture_recommendation","Neutral")
                    st.markdown(
                        f"<div class='metric-card'><strong>Capture Recommendation:</strong> "
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
