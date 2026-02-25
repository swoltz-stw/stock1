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
_poly = get_secret("POLYGON_API_KEY")
_nws  = get_secret("NEWS_API_KEY")

with st.expander("⚙️ API Keys (stored only for this session)", expanded=not _ant):
    c1, c2, c3 = st.columns(3)
    with c1: anthropic_key = st.text_input("Anthropic API Key",       value=_ant,  type="password", help="console.anthropic.com")
    with c2: poly_key      = st.text_input("Polygon.io API Key",      value=_poly, type="password", help="polygon.io — free, unlimited calls")
    with c3: news_key      = st.text_input("News API Key (optional)", value=_nws,  type="password", help="newsapi.org — free")

st.markdown("### Enter a Stock Ticker")
ci, cb = st.columns([3, 1])
with ci: ticker_input = st.text_input("Stock Ticker", placeholder="e.g. AAPL, MSFT, NVDA, TSLA", label_visibility="collapsed")
with cb: analyze_btn  = st.button("🔍 Analyze", use_container_width=True, type="primary")


# ══════════════════════════════════════════════════════════════════════════════
# POLYGON.IO DATA LAYER
# ══════════════════════════════════════════════════════════════════════════════

POLY_BASE = "https://api.polygon.io"

def poly_get(path: str, api_key: str, params: dict = None) -> dict | None:
    """Call Polygon.io API. Raises RuntimeError on auth/rate issues."""
    try:
        p = params or {}
        p["apiKey"] = api_key
        r = requests.get(f"{POLY_BASE}{path}", params=p, timeout=15)
        if r.status_code == 403:
            raise RuntimeError("Polygon.io API key is invalid or unauthorized. Please check your key.")
        if r.status_code == 429:
            raise RuntimeError("Polygon.io rate limit hit. Please wait a moment and try again.")
        if r.status_code != 200:
            raise RuntimeError(f"Polygon.io returned HTTP {r.status_code} for {path}")
        data = r.json()
        if data.get("status") == "ERROR":
            raise RuntimeError(f"Polygon.io error: {data.get('error', 'unknown')}")
        return data
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Polygon.io request failed: {e}")


