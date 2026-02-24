import streamlit as st
import yfinance as yf
import anthropic
import requests
import json
import time
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# ── Load secrets from Streamlit Cloud if available ───────────────────────────
# This bridges st.secrets (Streamlit Cloud) and os.getenv (.env local)
def get_secret(key: str) -> str:
    try:
        val = st.secrets.get(key, "")
        if val:
            return val
    except Exception:
        pass
    return os.getenv(key, "")

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
    .sub-header { color: #666; margin-bottom: 2rem; font-size: 1rem; }
    .rating-excellent { background:#d4edda; color:#155724; border-radius:6px; padding:4px 10px; font-weight:700; display:inline-block; }
    .rating-good      { background:#cce5ff; color:#004085; border-radius:6px; padding:4px 10px; font-weight:700; display:inline-block; }
    .rating-neutral   { background:#fff3cd; color:#856404; border-radius:6px; padding:4px 10px; font-weight:700; display:inline-block; }
    .rating-bad       { background:#f8d7da; color:#721c24; border-radius:6px; padding:4px 10px; font-weight:700; display:inline-block; }
    .metric-card { background:#f8f9fa; border-radius:10px; padding:1rem 1.2rem; border-left:4px solid #1a73e8; margin-bottom:1rem; }
    .section-divider { border-top: 2px solid #e0e0e0; margin: 2rem 0; }
    .news-card { background:#f8f9fa; border-radius:8px; padding:1rem; margin-bottom:0.8rem; border-left:3px solid #1a73e8; }
    .dividend-highlight { background: linear-gradient(135deg, #e8f5e9, #c8e6c9); border-radius:10px; padding:1.2rem; border:1px solid #81c784; }
    .price-target-card { background:#fff; border:1px solid #e0e0e0; border-radius:10px; padding:1rem; text-align:center; }
    .price-up   { color: #2e7d32; font-weight: 700; }
    .price-down { color: #c62828; font-weight: 700; }
    .source-badge { font-size:0.7rem; padding:2px 8px; border-radius:10px; background:#e3f2fd; color:#1565c0; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-header">📈 Stock Evaluator AI</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Earnings analysis · Price targets · News · Dividends — powered by Claude AI</p>', unsafe_allow_html=True)

# ── API Key inputs ─────────────────────────────────────────────────────────────
_anthropic_default = get_secret("ANTHROPIC_API_KEY")
_fmp_default        = get_secret("FMP_API_KEY")
_news_default       = get_secret("NEWS_API_KEY")

with st.expander("⚙️ API Keys (required — stored only for this session)", expanded=not _anthropic_default):
    col1, col2, col3 = st.columns(3)
    with col1:
        anthropic_key = st.text_input("Anthropic API Key", value=_anthropic_default, type="password", help="Get at console.anthropic.com")
    with col2:
        fmp_key = st.text_input("FMP API Key (primary data)", value=_fmp_default, type="password", help="Free at financialmodelingprep.com — 250 req/day")
    with col3:
        news_key = st.text_input("News API Key (for news tab)", value=_news_default, type="password", help="Free at newsapi.org — 100 req/day")

# ── Diagnostics (shown when secrets appear missing) ───────────────────────────
if not _anthropic_default or not _fmp_default:
    with st.expander("🔧 Troubleshooting — click if you're seeing data errors", expanded=False):
        st.markdown("**Checking Streamlit secrets...**")
        try:
            found_keys = list(st.secrets.keys())
            if found_keys:
                st.success(f"✅ Streamlit secrets found: {found_keys}")
            else:
                st.error("❌ No secrets found. Go to: Streamlit Cloud → your app → ⋮ menu → Settings → Secrets")
        except Exception as e:
            st.error(f"❌ Could not read secrets: {e}")
        st.code('''ANTHROPIC_API_KEY = "sk-ant-api03-your-key-here"\nFMP_API_KEY = "your-fmp-key-here"\nNEWS_API_KEY = "your-newsapi-key-here"''', language="toml")
        st.caption("Paste the above (with your real keys) into Streamlit Cloud → App Settings → Secrets, then click Save.")

# ── Ticker input ──────────────────────────────────────────────────────────────
st.markdown("### Enter a Stock Ticker")
col_input, col_btn = st.columns([3, 1])
with col_input:
    ticker_input = st.text_input("Stock Ticker", placeholder="e.g. AAPL, MSFT, NVDA, TSLA", label_visibility="collapsed")
with col_btn:
    analyze_btn = st.button("🔍 Analyze", use_container_width=True, type="primary")


# ════════════════════════════════════════════════════════════════════════════
# DATA LAYER — FMP primary, yfinance fallback
# ════════════════════════════════════════════════════════════════════════════

FMP_BASE = "https://financialmodelingprep.com/api/v3"

def fmp_get(endpoint, api_key, params=None):
    if not api_key:
        return None
    p = params or {}
    p["apikey"] = api_key
    try:
        r = requests.get(f"{FMP_BASE}/{endpoint}", params=p, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and "Error Message" in data:
                return None
            return data
    except Exception:
        pass
    return None


def get_stock_data_fmp(ticker, api_key):
    if not api_key:
        return None

    profile      = fmp_get(f"profile/{ticker}", api_key)
    quote        = fmp_get(f"quote/{ticker}", api_key)
    income_a     = fmp_get(f"income-statement/{ticker}", api_key, {"limit": 4})
    income_q     = fmp_get(f"income-statement/{ticker}", api_key, {"period": "quarter", "limit": 4})
    cashflow_a   = fmp_get(f"cash-flow-statement/{ticker}", api_key, {"limit": 2})
    balance_a    = fmp_get(f"balance-sheet-statement/{ticker}", api_key, {"limit": 2})
    ratios       = fmp_get(f"ratios-ttm/{ticker}", api_key)
    price_target = fmp_get(f"price-target-consensus/{ticker}", api_key)
    dividends    = fmp_get(f"stock_dividend_calendar", api_key, {"symbol": ticker, "from": datetime.now().strftime("%Y-%m-%d"), "to": (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d")})
    earnings_cal = fmp_get(f"earning_calendar", api_key, {"symbol": ticker, "from": datetime.now().strftime("%Y-%m-%d"), "to": (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d")})

    if not profile or not isinstance(profile, list) or len(profile) == 0:
        return None

    p  = profile[0]
    q  = quote[0]   if quote   and isinstance(quote, list)   and len(quote)   > 0 else {}
    r  = ratios[0]  if ratios  and isinstance(ratios, list)  and len(ratios)  > 0 else {}
    pt = price_target[0] if price_target and isinstance(price_target, list) and len(price_target) > 0 else {}
    ia = income_a[0] if income_a and isinstance(income_a, list) and len(income_a) > 0 else {}
    ca = cashflow_a[0] if cashflow_a and isinstance(cashflow_a, list) and len(cashflow_a) > 0 else {}
    ba = balance_a[0] if balance_a and isinstance(balance_a, list) and len(balance_a) > 0 else {}
    next_div  = dividends[0]    if dividends    and isinstance(dividends, list)    and len(dividends)    > 0 else {}
    next_earn = earnings_cal[0] if earnings_cal and isinstance(earnings_cal, list) and len(earnings_cal) > 0 else {}

    info = {
        "longName":             p.get("companyName", ticker),
        "sector":               p.get("sector", "N/A"),
        "industry":             p.get("industry", "N/A"),
        "currentPrice":         q.get("price", p.get("price")),
        "fiftyTwoWeekLow":      q.get("yearLow"),
        "fiftyTwoWeekHigh":     q.get("yearHigh"),
        "marketCap":            q.get("marketCap", p.get("mktCap")),
        "trailingPE":           q.get("pe"),
        "forwardPE":            r.get("peRatioTTM"),
        "trailingEps":          q.get("eps"),
        "forwardEps":           None,
        "totalRevenue":         ia.get("revenue"),
        "grossMargins":         r.get("grossProfitMarginTTM"),
        "operatingMargins":     r.get("operatingProfitMarginTTM"),
        "profitMargins":        r.get("netProfitMarginTTM"),
        "revenueGrowth":        ia.get("revenueGrowth"),
        "earningsGrowth":       ia.get("netIncomeGrowth"),
        "beta":                 p.get("beta"),
        "dividendRate":         p.get("lastDiv"),
        "dividendYield":        (p.get("lastDiv") / p.get("price", 1)) if p.get("lastDiv") and p.get("price") else None,
        "exDividendDate":       next_div.get("date"),
        "payoutRatio":          r.get("payoutRatioTTM"),
        "fiveYearAvgDividendYield": None,
        "lastDividendValue":    next_div.get("dividend"),
        "targetMeanPrice":      pt.get("targetConsensus"),
        "targetLowPrice":       pt.get("targetLow"),
        "targetHighPrice":      pt.get("targetHigh"),
        "returnOnEquity":       r.get("returnOnEquityTTM"),
        "returnOnAssets":       r.get("returnOnAssetsTTM"),
        "debtToEquity":         r.get("debtEquityRatioTTM"),
        "freeCashflow":         ca.get("freeCashFlow"),
        "totalCash":            ba.get("cashAndCashEquivalents"),
        "totalDebt":            ba.get("totalDebt"),
        "_next_earnings_date":  next_earn.get("date",""),
        "_next_eps_estimate":   next_earn.get("epsEstimated",""),
        "_next_rev_estimate":   next_earn.get("revenueEstimated",""),
        "_quarterly_revenue":   [x.get("revenue") for x in (income_q or [])[:4]],
        "_quarterly_eps":       [x.get("eps") for x in (income_q or [])[:4]],
        "_annual_revenue":      [x.get("revenue") for x in (income_a or [])[:4]],
        "_annual_fcf":          [x.get("freeCashFlow") for x in (cashflow_a or [])[:4]],
    }
    return {"info": info, "source": "FMP"}


def get_stock_data_yfinance(ticker):
    for attempt in range(3):
        try:
            stock = yf.Ticker(ticker)
            info  = stock.info
            # yfinance returns a minimal dict with just quoteType on rate limit
            meaningful = info and len(info) > 10 and (
                info.get("regularMarketPrice") is not None or
                info.get("currentPrice") is not None or
                info.get("price") is not None
            )
            if not meaningful:
                raise ValueError(f"yfinance returned insufficient data (keys: {len(info) if info else 0}), likely rate limited")
            return {
                "info": info,
                "quarterly_financials": stock.quarterly_financials,
                "quarterly_income":     stock.quarterly_income_stmt,
                "cashflow":             stock.cashflow,
                "source": "Yahoo Finance",
            }
        except Exception as e:
            last_err = str(e)
            if attempt < 2:
                time.sleep(3 + attempt * 3)
    raise RuntimeError(f"yfinance failed after 3 attempts: {last_err}")


def get_stock_data(ticker, fmp_api_key):
    """Try FMP first, fall back to yfinance. Raises with detailed diagnostics on failure."""
    fmp_error = None
    yf_error  = None

    # Try FMP
    if fmp_api_key:
        try:
            data = get_stock_data_fmp(ticker, fmp_api_key)
            if data:
                return data
            probe = fmp_get(f"profile/{ticker}", fmp_api_key)
            if probe is None:
                fmp_error = "FMP request failed (network error or invalid key)"
            elif isinstance(probe, dict) and "Error Message" in probe:
                fmp_error = f"FMP error: {probe['Error Message']}"
            elif isinstance(probe, list) and len(probe) == 0:
                fmp_error = f"FMP returned no data for ticker — may be invalid or not on free tier"
            else:
                fmp_error = f"FMP unexpected response: {str(probe)[:150]}"
        except Exception as e:
            fmp_error = f"FMP exception: {str(e)}"
    else:
        fmp_error = "FMP key not provided"

    # Try yfinance
    try:
        data = get_stock_data_yfinance(ticker)
        if data:
            return data
        yf_error = "yfinance returned empty data after 3 attempts"
    except Exception as e:
        yf_error = f"yfinance exception: {str(e)}"

    raise RuntimeError(
        f"Could not load data for {ticker}.\n\n"
        f"FMP result: {fmp_error}\n"
        f"Yahoo Finance result: {yf_error}\n\n"
        f"Check the ticker symbol is correct (e.g. TSLA, AAPL, MSFT)."
    )


# ════════════════════════════════════════════════════════════════════════════
# CONTEXT BUILDER
# ════════════════════════════════════════════════════════════════════════════

def safe_val(val):
    try:
        if val is None: return None
        if hasattr(val, 'item'): return val.item()
        if hasattr(val, 'isoformat'): return val.isoformat()
        return val
    except Exception:
        return str(val)


def df_to_dict(df, rows=4):
    if df is None or (hasattr(df, 'empty') and df.empty):
        return {}
    try:
        subset = df.iloc[:, :rows]
        return {str(col)[:20]: {str(idx): safe_val(v) for idx, v in subset[col].items()} for col in subset.columns}
    except Exception:
        return {}


def fmt(v, prefix=""):
    if v is None: return "N/A"
    if isinstance(v, (int, float)) and abs(v) > 1_000_000:
        return f"{prefix}{v:,.0f}"
    return f"{prefix}{v}"


def build_context(data, ticker):
    info   = data["info"]
    source = data.get("source", "unknown")
    parts  = [
        f"DATA SOURCE: {source}",
        f"STOCK: {ticker.upper()} — {info.get('longName', ticker)}",
        f"Sector: {info.get('sector','N/A')} | Industry: {info.get('industry','N/A')}",
        f"Current Price: ${info.get('currentPrice', info.get('regularMarketPrice','N/A'))}",
        f"52-Week Range: ${info.get('fiftyTwoWeekLow','N/A')} – ${info.get('fiftyTwoWeekHigh','N/A')}",
        f"Market Cap: {fmt(info.get('marketCap'),'$')}",
        f"P/E (TTM): {info.get('trailingPE','N/A')} | Forward P/E: {info.get('forwardPE','N/A')}",
        f"EPS (TTM): {info.get('trailingEps','N/A')}",
        f"Revenue (Latest Annual): {fmt(info.get('totalRevenue'),'$')}",
        f"Gross Margins: {info.get('grossMargins','N/A')} | Operating Margins: {info.get('operatingMargins','N/A')} | Profit Margins: {info.get('profitMargins','N/A')}",
        f"Revenue Growth (YoY): {info.get('revenueGrowth','N/A')} | Earnings Growth: {info.get('earningsGrowth','N/A')}",
        f"Beta: {info.get('beta','N/A')}",
        f"Dividend Rate (annual): {info.get('dividendRate','N/A')} | Dividend Yield: {info.get('dividendYield','N/A')}",
        f"Ex-Dividend Date: {info.get('exDividendDate','N/A')} | Payout Ratio: {info.get('payoutRatio','N/A')}",
        f"Analyst Consensus Target: {info.get('targetMeanPrice','N/A')} (Low: {info.get('targetLowPrice','N/A')}, High: {info.get('targetHighPrice','N/A')})",
        f"Return on Equity: {info.get('returnOnEquity','N/A')} | Return on Assets: {info.get('returnOnAssets','N/A')}",
        f"Debt to Equity: {info.get('debtToEquity','N/A')}",
        f"Free Cash Flow: {fmt(info.get('freeCashflow'),'$')}",
        f"Total Cash: {fmt(info.get('totalCash'),'$')} | Total Debt: {fmt(info.get('totalDebt'),'$')}",
    ]
    if info.get("_next_earnings_date"):
        parts.append(f"Next Earnings Date: {info['_next_earnings_date']} | EPS Est: {info.get('_next_eps_estimate','N/A')} | Rev Est: {fmt(info.get('_next_rev_estimate'),'$')}")
    if info.get("_quarterly_revenue"):
        parts.append(f"Quarterly Revenue (recent 4): {info['_quarterly_revenue']}")
    if info.get("_quarterly_eps"):
        parts.append(f"Quarterly EPS (recent 4): {info['_quarterly_eps']}")
    if info.get("_annual_revenue"):
        parts.append(f"Annual Revenue (recent): {info['_annual_revenue']}")
    if info.get("_annual_fcf"):
        parts.append(f"Annual Free Cash Flow: {info['_annual_fcf']}")
    if "quarterly_financials" in data:
        parts.append("\n--- QUARTERLY FINANCIALS (yfinance) ---")
        parts.append(json.dumps(df_to_dict(data["quarterly_financials"]), indent=2))
    if "cashflow" in data:
        parts.append("\n--- CASHFLOW (yfinance) ---")
        parts.append(json.dumps(df_to_dict(data["cashflow"]), indent=2))
    return "\n".join(str(p) for p in parts)


# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════

def get_news(ticker, company_name, api_key):
    if not api_key:
        return []
    try:
        r = requests.get("https://newsapi.org/v2/everything",
            params={"q": company_name, "sortBy": "publishedAt", "pageSize": 10, "language": "en", "apiKey": api_key},
            timeout=10)
        if r.status_code == 200:
            return r.json().get("articles", [])
    except Exception:
        pass
    return []


def ask_claude(client, system_prompt, user_prompt):
    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )
    return msg.content[0].text


def parse_json_response(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def display_rating(label, rating, commentary=""):
    r = rating.lower()
    cls = "rating-excellent" if "excellent" in r else "rating-good" if "good" in r else "rating-bad" if "bad" in r else "rating-neutral"
    note = f"<br><small style='color:#555'>{commentary}</small>" if commentary else ""
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;margin-bottom:8px'>"
        f"<span style='min-width:220px;font-weight:600'>{label}</span>"
        f"<span class='{cls}'>{rating}</span>{note}</div>",
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════════════════════════════════════
# MAIN ANALYSIS
# ════════════════════════════════════════════════════════════════════════════

if analyze_btn and ticker_input:
    ticker = ticker_input.strip().upper()

    if not anthropic_key:
        st.error("Please enter your Anthropic API key in the ⚙️ API Keys section above.")
        st.stop()

    client = anthropic.Anthropic(api_key=anthropic_key)

    with st.spinner(f"Fetching data for {ticker}…"):
        try:
            data = get_stock_data(ticker, fmp_key)
        except Exception as e:
            msg = str(e)
            st.error("❌ Data fetch failed — see details below")
            for line in msg.split("\n"):
                if line.strip():
                    st.markdown(line)
            st.stop()

    info          = data["info"]
    source        = data.get("source", "Unknown")
    company_name  = info.get("longName", ticker)
    current_price = info.get("currentPrice", info.get("regularMarketPrice", "N/A"))

    st.markdown(f"## {company_name} ({ticker})")
    col_h1, col_h2, col_h3 = st.columns([2, 2, 1])
    col_h1.markdown(f"**Price:** ${current_price} &nbsp;|&nbsp; **Sector:** {info.get('sector','N/A')}")
    col_h2.markdown(f"**Industry:** {info.get('industry','N/A')}")
    col_h3.markdown(f"<span class='source-badge'>Data: {source}</span>", unsafe_allow_html=True)
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    context = build_context(data, ticker)
    tabs    = st.tabs(["📊 Earnings Analysis", "💡 Insights & Price Targets", "📰 Stock in the News", "💰 Dividends"])

    # ── Tab 1: Earnings ───────────────────────────────────────────────────────
    with tabs[0]:
        st.markdown("### Earnings Report Scorecard")
        with st.spinner("Running earnings analysis with Claude AI…"):
            try:
                earnings_data = parse_json_response(ask_claude(client,
                    "You are a financial analyst. Return only valid JSON, no markdown.",
                    f"""You are a professional equity analyst. Evaluate the latest available earnings data for {ticker} ({company_name}).

{context}

Respond ONLY with a valid JSON object (no markdown fences):
{{
  "overall_rating": "Excellent|Good|Neutral|Bad",
  "overall_summary": "2-3 sentence overall assessment",
  "categories": [
    {{"name": "Revenue Growth",          "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Profitability & Margins", "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Earnings Per Share (EPS)","rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Cash Flow Generation",    "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Balance Sheet Health",    "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Valuation",               "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Analyst Sentiment",       "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Revenue vs Expectations", "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Cost Management",         "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}},
    {{"name": "Return on Capital",       "rating": "Excellent|Good|Neutral|Bad", "commentary": "one sentence"}}
  ]
}}"""))
                overall = earnings_data.get("overall_rating", "Neutral")
                oc = "rating-excellent" if "excellent" in overall.lower() else "rating-good" if "good" in overall.lower() else "rating-bad" if "bad" in overall.lower() else "rating-neutral"
                st.markdown(f"<div class='metric-card'><strong>Overall Earnings Rating:</strong> <span class='{oc}'>{overall}</span><br><span style='color:#444'>{earnings_data.get('overall_summary','')}</span></div>", unsafe_allow_html=True)
                st.markdown("#### Category Breakdown")
                for cat in earnings_data.get("categories", []):
                    display_rating(cat["name"], cat["rating"], cat.get("commentary",""))
            except Exception as e:
                st.error(f"Could not parse earnings analysis: {e}")

    # ── Tab 2: Insights & Price Targets ───────────────────────────────────────
    with tabs[1]:
        st.markdown("### AI Insights & Price Targets")
        with st.spinner("Generating insights and price targets…"):
            try:
                insights_data = parse_json_response(ask_claude(client,
                    "You are a financial analyst. Return only valid JSON, no markdown.",
                    f"""You are a senior equity analyst with 20 years of experience.

Financial data for {ticker} ({company_name}):
{context}

Current price: ${current_price}

Respond ONLY with a valid JSON object (no markdown fences):
{{
  "what_doing_well": ["point 1", "point 2", "point 3", "point 4"],
  "risks_concerns":  ["risk 1",  "risk 2",  "risk 3"],
  "overall_outlook": "Bullish|Cautiously Bullish|Neutral|Cautiously Bearish|Bearish",
  "outlook_rationale": "3-4 sentence explanation",
  "price_targets": {{
    "next_day":     {{"target": 0.0, "direction": "Up|Down|Flat", "rationale": "brief reason"}},
    "next_week":    {{"target": 0.0, "direction": "Up|Down|Flat", "rationale": "brief reason"}},
    "next_month":   {{"target": 0.0, "direction": "Up|Down|Flat", "rationale": "brief reason"}},
    "next_quarter": {{"target": 0.0, "direction": "Up|Down|Flat", "rationale": "brief reason"}},
    "next_year":    {{"target": 0.0, "direction": "Up|Down|Flat", "rationale": "brief reason"}}
  }},
  "buy_sell_hold": "Buy|Sell|Hold",
  "conviction": "High|Medium|Low"
}}"""))

                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Outlook",        insights_data.get("overall_outlook","Neutral"))
                col_b.metric("Recommendation", insights_data.get("buy_sell_hold","Hold"))
                col_c.metric("Conviction",     insights_data.get("conviction","Medium"))
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
                periods = [("next_day","Next Day"),("next_week","Next Week"),("next_month","Next Month"),("next_quarter","Next Quarter"),("next_year","Next Year")]
                pt_cols = st.columns(5)
                for i, (key, label) in enumerate(periods):
                    pt        = pt_data.get(key, {})
                    target    = pt.get("target", 0)
                    direction = pt.get("direction","Flat")
                    arrow     = "▲" if direction=="Up" else "▼" if direction=="Down" else "→"
                    color_cls = "price-up" if direction=="Up" else "price-down" if direction=="Down" else ""
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
                            f"<div style='font-size:0.7rem;color:#888;margin-top:6px'>{pt.get('rationale','')}</div>"
                            f"</div>", unsafe_allow_html=True)
                st.caption("⚠️ AI-generated estimates for informational purposes only — not financial advice.")
            except Exception as e:
                st.error(f"Could not parse insights: {e}")

    # ── Tab 3: News ───────────────────────────────────────────────────────────
    with tabs[2]:
        st.markdown("### Stock in the News")
        articles = get_news(ticker, company_name, news_key)
        if articles:
            with st.spinner("Analyzing news with Claude AI…"):
                headlines = "\n".join([f"- {a['title']} ({a.get('source',{}).get('name','')})" for a in articles[:10]])
                try:
                    news_data = parse_json_response(ask_claude(client,
                        "You are a financial analyst. Return only valid JSON, no markdown.",
                        f"""Recent news for {ticker} ({company_name}):
{headlines}

Financial context: {context[:2000]}

Respond ONLY with valid JSON (no markdown fences):
{{
  "exciting_things": ["thing 1", "thing 2", "thing 3"],
  "caution_flags":   ["flag 1",  "flag 2",  "flag 3"],
  "upcoming_earnings_estimate": {{
    "date_estimate": "approximate date",
    "eps_estimate": "your EPS estimate",
    "revenue_estimate": "your revenue estimate",
    "beat_miss_prediction": "Beat|Meet|Miss",
    "confidence": "High|Medium|Low",
    "rationale": "2-3 sentences"
  }},
  "overall_news_sentiment": "Positive|Neutral|Negative|Mixed",
  "key_themes": ["theme 1", "theme 2", "theme 3"]
}}"""))
                    sentiment  = news_data.get("overall_news_sentiment","Neutral")
                    sent_color = "#2e7d32" if sentiment=="Positive" else "#c62828" if sentiment=="Negative" else "#f57c00"
                    st.markdown(f"**News Sentiment:** <span style='color:{sent_color};font-weight:700'>{sentiment}</span>", unsafe_allow_html=True)
                    col_e, col_c2 = st.columns(2)
                    with col_e:
                        st.markdown("#### 🚀 Things to Be Excited About")
                        for pt in news_data.get("exciting_things", []): st.markdown(f"✅ {pt}")
                    with col_c2:
                        st.markdown("#### 🚨 Things to Be Cautious Of")
                        for pt in news_data.get("caution_flags", []): st.markdown(f"⚠️ {pt}")
                    st.markdown("#### 📅 Upcoming Earnings Estimate")
                    ee = news_data.get("upcoming_earnings_estimate", {})
                    col_ee1, col_ee2, col_ee3, col_ee4 = st.columns(4)
                    col_ee1.metric("Est. Date",        ee.get("date_estimate","N/A"))
                    col_ee2.metric("EPS Estimate",     ee.get("eps_estimate","N/A"))
                    col_ee3.metric("Revenue Estimate", ee.get("revenue_estimate","N/A"))
                    pred = ee.get("beat_miss_prediction","N/A")
                    col_ee4.markdown(f"**Beat/Meet/Miss**<br><span style='color:{'#2e7d32' if pred=='Beat' else '#c62828' if pred=='Miss' else '#f57c00'};font-size:1.3rem;font-weight:700'>{pred}</span>", unsafe_allow_html=True)
                    st.markdown(f"<div class='metric-card'>{ee.get('rationale','')}</div>", unsafe_allow_html=True)
                    st.markdown("#### 🔑 Key Themes")
                    for theme in news_data.get("key_themes", []): st.markdown(f"• {theme}")
                except Exception as e:
                    st.error(f"Could not parse news analysis: {e}")

            st.markdown("#### Recent Headlines")
            for a in articles[:8]:
                desc = (a.get("description","") or "")
                st.markdown(
                    f"<div class='news-card'>"
                    f"<a href='{a.get('url','#')}' target='_blank' style='font-weight:600;color:#1a73e8;text-decoration:none'>{a.get('title','')}</a>"
                    f"<br><small style='color:#888'>{a.get('source',{}).get('name','')} · {a.get('publishedAt','')[:10]}</small>"
                    f"<br><small style='color:#555'>{desc[:150]}{'…' if len(desc)>150 else ''}</small>"
                    f"</div>", unsafe_allow_html=True)
        else:
            st.info("No news articles found. Add a News API key in ⚙️ API Keys above to enable this section.")
            st.markdown("Get a free key at [newsapi.org](https://newsapi.org)")

    # ── Tab 4: Dividends ──────────────────────────────────────────────────────
    with tabs[3]:
        st.markdown("### Dividend Analysis")
        dividend_rate  = info.get("dividendRate")
        dividend_yield = info.get("dividendYield")
        ex_div_date    = info.get("exDividendDate")
        payout_ratio   = info.get("payoutRatio")
        five_yr        = info.get("fiveYearAvgDividendYield")
        last_div       = info.get("lastDividendValue")

        if dividend_rate and float(dividend_rate) > 0:
            with st.spinner("Analyzing dividend with Claude AI…"):
                try:
                    div_data = parse_json_response(ask_claude(client,
                        "You are a dividend investing expert. Return only valid JSON, no markdown.",
                        f"""Dividend data for {ticker} ({company_name}):
Current Price: ${current_price}
Annual Dividend Rate: ${dividend_rate}
Dividend Yield: {dividend_yield}
Ex-Dividend Date: {ex_div_date}
Payout Ratio: {payout_ratio}
5-Year Average Yield: {five_yr}
Last Dividend Per Share: ${last_div}
{context[:1500]}

Respond ONLY with valid JSON (no markdown fences):
{{
  "ex_dividend_date_human": "human readable date",
  "must_own_by": "date you must own shares by",
  "payment_date_estimate": "estimated payment date",
  "quarterly_dividend_per_share": "dollar amount",
  "annual_yield_pct": "percentage e.g. 3.2%",
  "yield_vs_average": "Above Average|Average|Below Average",
  "dividend_safety_rating": "Very Safe|Safe|Moderate|At Risk",
  "dividend_safety_rationale": "2-3 sentences",
  "capture_recommendation": "Strong Buy for Dividend|Buy for Dividend|Neutral|Avoid for Dividend",
  "capture_rationale": "2-3 sentences",
  "dividend_growth_outlook": "Growing|Stable|At Risk of Cut",
  "key_insights": ["insight 1", "insight 2", "insight 3"]
}}"""))

                    st.markdown(
                        f"<div class='dividend-highlight'><h4 style='margin:0 0 12px 0'>💰 Dividend Summary for {ticker}</h4>"
                        f"<table style='width:100%;border-collapse:collapse'>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Annual Dividend Rate:</td><td>${dividend_rate}/share</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Dividend Yield:</td><td>{div_data.get('annual_yield_pct','N/A')}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Quarterly Per Share:</td><td>{div_data.get('quarterly_dividend_per_share','N/A')}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Ex-Dividend Date:</td><td><strong>{div_data.get('ex_dividend_date_human','N/A')}</strong></td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>⚡ Must Own By:</td><td><strong style='color:#c62828'>{div_data.get('must_own_by','N/A')}</strong></td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Est. Payment Date:</td><td>{div_data.get('payment_date_estimate','N/A')}</td></tr>"
                        f"<tr><td style='padding:6px 0;font-weight:600'>Payout Ratio:</td><td>{payout_ratio or 'N/A'}</td></tr>"
                        f"</table></div>", unsafe_allow_html=True)

                    col_d1, col_d2, col_d3 = st.columns(3)
                    col_d1.metric("Safety Rating",    div_data.get("dividend_safety_rating","N/A"))
                    col_d2.metric("Yield vs Average", div_data.get("yield_vs_average","N/A"))
                    col_d3.metric("Growth Outlook",   div_data.get("dividend_growth_outlook","N/A"))
                    st.markdown(f"<div class='metric-card'><strong>Safety Analysis:</strong> {div_data.get('dividend_safety_rationale','')}</div>", unsafe_allow_html=True)
                    rec = div_data.get("capture_recommendation","Neutral")
                    st.markdown(
                        f"<div class='metric-card'><strong>Dividend Capture Recommendation:</strong> "
                        f"<span style='color:{'#2e7d32' if 'Buy' in rec else '#c62828' if 'Avoid' in rec else '#f57c00'};font-weight:700'>{rec}</span>"
                        f"<br>{div_data.get('capture_rationale','')}</div>", unsafe_allow_html=True)
                    st.markdown("#### 💡 Key Dividend Insights")
                    for ins in div_data.get("key_insights", []): st.markdown(f"• {ins}")
                    st.caption("⚠️ Always verify the ex-dividend date with your broker before trading.")
                except Exception as e:
                    st.error(f"Could not parse dividend analysis: {e}")
        else:
            st.info(f"**{company_name} ({ticker})** does not currently pay a dividend.")

elif analyze_btn and not ticker_input:
    st.warning("Please enter a stock ticker symbol.")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
st.caption("⚠️ For informational and educational purposes only. Not financial advice. Always do your own research.")