def get_stock_data(ticker: str, api_key: str) -> dict:
    """Fetch all needed data from Polygon.io. Returns unified data dict."""

    # 1. Ticker details (company info, description, market cap etc.)
    details = poly_get(f"/v3/reference/tickers/{ticker}", api_key)
    if not details or not details.get("results"):
        raise RuntimeError(
            f"Could not find **{ticker}** on Polygon.io. "
            f"Please check the ticker symbol is correct (e.g. NVDA, AAPL, TSLA)."
        )
    info = details["results"]

    # 2. Previous day close (most recent price — free tier doesn't have real-time)
    prev_close = poly_get(f"/v2/aggs/ticker/{ticker}/prev", api_key)
    price_data = prev_close.get("results", [{}])[0] if prev_close and prev_close.get("results") else {}

    # 3. Snapshot (includes current price, day change, etc.)
    snapshot = poly_get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}", api_key)
    snap     = snapshot.get("ticker", {}) if snapshot else {}

    # 4. Income statements — last 8 quarters + 4 annual
    income_q = poly_get("/vX/reference/financials", api_key, {
        "ticker": ticker, "timeframe": "quarterly", "limit": 8, "sort": "period_of_report_date", "order": "desc"
    })
    income_a = poly_get("/vX/reference/financials", api_key, {
        "ticker": ticker, "timeframe": "annual", "limit": 4, "sort": "period_of_report_date", "order": "desc"
    })

    quarterly_financials = income_q.get("results", []) if income_q else []
    annual_financials    = income_a.get("results", []) if income_a else []

    # 5. Dividends
    today     = datetime.now().strftime("%Y-%m-%d")
    next_6mo  = (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d")
    past_1yr  = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    divs_upcoming = poly_get("/v3/reference/dividends", api_key, {
        "ticker": ticker, "ex_dividend_date.gte": today, "ex_dividend_date.lte": next_6mo, "limit": 5
    })
    divs_history = poly_get("/v3/reference/dividends", api_key, {
        "ticker": ticker, "ex_dividend_date.gte": past_1yr, "ex_dividend_date.lte": today, "limit": 8
    })

    upcoming_divs = divs_upcoming.get("results", []) if divs_upcoming else []
    history_divs  = divs_history.get("results",  []) if divs_history  else []

    # 6. Recent news
    news_data = poly_get("/v2/reference/news", api_key, {
        "ticker": ticker, "limit": 10, "sort": "published_utc", "order": "desc"
    })
    news_articles = news_data.get("results", []) if news_data else []

    # Derive best available price
    current_price = (
        snap.get("day", {}).get("c") or
        snap.get("prevDay", {}).get("c") or
        price_data.get("c") or
        info.get("market_cap") and None or
        "N/A"
    )
    if current_price and current_price != "N/A":
        current_price = str(round(float(current_price), 2))

    return {
        "info":                  info,
        "snap":                  snap,
        "price_data":            price_data,
        "quarterly_financials":  quarterly_financials,
        "annual_financials":     annual_financials,
        "upcoming_divs":         upcoming_divs,
        "history_divs":          history_divs,
        "news_articles":         news_articles,
        "current_price":         current_price,
        "source":                "Polygon.io",
    }


# ══════════════════════════════════════════════════════════════════════════════
# CONTEXT BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def safe_float(v, decimals=2):
    try: return round(float(v), decimals)
    except: return None

def fmt_num(v, prefix="$"):
    try:
        v = float(v)
        if abs(v) >= 1e12: return f"{prefix}{v/1e12:.2f}T"
        if abs(v) >= 1e9:  return f"{prefix}{v/1e9:.2f}B"
        if abs(v) >= 1e6:  return f"{prefix}{v/1e6:.2f}M"
        return f"{prefix}{v:,.2f}"
    except: return str(v) if v else "N/A"

def extract_financials(report: dict) -> dict:
    """Pull key line items from a Polygon financials report."""
    ic = report.get("financials", {}).get("income_statement", {})
    bs = report.get("financials", {}).get("balance_sheet", {})
    cf = report.get("financials", {}).get("cash_flow_statement", {})

    def val(d, key): return d.get(key, {}).get("value")

    return {
        "period":        report.get("end_date", "?"),
        "revenue":       val(ic, "revenues"),
        "net_income":    val(ic, "net_income_loss"),
        "gross_profit":  val(ic, "gross_profit"),
        "operating_income": val(ic, "operating_income_loss"),
        "eps_basic":     val(ic, "basic_earnings_per_share"),
        "eps_diluted":   val(ic, "diluted_earnings_per_share"),
        "operating_cf":  val(cf, "net_cash_flow_from_operating_activities"),
        "capex":         val(cf, "capital_expenditure"),
        "total_assets":  val(bs, "assets"),
        "total_debt":    val(bs, "long_term_debt"),
        "cash":          val(bs, "cash_and_equivalents"),
        "equity":        val(bs, "equity"),
    }


def build_context(data: dict, ticker: str) -> str:
    info  = data["info"]
    snap  = data["snap"]
    cp    = data["current_price"]
    pd    = data["price_data"]

    # Snap data
    day       = snap.get("day", {})
    prev_day  = snap.get("prevDay", {})
    change_pct = snap.get("todaysChangePerc")

    lines = [
        f"STOCK: {ticker.upper()} — {info.get('name', ticker)}",
        f"Sector: {info.get('sic_description','N/A')}",
        f"Description: {(info.get('description',''))[:400]}",
        f"Employees: {info.get('total_employees','N/A')} | Listed: {info.get('list_date','N/A')}",
        f"Market Cap: {fmt_num(info.get('market_cap'), '$')}",
        f"Share Class Shares Outstanding: {fmt_num(info.get('share_class_shares_outstanding',''), '')}",
        f"",
        f"── PRICE ──",
        f"Current Price: ${cp}",
        f"Today: Open=${day.get('o','N/A')} High=${day.get('h','N/A')} Low=${day.get('l','N/A')} Vol={fmt_num(day.get('v',''), '')}",
        f"Prev Close: ${prev_day.get('c', pd.get('c','N/A'))}",
        f"Today's Change: {f'{change_pct:+.2f}%' if change_pct else 'N/A'}",
        f"52-Week High: ${snap.get('day', {}).get('h','N/A')} (today high — use with context)",
        f"",
    ]

    # Quarterly financials
    lines.append("── QUARTERLY FINANCIALS (most recent 4 quarters) ──")
    for r in data["quarterly_financials"][:4]:
        f = extract_financials(r)
        lines.append(
            f"  {f['period']}: Rev={fmt_num(f['revenue'])} NetIncome={fmt_num(f['net_income'])} "
            f"GrossProfit={fmt_num(f['gross_profit'])} OperatingIncome={fmt_num(f['operating_income'])} "
            f"EPS={f['eps_diluted']} OperatingCF={fmt_num(f['operating_cf'])}"
        )

    # Annual financials
    lines.append("\n── ANNUAL FINANCIALS (most recent 4 years) ──")
    for r in data["annual_financials"][:4]:
        f = extract_financials(r)
        lines.append(
            f"  {f['period']}: Rev={fmt_num(f['revenue'])} NetIncome={fmt_num(f['net_income'])} "
            f"EPS={f['eps_diluted']} OperatingCF={fmt_num(f['operating_cf'])} "
            f"Cash={fmt_num(f['cash'])} TotalDebt={fmt_num(f['total_debt'])} Equity={fmt_num(f['equity'])}"
        )

    # Dividends
    lines.append("\n── DIVIDENDS ──")
    if data["upcoming_divs"]:
        for d in data["upcoming_divs"][:3]:
            lines.append(
                f"  UPCOMING: Ex-Date={d.get('ex_dividend_date','N/A')} "
                f"Pay-Date={d.get('pay_date','N/A')} Amount=${d.get('cash_amount','N/A')} "
                f"Frequency={d.get('frequency','N/A')}"
            )
    else:
        lines.append("  No upcoming dividends found.")
    if data["history_divs"]:
        lines.append("  Recent history:")
        for d in data["history_divs"][:4]:
            lines.append(f"    Ex-Date={d.get('ex_dividend_date','N/A')} Amount=${d.get('cash_amount','N/A')}")

    return "\n".join(str(x) for x in lines)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_news_newsapi(company: str, api_key: str) -> list:
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
    if not poly_key:
        st.error("Please enter your Polygon.io API key above. Get a free one at polygon.io")
        st.stop()

    client = anthropic.Anthropic(api_key=anthropic_key)

    with st.spinner(f"Fetching data for {ticker} from Polygon.io…"):
        try:
            data = get_stock_data(ticker, poly_key)
        except Exception as e:
            st.error("❌ Could not load stock data")
            for line in str(e).split("\n"):
                if line.strip(): st.markdown(line)
            st.stop()

    info         = data["info"]
    company_name = info.get("name", ticker)
    cp           = data["current_price"]

    st.markdown(f"## {company_name} ({ticker}) <span class='data-badge'>Polygon.io</span>", unsafe_allow_html=True)
    snap = data["snap"]
    change_pct = snap.get("todaysChangePerc")
    change_str = f" &nbsp;({change_pct:+.2f}% today)" if change_pct else ""
    st.markdown(f"**Price:** ${cp}{change_str} &nbsp;|&nbsp; **{info.get('sic_description','N/A')}**", unsafe_allow_html=True)
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

        # Use Polygon news first (already fetched, no extra API call), fallback to NewsAPI
        poly_news = data.get("news_articles", [])
        newsapi_articles = get_news_newsapi(company_name, news_key)

        # Format Polygon articles to match NewsAPI shape
        articles = []
        for a in poly_news[:10]:
            articles.append({
                "title":       a.get("title",""),
                "url":         a.get("article_url","#"),
                "description": a.get("description","") or " ".join(a.get("keywords",[])),
                "publishedAt": a.get("published_utc","")[:10],
                "source":      {"name": a.get("publisher",{}).get("name","")},
            })
        # Supplement with NewsAPI if available
        if newsapi_articles:
            articles = (articles + newsapi_articles)[:12]

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
        upcoming = data.get("upcoming_divs", [])
        history  = data.get("history_divs", [])
        next_div = upcoming[0] if upcoming else (history[0] if history else None)

        if next_div or history:
            # Calculate annual yield from history
            annual_div = sum(float(d.get("cash_amount",0)) for d in history[:4]) if history else 0
            div_yield  = round((annual_div / float(cp)) * 100, 2) if cp != "N/A" and annual_div > 0 else None

            with st.spinner("Analyzing dividend with Claude AI…"):
                try:
                    div_context = "\n".join([
                        f"  Ex-Date: {d.get('ex_dividend_date','N/A')} | Pay-Date: {d.get('pay_date','N/A')} | Amount: ${d.get('cash_amount','N/A')} | Freq: {d.get('frequency','N/A')}"
                        for d in (upcoming + history)[:6]
                    ])

                    dd = parse_json(ask_claude(client,
                        "You are a dividend investing expert. Return only valid JSON, no markdown.",
                        f"""Dividend analysis for {ticker} ({company_name}):
Current Price: ${cp}
Estimated Annual Dividend: ${annual_div:.4f}
Estimated Yield: {div_yield}%
Recent dividend records:
{div_context}

{context[:1500]}

Respond ONLY with valid JSON:
{{
  "ex_dividend_date_human":"human readable next ex-div date",
  "must_own_by":"date you must own shares by (day before ex-div)",
  "payment_date_estimate":"next payment date",
  "quarterly_dividend_per_share":"dollar amount",
  "annual_yield_pct":"e.g. 3.2%",
  "yield_vs_average":"Above Average|Average|Below Average",
  "dividend_safety_rating":"Very Safe|Safe|Moderate|At Risk",
  "dividend_safety_rationale":"2-3 sentences on safety",
  "capture_recommendation":"Strong Buy for Dividend|Buy for Dividend|Neutral|Avoid for Dividend",
  "capture_rationale":"2-3 sentences on whether capturing the dividend makes sense",
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
                        f"<tr><td style='padding:6px 0;font-weight:600'>Next Payment Date:</td><td>{dd.get('payment_date_estimate','N/A')}</td></tr>"
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
