import streamlit as st
import anthropic
import requests
import json
import os
import math
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def get_secret(key):
    try:
        val = st.secrets.get(key, "")
        if val: return val
    except: pass
    return os.getenv(key, "")

st.set_page_config(page_title="Stock Evaluator AI", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .main-header { font-size:2.5rem; font-weight:800; background:linear-gradient(90deg,#1a73e8,#0d47a1);
        -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:0.2rem; }
    .sub-header { color:#666; margin-bottom:1rem; font-size:1rem; }
    .rating-excellent { background:#d4edda; color:#155724; border-radius:6px; padding:3px 8px; font-weight:700; display:inline-block; font-size:0.8rem; }
    .rating-good      { background:#cce5ff; color:#004085; border-radius:6px; padding:3px 8px; font-weight:700; display:inline-block; font-size:0.8rem; }
    .rating-neutral   { background:#fff3cd; color:#856404; border-radius:6px; padding:3px 8px; font-weight:700; display:inline-block; font-size:0.8rem; }
    .rating-bad       { background:#f8d7da; color:#721c24; border-radius:6px; padding:3px 8px; font-weight:700; display:inline-block; font-size:0.8rem; }
    .metric-card { background:#f8f9fa; border-radius:10px; padding:1rem 1.2rem; border-left:4px solid #1a73e8; margin-bottom:1rem; }
    .section-divider { border-top:2px solid #e0e0e0; margin:2rem 0; }
    .news-card { background:#f8f9fa; border-radius:8px; padding:1rem; margin-bottom:0.8rem; border-left:3px solid #1a73e8; }
    .dividend-highlight { background:linear-gradient(135deg,#e8f5e9,#c8e6c9); border-radius:10px; padding:1.2rem; border:1px solid #81c784; }
    .price-target-card { background:#fff; border:1px solid #e0e0e0; border-radius:10px; padding:1rem; text-align:center; }
    .price-up   { color:#2e7d32; font-weight:700; }
    .price-down { color:#c62828; font-weight:700; }
    .data-badge { font-size:0.72rem; padding:2px 10px; border-radius:10px; background:#e8f0fe; color:#1a73e8; font-weight:600; display:inline-block; margin-left:8px; }
    .insider-buy  { color:#2e7d32; font-weight:700; }
    .insider-sell { color:#c62828; font-weight:700; }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">📈 Stock Evaluator AI</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Earnings · Price Targets · Screener · Backtesting · Technicals · Peers · Insiders</p>', unsafe_allow_html=True)

# ── API Keys ──────────────────────────────────────────────────────────────────
_ant = get_secret("ANTHROPIC_API_KEY")
_tii = get_secret("TIINGO_API_KEY")
_nws = get_secret("NEWS_API_KEY")

with st.expander("⚙️ API Keys", expanded=not _ant):
    c1,c2,c3 = st.columns(3)
    with c1: anthropic_key = st.text_input("Anthropic API Key", value=_ant, type="password")
    with c2: tiingo_key    = st.text_input("Tiingo API Key",    value=_tii, type="password", help="api.tiingo.com — free")
    with c3: news_key      = st.text_input("News API Key",      value=_nws, type="password", help="newsapi.org — free")

# ══════════════════════════════════════════════════════════════════════════════
# INDEX CONSTITUENTS
# ══════════════════════════════════════════════════════════════════════════════
DOW30 = ["AAPL","AMGN","AXP","BA","CAT","CRM","CSCO","CVX","DIS","DOW",
         "GS","HD","HON","IBM","INTC","JNJ","JPM","KO","MCD","MMM",
         "MRK","MSFT","NKE","PG","TRV","UNH","V","VZ","WBA","WMT"]

NASDAQ100 = ["AAPL","ABNB","ADBE","ADI","ADP","ADSK","AEP","AMAT","AMD","AMGN",
             "AMZN","ANSS","APP","ARM","ASML","AVGO","AZN","BIIB","BKNG","BKR",
             "CCEP","CDNS","CDW","CEG","CMCSA","COST","CPRT","CRWD","CSCO","CSGP",
             "CSX","CTAS","CTSH","DASH","DDOG","DLTR","DXCM","EA","EXC","FANG",
             "FAST","FTNT","GEHC","GFS","GILD","GOOG","GOOGL","HON","IDXX","ILMN",
             "INTC","INTU","ISRG","KDP","KHC","KLAC","LIN","LRCX","LULU","MAR",
             "MCHP","MDB","MDLZ","META","MNST","MRNA","MRVL","MSFT","MU","NFLX",
             "NVDA","NXPI","ODFL","ON","ORLY","PANW","PAYX","PCAR","PDD","PEP",
             "PYPL","QCOM","REGN","ROP","ROST","SBUX","SMCI","SNPS","TEAM","TMUS",
             "TSLA","TTD","TTWO","TXN","VRSK","VRTX","WBA","WBD","WDAY","XEL","ZS"]

SP500_SAMPLE = ["AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","BRK.B","UNH","LLY",
                "JPM","V","XOM","MA","AVGO","PG","HD","COST","MRK","CVX",
                "ABBV","KO","PEP","WMT","BAC","CRM","ACN","MCD","NFLX","TMO",
                "CSCO","ABT","LIN","DHR","ADBE","TXN","WFC","PM","NEE","ORCL",
                "RTX","HON","AMGN","INTU","IBM","AMD","QCOM","CAT","GE","SPGI",
                "LOW","ISRG","BKNG","T","GS","ELV","BLK","PFE","SYK","GILD",
                "AXP","BA","MDLZ","TJX","VRTX","MMC","C","DUK","SO","PLD",
                "ZTS","ADP","CB","CI","MO","REGN","CME","AON","SCHW","BSX",
                "ETN","NOC","HUM","ITW","CL","FI","ICE","WM","MCK","NSC"]

# ══════════════════════════════════════════════════════════════════════════════
# TIINGO API
# ══════════════════════════════════════════════════════════════════════════════
TIINGO_BASE = "https://api.tiingo.com"

def tiingo_get(path, api_key, params=None):
    try:
        headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}
        r = requests.get(f"{TIINGO_BASE}{path}", headers=headers, params=params or {}, timeout=15)
        if r.status_code == 401: raise RuntimeError("Tiingo API key invalid. Check api.tiingo.com → Account → API.")
        if r.status_code == 403: raise RuntimeError(f"Tiingo 403: {r.text[:200]}")
        if r.status_code == 404: return None
        if r.status_code == 429: raise RuntimeError("Tiingo rate limit hit. Try again shortly.")
        if r.status_code != 200: raise RuntimeError(f"Tiingo HTTP {r.status_code}: {r.text[:200]}")
        return r.json()
    except RuntimeError: raise
    except Exception as e: raise RuntimeError(f"Tiingo request failed: {e}")

def tiingo_get_safe(path, api_key, params=None):
    """Silent version — returns None instead of raising."""
    try: return tiingo_get(path, api_key, params)
    except: return None

def get_stock_data(ticker, api_key):
    t = ticker.lower()
    meta = tiingo_get(f"/tiingo/daily/{t}", api_key)
    if not meta:
        raise RuntimeError(f"Ticker **{ticker}** not found on Tiingo. Check the symbol.")

    prices = tiingo_get(f"/tiingo/daily/{t}/prices", api_key, {
        "startDate": (datetime.now()-timedelta(days=5)).strftime("%Y-%m-%d"),
        "endDate":   datetime.now().strftime("%Y-%m-%d"),
    })
    latest = prices[-1] if prices else {}

    fund_latest = {}
    try:
        fm = tiingo_get_safe(f"/tiingo/fundamentals/{t}/daily", api_key, {
            "startDate": (datetime.now()-timedelta(days=10)).strftime("%Y-%m-%d")
        })
        fund_latest = fm[-1] if fm else {}
    except: pass

    q_income, a_income, q_balance, a_cashflow = [], [], [], []
    try:
        stmts = tiingo_get_safe(f"/tiingo/fundamentals/{t}/statements", api_key, {
            "startDate": (datetime.now()-timedelta(days=730)).strftime("%Y-%m-%d"),
            "filter": "quarterlyIncomeStatement,annualIncomeStatement,quarterlyBalanceSheet,annualCashFlow",
        })
        if stmts:
            for s in stmts:
                pt = s.get("quarter")
                st_type = s.get("statementType","")
                d = {r["name"]: r["value"] for r in s.get("dataEntries",[]) if "name" in r}
                d["_date"] = s.get("date","")
                d["_quarter"] = pt
                if "incomeStatement" in st_type.lower() and pt and pt > 0: q_income.append(d)
                elif "incomeStatement" in st_type.lower() and pt == 0: a_income.append(d)
                elif "balanceSheet" in st_type.lower() and pt and pt > 0: q_balance.append(d)
                elif "cashFlow" in st_type.lower() and pt == 0: a_cashflow.append(d)
    except: pass

    news = []
    try:
        n = tiingo_get_safe("/tiingo/news", api_key, {"tickers": t, "limit": 10, "sortBy": "publishedDate"})
        news = n or []
    except: pass

    cp = latest.get("adjClose") or latest.get("close")
    cp = str(round(float(cp), 2)) if cp else "N/A"

    return {
        "meta": meta, "latest_price": latest, "fund_latest": fund_latest,
        "quarterly_income": q_income[:4], "annual_income": a_income[:4],
        "quarterly_balance": q_balance[:4], "annual_cashflow": a_cashflow[:2],
        "news": news, "current_price": cp, "source": "Tiingo",
    }

def get_historical_prices(ticker, start_date, end_date, api_key):
    t = ticker.lower()
    data = tiingo_get_safe(f"/tiingo/daily/{t}/prices", api_key, {
        "startDate": start_date, "endDate": end_date,
        "resampleFreq": "daily",
    })
    return data or []

def get_screener_data(ticker, api_key):
    """Lightweight fetch for screener — just price + basic info."""
    t = ticker.lower()
    try:
        prices = tiingo_get_safe(f"/tiingo/daily/{t}/prices", api_key, {
            "startDate": (datetime.now()-timedelta(days=365)).strftime("%Y-%m-%d"),
            "endDate":   datetime.now().strftime("%Y-%m-%d"),
        })
        if not prices: return None
        latest = prices[-1]
        year_ago = prices[0]
        cp = latest.get("adjClose") or latest.get("close") or 0
        yr_ago_p = year_ago.get("adjClose") or year_ago.get("close") or cp

        # 52-week high/low
        all_closes = [p.get("adjClose") or p.get("close") or 0 for p in prices]
        high_52w = max(all_closes) if all_closes else 0
        low_52w  = min(all_closes) if all_closes else 0

        # RSI (14-day)
        rsi = calc_rsi([p.get("adjClose") or p.get("close") or 0 for p in prices[-15:]])

        # Moving averages
        ma50  = calc_ma(all_closes, 50)
        ma200 = calc_ma(all_closes, 200)

        # Dividends
        divs = tiingo_get_safe(f"/tiingo/daily/{t}/dividends", api_key, {
            "startDate": (datetime.now()-timedelta(days=400)).strftime("%Y-%m-%d"),
            "endDate":   (datetime.now()+timedelta(days=180)).strftime("%Y-%m-%d"),
        })
        div_list = sorted(divs or [], key=lambda x: x.get("exDate",""), reverse=True)
        annual_div = sum(float(d.get("divCash",0)) for d in div_list[:4])
        div_yield  = round((annual_div / float(cp)) * 100, 2) if cp and annual_div > 0 else 0
        next_ex    = next((d.get("exDate","") for d in div_list if d.get("exDate","") >= datetime.now().strftime("%Y-%m-%d")), "")
        last_ex    = div_list[0].get("exDate","") if div_list else ""

        perf_1yr = round(((float(cp) - float(yr_ago_p)) / float(yr_ago_p)) * 100, 1) if yr_ago_p else 0

        # Score 0-100 based on: momentum, RSI zone, MA position
        score = calc_screener_score(cp, ma50, ma200, rsi, perf_1yr, div_yield)

        return {
            "ticker": ticker, "price": round(float(cp),2),
            "perf_1yr": perf_1yr,
            "high_52w": round(high_52w,2), "low_52w": round(low_52w,2),
            "ma50": round(ma50,2) if ma50 else None,
            "ma200": round(ma200,2) if ma200 else None,
            "rsi": round(rsi,1) if rsi else None,
            "div_yield": div_yield, "annual_div": round(annual_div,4),
            "next_ex_div": next_ex[:10] if next_ex else "",
            "last_ex_div": last_ex[:10] if last_ex else "",
            "score": score,
        }
    except: return None

# ══════════════════════════════════════════════════════════════════════════════
# TECHNICAL CALCULATIONS
# ══════════════════════════════════════════════════════════════════════════════

def calc_rsi(prices, period=14):
    if len(prices) < period+1: return None
    gains, losses = [], []
    for i in range(1, len(prices)):
        d = prices[i] - prices[i-1]
        gains.append(max(d,0)); losses.append(max(-d,0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1+rs))

def calc_ma(prices, period):
    if len(prices) < period: return None
    return sum(prices[-period:]) / period

def calc_macd(prices):
    if len(prices) < 26: return None, None, None
    def ema(p, n):
        k = 2/(n+1); e = p[0]
        for x in p[1:]: e = x*k + e*(1-k)
        return e
    ema12 = ema(prices[-26:], 12)
    ema26 = ema(prices[-26:], 26)
    macd_line = ema12 - ema26
    signal = ema(prices[-9:], 9) if len(prices) >= 9 else macd_line
    histogram = macd_line - signal
    return round(macd_line,4), round(signal,4), round(histogram,4)

def calc_screener_score(price, ma50, ma200, rsi, perf_1yr, div_yield):
    score = 50
    if ma50 and price > ma50: score += 10
    if ma200 and price > ma200: score += 10
    if rsi:
        if 40 <= rsi <= 60: score += 10
        elif rsi < 30: score += 5   # oversold — potential opportunity
        elif rsi > 70: score -= 5   # overbought
    if perf_1yr > 20: score += 15
    elif perf_1yr > 0: score += 8
    elif perf_1yr < -20: score -= 10
    if div_yield > 3: score += 5
    elif div_yield > 1: score += 2
    return min(max(score, 0), 100)

def score_label(s):
    if s >= 75: return "🟢 Strong"
    if s >= 60: return "🟡 Good"
    if s >= 45: return "🟠 Neutral"
    return "🔴 Weak"

# ══════════════════════════════════════════════════════════════════════════════
# CONTEXT & CLAUDE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def fmt_num(v, prefix="$"):
    try:
        v = float(v)
        if abs(v) >= 1e12: return f"{prefix}{v/1e12:.2f}T"
        if abs(v) >= 1e9:  return f"{prefix}{v/1e9:.2f}B"
        if abs(v) >= 1e6:  return f"{prefix}{v/1e6:.2f}M"
        return f"{prefix}{v:,.2f}"
    except: return str(v) if v not in (None,"") else "N/A"

def build_context(data, ticker):
    meta = data["meta"]; lp = data["latest_price"]; fl = data["fund_latest"]; cp = data["current_price"]
    lines = [
        f"STOCK: {ticker.upper()} — {meta.get('name',ticker)}",
        f"Description: {meta.get('description','')[:300]}",
        f"Exchange: {meta.get('exchangeCode','N/A')}",
        f"Current Price: ${cp}",
        f"Prev Close: {lp.get('adjClose','N/A')} | Open: {lp.get('open','N/A')} | High: {lp.get('high','N/A')} | Low: {lp.get('low','N/A')} | Vol: {lp.get('volume','N/A')}",
    ]
    if fl:
        lines += [f"Market Cap: {fmt_num(fl.get('marketCap'))}", f"P/E: {fl.get('peRatio','N/A')}", f"EPS TTM: {fl.get('trailingEps12m','N/A')}"]
    has_stmts = bool(data.get("quarterly_income") or data.get("annual_income"))
    if has_stmts:
        lines.append("\n── QUARTERLY INCOME ──")
        for d in data["quarterly_income"]:
            lines.append(f"  {d.get('_date','')[:10]}: Rev={fmt_num(d.get('revenue'))} NI={fmt_num(d.get('netIncome'))} EPS={d.get('eps','N/A')}")
        lines.append("── ANNUAL INCOME ──")
        for d in data["annual_income"]:
            lines.append(f"  {d.get('_date','')[:10]}: Rev={fmt_num(d.get('revenue'))} NI={fmt_num(d.get('netIncome'))} EPS={d.get('eps','N/A')}")
    else:
        lines.append("\nNOTE: Detailed financials unavailable. Use your training knowledge for this company's recent earnings, revenue, margins, and EPS.")
    return "\n".join(str(x) for x in lines)

def ask_claude(client, system, prompt):
    msg = client.messages.create(model="claude-opus-4-6", max_tokens=4096,
        system=system, messages=[{"role":"user","content":prompt}])
    return msg.content[0].text

def parse_json(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    return json.loads(raw.strip())

def rcls(r):
    r = r.lower()
    return "rating-excellent" if "excellent" in r else "rating-good" if "good" in r else "rating-bad" if "bad" in r else "rating-neutral"

def display_rating(label, rating, commentary=""):
    note = f"<br><small style='color:#555'>{commentary}</small>" if commentary else ""
    st.markdown(f"<div style='display:flex;align-items:center;gap:12px;margin-bottom:8px'>"
        f"<span style='min-width:220px;font-weight:600'>{label}</span>"
        f"<span class='{rcls(rating)}'>{rating}</span>{note}</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# NAVIGATION
# ══════════════════════════════════════════════════════════════════════════════

page = st.radio("", ["🔍 Stock Analysis", "📋 Index Screener", "📈 Backtester", "🔧 Technical Analysis", "🏢 Peer Comparison", "📅 Earnings Calendar", "🕵️ Insider Activity"],
    horizontal=True, label_visibility="collapsed")
st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: STOCK ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
if page == "🔍 Stock Analysis":
    ci, cb = st.columns([3,1])
    with ci: ticker_input = st.text_input("Stock Ticker", placeholder="e.g. AAPL, MSFT, NVDA, TSLA", label_visibility="collapsed")
    with cb: analyze_btn  = st.button("🔍 Analyze", use_container_width=True, type="primary")

    if analyze_btn and ticker_input:
        ticker = ticker_input.strip().upper()
        if not anthropic_key: st.error("Anthropic API key required."); st.stop()
        if not tiingo_key:    st.error("Tiingo API key required."); st.stop()
        client = anthropic.Anthropic(api_key=anthropic_key)

        with st.spinner(f"Fetching {ticker} from Tiingo…"):
            try: data = get_stock_data(ticker, tiingo_key)
            except Exception as e:
                st.error("❌ Could not load stock data")
                for l in str(e).split("\n"):
                    if l.strip(): st.markdown(l)
                st.stop()

        meta = data["meta"]; cp = data["current_price"]; company_name = meta.get("name", ticker)
        st.markdown(f"## {company_name} ({ticker}) <span class='data-badge'>Tiingo</span>", unsafe_allow_html=True)
        st.markdown(f"**Price:** ${cp} &nbsp;|&nbsp; **Exchange:** {meta.get('exchangeCode','N/A')}", unsafe_allow_html=True)
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        context = build_context(data, ticker)
        tabs = st.tabs(["📊 Earnings", "💡 Insights & Targets", "📰 News", "💰 Dividends"])

        with tabs[0]:
            st.markdown("### Earnings Report Scorecard")
            with st.spinner("Analyzing with Claude…"):
                try:
                    ed = parse_json(ask_claude(client, "You are a financial analyst. Return only valid JSON, no markdown.",
                        f"""Evaluate latest earnings for {ticker} ({company_name}).\n{context}\n
Respond ONLY with valid JSON:
{{"overall_rating":"Excellent|Good|Neutral|Bad","overall_summary":"2-3 sentences","categories":[
{{"name":"Revenue Growth","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"}},
{{"name":"Profitability & Margins","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"}},
{{"name":"Earnings Per Share","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"}},
{{"name":"Cash Flow Generation","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"}},
{{"name":"Balance Sheet Health","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"}},
{{"name":"Valuation","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"}},
{{"name":"Analyst Sentiment","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"}},
{{"name":"Revenue vs Expectations","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"}},
{{"name":"Cost Management","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"}},
{{"name":"Return on Capital","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"}}]}}"""))
                    overall = ed.get("overall_rating","Neutral")
                    st.markdown(f"<div class='metric-card'><strong>Overall:</strong> <span class='{rcls(overall)}'>{overall}</span><br><span style='color:#444'>{ed.get('overall_summary','')}</span></div>", unsafe_allow_html=True)
                    for cat in ed.get("categories",[]): display_rating(cat["name"], cat["rating"], cat.get("commentary",""))
                except Exception as e: st.error(f"Error: {e}")

        with tabs[1]:
            st.markdown("### AI Insights & Price Targets")
            with st.spinner("Generating insights…"):
                try:
                    ins = parse_json(ask_claude(client, "You are a financial analyst. Return only valid JSON, no markdown.",
                        f"""Senior analyst view on {ticker} ({company_name}). Current price: ${cp}.\n{context}\n
Respond ONLY with valid JSON:
{{"what_doing_well":["p1","p2","p3","p4"],"risks_concerns":["r1","r2","r3"],
"overall_outlook":"Bullish|Cautiously Bullish|Neutral|Cautiously Bearish|Bearish",
"outlook_rationale":"3-4 sentences",
"price_targets":{{"next_day":{{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"}},
"next_week":{{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"}},
"next_month":{{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"}},
"next_quarter":{{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"}},
"next_year":{{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"}}}},
"buy_sell_hold":"Buy|Sell|Hold","conviction":"High|Medium|Low"}}"""))
                    ca,cb2,cc = st.columns(3)
                    ca.metric("Outlook", ins.get("overall_outlook","N/A"))
                    cb2.metric("Recommendation", ins.get("buy_sell_hold","N/A"))
                    cc.metric("Conviction", ins.get("conviction","N/A"))
                    st.markdown(f"<div class='metric-card'>{ins.get('outlook_rationale','')}</div>", unsafe_allow_html=True)
                    cl,cr = st.columns(2)
                    with cl:
                        st.markdown("#### ✅ Doing Well"); [st.markdown(f"• {p}") for p in ins.get("what_doing_well",[])]
                    with cr:
                        st.markdown("#### ⚠️ Risks"); [st.markdown(f"• {p}") for p in ins.get("risks_concerns",[])]
                    st.markdown("#### 🎯 Price Targets")
                    periods = [("next_day","Next Day"),("next_week","Next Week"),("next_month","Next Month"),("next_quarter","Next Quarter"),("next_year","Next Year")]
                    ptc = st.columns(5)
                    for i,(key,label) in enumerate(periods):
                        pt = ins.get("price_targets",{}).get(key,{}); tgt = pt.get("target",0); d = pt.get("direction","Flat")
                        arrow = "▲" if d=="Up" else "▼" if d=="Down" else "→"
                        cls = "price-up" if d=="Up" else "price-down" if d=="Down" else ""
                        try: pct_str = f"{((float(tgt)-float(cp))/float(cp))*100:+.1f}%"
                        except: pct_str = ""
                        with ptc[i]:
                            st.markdown(f"<div class='price-target-card'><div style='font-size:0.8rem;color:#666'>{label}</div>"
                                f"<div style='font-size:1.4rem;font-weight:800'>${tgt:.2f}</div>"
                                f"<div class='{cls}'>{arrow} {pct_str}</div>"
                                f"<div style='font-size:0.7rem;color:#888'>{pt.get('rationale','')}</div></div>", unsafe_allow_html=True)
                    st.caption("⚠️ AI-generated — not financial advice.")
                except Exception as e: st.error(f"Error: {e}")

        with tabs[2]:
            st.markdown("### Stock in the News")
            articles = []
            for a in data.get("news",[]):
                articles.append({"title":a.get("title",""),"url":a.get("url","#"),
                    "description":a.get("description",""),"publishedAt":(a.get("publishedDate","") or "")[:10],
                    "source":{"name":a.get("source","")}})
            if news_key:
                try:
                    r = requests.get("https://newsapi.org/v2/everything",
                        params={"q":company_name,"sortBy":"publishedAt","pageSize":10,"language":"en","apiKey":news_key},timeout=10)
                    if r.status_code==200: articles += r.json().get("articles",[])
                except: pass
            if articles:
                with st.spinner("Analyzing news…"):
                    try:
                        headlines = "\n".join([f"- {a['title']}" for a in articles[:10]])
                        nd = parse_json(ask_claude(client, "Financial analyst. Return only valid JSON.",
                            f"""News for {ticker}: {headlines}\nContext: {context[:1500]}\n
Respond with JSON: {{"exciting_things":["t1","t2","t3"],"caution_flags":["f1","f2","f3"],
"upcoming_earnings_estimate":{{"date_estimate":"date","eps_estimate":"est","revenue_estimate":"rev",
"beat_miss_prediction":"Beat|Meet|Miss","confidence":"High|Medium|Low","rationale":"2-3 sentences"}},
"overall_news_sentiment":"Positive|Neutral|Negative|Mixed","key_themes":["t1","t2","t3"]}}"""))
                        sent = nd.get("overall_news_sentiment","Neutral")
                        sc = "#2e7d32" if sent=="Positive" else "#c62828" if sent=="Negative" else "#f57c00"
                        st.markdown(f"**Sentiment:** <span style='color:{sc};font-weight:700'>{sent}</span>", unsafe_allow_html=True)
                        ce,cc2 = st.columns(2)
                        with ce:
                            st.markdown("#### 🚀 Exciting"); [st.markdown(f"✅ {p}") for p in nd.get("exciting_things",[])]
                        with cc2:
                            st.markdown("#### 🚨 Caution"); [st.markdown(f"⚠️ {p}") for p in nd.get("caution_flags",[])]
                        ee = nd.get("upcoming_earnings_estimate",{})
                        e1,e2,e3,e4 = st.columns(4)
                        e1.metric("Est. Date", ee.get("date_estimate","N/A"))
                        e2.metric("EPS Est.", ee.get("eps_estimate","N/A"))
                        e3.metric("Rev Est.", ee.get("revenue_estimate","N/A"))
                        pred = ee.get("beat_miss_prediction","N/A")
                        e4.markdown(f"**Beat/Meet/Miss**<br><span style='color:{'#2e7d32' if pred=='Beat' else '#c62828' if pred=='Miss' else '#f57c00'};font-size:1.3rem;font-weight:700'>{pred}</span>", unsafe_allow_html=True)
                        st.markdown(f"<div class='metric-card'>{ee.get('rationale','')}</div>", unsafe_allow_html=True)
                    except Exception as e: st.error(f"News analysis error: {e}")
                for a in articles[:8]:
                    desc = a.get("description","") or ""
                    st.markdown(f"<div class='news-card'><a href='{a.get('url','#')}' target='_blank' style='font-weight:600;color:#1a73e8;text-decoration:none'>{a.get('title','')}</a>"
                        f"<br><small style='color:#888'>{a.get('source',{}).get('name','')} · {a.get('publishedAt','')[:10]}</small>"
                        f"<br><small style='color:#555'>{desc[:150]}</small></div>", unsafe_allow_html=True)
            else: st.info("No news found. Add a News API key to enable.")

        with tabs[3]:
            st.markdown("### Dividend Analysis")
            try:
                divs = tiingo_get_safe(f"/tiingo/daily/{ticker.lower()}/dividends", tiingo_key, {
                    "startDate":(datetime.now()-timedelta(days=730)).strftime("%Y-%m-%d"),
                    "endDate":(datetime.now()+timedelta(days=180)).strftime("%Y-%m-%d"),
                })
                recent = sorted(divs or [], key=lambda x: x.get("exDate",""), reverse=True)[:8]
                last_4 = [float(d.get("divCash",0)) for d in recent[:4]]
                annual_div = sum(last_4)
                has_div = annual_div > 0
            except: has_div = False; annual_div = 0; recent = []

            if has_div:
                div_yield = round((annual_div/float(cp))*100,2) if cp!="N/A" else 0
                with st.spinner("Analyzing dividend…"):
                    try:
                        div_hist = "\n".join([f"  Ex-Date:{d.get('exDate','N/A')} Amount:${d.get('divCash','N/A')}" for d in recent[:6]])
                        dd = parse_json(ask_claude(client, "Dividend expert. Return only valid JSON.",
                            f"""Dividend analysis for {ticker}: Price=${cp} AnnualDiv=${annual_div:.4f} Yield={div_yield}%
History:\n{div_hist}\n{context[:1000]}\n
Respond with JSON: {{"ex_dividend_date_human":"date","must_own_by":"date","payment_date_estimate":"date",
"quarterly_dividend_per_share":"amount","annual_yield_pct":"pct","yield_vs_average":"Above Average|Average|Below Average",
"dividend_safety_rating":"Very Safe|Safe|Moderate|At Risk","dividend_safety_rationale":"2-3 sentences",
"capture_recommendation":"Strong Buy for Dividend|Buy for Dividend|Neutral|Avoid for Dividend",
"capture_rationale":"2-3 sentences","dividend_growth_outlook":"Growing|Stable|At Risk of Cut",
"key_insights":["i1","i2","i3"]}}"""))
                        st.markdown(f"<div class='dividend-highlight'><h4>💰 Dividend Summary — {ticker}</h4>"
                            f"<table style='width:100%;border-collapse:collapse'>"
                            f"<tr><td style='padding:5px 0;font-weight:600'>Annual Div/Share:</td><td>${annual_div:.4f}</td></tr>"
                            f"<tr><td style='padding:5px 0;font-weight:600'>Yield:</td><td>{dd.get('annual_yield_pct','N/A')}</td></tr>"
                            f"<tr><td style='padding:5px 0;font-weight:600'>Quarterly/Share:</td><td>{dd.get('quarterly_dividend_per_share','N/A')}</td></tr>"
                            f"<tr><td style='padding:5px 0;font-weight:600'>Next Ex-Div:</td><td><strong>{dd.get('ex_dividend_date_human','N/A')}</strong></td></tr>"
                            f"<tr><td style='padding:5px 0;font-weight:600'>⚡ Must Own By:</td><td><strong style='color:#c62828'>{dd.get('must_own_by','N/A')}</strong></td></tr>"
                            f"<tr><td style='padding:5px 0;font-weight:600'>Payment Date:</td><td>{dd.get('payment_date_estimate','N/A')}</td></tr>"
                            f"</table></div>", unsafe_allow_html=True)
                        d1,d2,d3 = st.columns(3)
                        d1.metric("Safety", dd.get("dividend_safety_rating","N/A"))
                        d2.metric("Yield vs Avg", dd.get("yield_vs_average","N/A"))
                        d3.metric("Growth Outlook", dd.get("dividend_growth_outlook","N/A"))
                        st.markdown(f"<div class='metric-card'><strong>Safety:</strong> {dd.get('dividend_safety_rationale','')}</div>", unsafe_allow_html=True)
                        rec = dd.get("capture_recommendation","Neutral")
                        st.markdown(f"<div class='metric-card'><strong>Capture Rec:</strong> <span style='color:{'#2e7d32' if 'Buy' in rec else '#c62828' if 'Avoid' in rec else '#f57c00'};font-weight:700'>{rec}</span><br>{dd.get('capture_rationale','')}</div>", unsafe_allow_html=True)
                        st.markdown("#### 💡 Key Insights"); [st.markdown(f"• {i}") for i in dd.get("key_insights",[])]
                        st.caption("⚠️ Verify ex-div date with your broker.")
                    except Exception as e: st.error(f"Dividend error: {e}")
            else:
                st.info(f"**{company_name}** does not currently pay a dividend.")

    elif analyze_btn: st.warning("Please enter a ticker symbol.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: INDEX SCREENER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Index Screener":
    import pandas as pd
    st.markdown("### 📋 Index Stock Screener")
    st.markdown("Algorithmically scores stocks on price momentum, technicals, and dividends. Click any ticker in the table to run a full AI analysis.")

    if not tiingo_key:
        st.error("Tiingo API key required."); st.stop()

    col_idx, col_btn = st.columns([2,1])
    with col_idx:
        index_choice = st.selectbox("Select Index", ["Dow Jones (30)", "Nasdaq-100 (100)", "S&P 500 Top 90"])
    with col_btn:
        run_screen = st.button("▶ Run Screener", type="primary", use_container_width=True)

    if run_screen:
        ticker_list = {"Dow Jones (30)": DOW30, "Nasdaq-100 (100)": NASDAQ100, "S&P 500 Top 90": SP500_SAMPLE}[index_choice]
        results = []
        prog = st.progress(0, text="Fetching stock data…")
        for i, t in enumerate(ticker_list):
            prog.progress((i+1)/len(ticker_list), text=f"Fetching {t} ({i+1}/{len(ticker_list)})…")
            row = get_screener_data(t, tiingo_key)
            if row: results.append(row)
            time.sleep(0.3)
        prog.empty()

        if results:
            df = pd.DataFrame(results)
            df = df.sort_values("score", ascending=False).reset_index(drop=True)
            df["rank"] = df.index + 1
            df["score_label"] = df["score"].apply(score_label)
            df["rsi_zone"] = df["rsi"].apply(lambda r: "Oversold" if r and r<30 else ("Overbought" if r and r>70 else "Normal") if r else "N/A")
            df["above_ma50"]  = df.apply(lambda r: "✅" if r["ma50"]  and r["price"] > r["ma50"]  else "❌", axis=1)
            df["above_ma200"] = df.apply(lambda r: "✅" if r["ma200"] and r["price"] > r["ma200"] else "❌", axis=1)

            st.markdown(f"**{len(df)} stocks loaded · Sorted by composite score**")

            # Summary stats
            s1,s2,s3,s4 = st.columns(4)
            s1.metric("Strong (75+)", len(df[df["score"]>=75]))
            s2.metric("Good (60-74)", len(df[(df["score"]>=60)&(df["score"]<75)]))
            s3.metric("Paying Dividend", len(df[df["div_yield"]>0]))
            s4.metric("Avg Score", round(df["score"].mean(),1))

            display_df = df[["rank","ticker","price","score_label","perf_1yr","rsi","rsi_zone","above_ma50","above_ma200","div_yield","next_ex_div"]].copy()
            display_df.columns = ["Rank","Ticker","Price","Score","1Y Return %","RSI","RSI Zone","Above MA50","Above MA200","Div Yield %","Next Ex-Div"]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            st.caption("💡 Scores are algorithmic (momentum + technicals + dividends). Run a full AI analysis on any ticker in the Stock Analysis tab.")
        else:
            st.warning("No data returned. Check your Tiingo key.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: BACKTESTER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📈 Backtester":
    import pandas as pd
    st.markdown("### 📈 Price Target Backtester")
    st.markdown("Compare what our AI price targets **would have projected** vs actual price performance.")
    st.caption("How it works: for each time period, Claude generates a forward price target based on the company's fundamentals and known context at that time. We then plot projected vs actual to measure accuracy.")

    if not tiingo_key or not anthropic_key:
        st.error("Both Tiingo and Anthropic API keys required."); st.stop()

    c1,c2,c3,c4 = st.columns(4)
    with c1: bt_ticker = st.text_input("Ticker", value="TSLA", label_visibility="visible")
    with c2: bt_start  = st.date_input("Start Date", value=datetime(2023,1,1))
    with c3: bt_end    = st.date_input("End Date",   value=datetime(2024,1,1))
    with c4: bt_freq   = st.selectbox("Frequency", ["Monthly","Quarterly","Weekly"])
    bt_run = st.button("▶ Run Backtest", type="primary")

    if bt_run and bt_ticker:
        ticker = bt_ticker.strip().upper()
        client = anthropic.Anthropic(api_key=anthropic_key)

        with st.spinner(f"Fetching historical prices for {ticker}…"):
            hist = get_historical_prices(ticker, bt_start.strftime("%Y-%m-%d"), bt_end.strftime("%Y-%m-%d"), tiingo_key)

        if not hist:
            st.error("No historical data found. Check ticker and date range."); st.stop()

        # Build date checkpoints
        checkpoints = []
        if bt_freq == "Weekly":
            d = bt_start
            while d <= bt_end:
                checkpoints.append(d.strftime("%Y-%m-%d")); d += timedelta(weeks=1)
        elif bt_freq == "Monthly":
            d = bt_start.replace(day=1)
            while d <= bt_end:
                checkpoints.append(d.strftime("%Y-%m-%d"))
                m = d.month+1; y = d.year+(m//13); m = m if m<=12 else 1
                d = d.replace(year=y, month=m, day=1)
        else:  # Quarterly
            d = bt_start.replace(day=1)
            while d <= bt_end:
                checkpoints.append(d.strftime("%Y-%m-%d"))
                m = d.month+3; y = d.year+(m//13); m = m if m<=12 else m-12
                d = d.replace(year=y, month=m, day=1)

        # Build price lookup
        price_map = {}
        for p in hist:
            date_str = p.get("date","")[:10]
            price_map[date_str] = p.get("adjClose") or p.get("close")

        def nearest_price(target_date):
            if target_date in price_map: return float(price_map[target_date])
            for offset in range(1,8):
                d = (datetime.strptime(target_date,"%Y-%m-%d") + timedelta(days=offset)).strftime("%Y-%m-%d")
                if d in price_map: return float(price_map[d])
                d = (datetime.strptime(target_date,"%Y-%m-%d") - timedelta(days=offset)).strftime("%Y-%m-%d")
                if d in price_map: return float(price_map[d])
            return None

        # Generate AI targets for each checkpoint
        bt_results = []
        prog2 = st.progress(0, text="Generating AI projections…")
        for i, chk_date in enumerate(checkpoints[:12]):  # cap at 12 to save API calls
            prog2.progress((i+1)/min(len(checkpoints),12), text=f"Analyzing {chk_date}…")
            actual_price = nearest_price(chk_date)
            if not actual_price: continue

            # Get next period's actual price for comparison
            next_idx = checkpoints.index(chk_date) + 1
            next_actual = nearest_price(checkpoints[next_idx]) if next_idx < len(checkpoints) else None

            try:
                resp = parse_json(ask_claude(client,
                    "You are a financial analyst. Return only valid JSON, no markdown.",
                    f"""It is {chk_date}. {ticker} is trading at ${actual_price:.2f}.
Based on your knowledge of this company's financial performance and market conditions as of {chk_date},
what would your price target be for 1 month forward?

Respond ONLY with valid JSON:
{{"projected_target": 0.0, "direction": "Up|Down|Flat", "rationale": "1-2 sentences",
"sentiment": "Bullish|Neutral|Bearish", "key_factor": "main reason for projection"}}"""))
                proj = float(resp.get("projected_target", actual_price))
                bt_results.append({
                    "date": chk_date,
                    "actual_price": round(actual_price,2),
                    "projected_target": round(proj,2),
                    "next_actual": round(next_actual,2) if next_actual else None,
                    "direction": resp.get("direction","Flat"),
                    "sentiment": resp.get("sentiment","Neutral"),
                    "rationale": resp.get("rationale",""),
                    "key_factor": resp.get("key_factor",""),
                    "proj_pct": round(((proj-actual_price)/actual_price)*100,1),
                    "actual_pct": round(((next_actual-actual_price)/actual_price)*100,1) if next_actual else None,
                })
            except: pass
            time.sleep(0.5)
        prog2.empty()

        if bt_results:
            df_bt = pd.DataFrame(bt_results)

            # Accuracy metrics
            matched = df_bt.dropna(subset=["actual_pct"])
            correct_dir = sum(1 for _,r in matched.iterrows()
                if (r["proj_pct"]>0 and r["actual_pct"]>0) or (r["proj_pct"]<0 and r["actual_pct"]<0) or (abs(r["proj_pct"])<2 and abs(r["actual_pct"])<2))
            accuracy = round((correct_dir/len(matched))*100,1) if len(matched) else 0

            a1,a2,a3,a4 = st.columns(4)
            a1.metric("Periods Analyzed", len(bt_results))
            a2.metric("Directional Accuracy", f"{accuracy}%")
            avg_proj = df_bt["proj_pct"].mean()
            avg_act  = matched["actual_pct"].mean() if len(matched) else 0
            a3.metric("Avg Projected Move", f"{avg_proj:+.1f}%")
            a4.metric("Avg Actual Move",    f"{avg_act:+.1f}%")

            # Chart
            st.markdown("#### Projected vs Actual Price")
            chart_data = df_bt[["date","actual_price","projected_target"]].set_index("date")
            st.line_chart(chart_data)

            # Table
            st.markdown("#### Period-by-Period Breakdown")
            disp = df_bt[["date","actual_price","projected_target","proj_pct","actual_pct","direction","sentiment","key_factor"]].copy()
            disp.columns = ["Date","Price at Date","AI Target","Proj %","Actual Next %","Direction","Sentiment","Key Factor"]
            st.dataframe(disp, use_container_width=True, hide_index=True)
            st.caption("⚠️ Backtesting uses AI knowledge of historical context. Directional accuracy measures whether projected and actual moves were in the same direction.")
        else:
            st.warning("Could not generate backtest results. Try a different ticker or date range.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4: TECHNICAL ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔧 Technical Analysis":
    import pandas as pd
    st.markdown("### 🔧 Technical Analysis")

    if not tiingo_key: st.error("Tiingo API key required."); st.stop()

    tc1,tc2 = st.columns([3,1])
    with tc1: ta_ticker = st.text_input("Ticker", placeholder="e.g. AAPL", label_visibility="visible")
    with tc2: ta_run = st.button("▶ Analyze", type="primary", use_container_width=True)

    if ta_run and ta_ticker:
        ticker = ta_ticker.strip().upper()
        with st.spinner(f"Fetching technical data for {ticker}…"):
            hist = get_historical_prices(ticker,
                (datetime.now()-timedelta(days=365)).strftime("%Y-%m-%d"),
                datetime.now().strftime("%Y-%m-%d"), tiingo_key)

        if not hist:
            st.error("No data found."); st.stop()

        closes  = [p.get("adjClose") or p.get("close") or 0 for p in hist]
        dates   = [p.get("date","")[:10] for p in hist]
        volumes = [p.get("volume") or 0 for p in hist]
        cp = closes[-1] if closes else 0

        ma20  = calc_ma(closes, 20)
        ma50  = calc_ma(closes, 50)
        ma200 = calc_ma(closes, 200)
        rsi   = calc_rsi(closes[-15:])
        macd_line, signal, histogram = calc_macd(closes)

        # Bollinger Bands (20-day)
        bb_upper, bb_lower, bb_mid = None, None, None
        if len(closes) >= 20:
            bb_slice = closes[-20:]
            bb_mid = sum(bb_slice)/20
            std = math.sqrt(sum((x-bb_mid)**2 for x in bb_slice)/20)
            bb_upper = bb_mid + 2*std
            bb_lower = bb_mid - 2*std

        st.markdown(f"#### {ticker} — Technical Indicators")

        # Key metrics
        m1,m2,m3,m4,m5 = st.columns(5)
        m1.metric("Current Price", f"${cp:.2f}")
        m2.metric("RSI (14)", f"{rsi:.1f}" if rsi else "N/A",
            delta="Overbought" if rsi and rsi>70 else ("Oversold" if rsi and rsi<30 else "Normal"))
        m3.metric("MACD", f"{macd_line:.3f}" if macd_line else "N/A",
            delta="Bullish" if macd_line and macd_line > 0 else "Bearish")
        m4.metric("50-Day MA", f"${ma50:.2f}" if ma50 else "N/A",
            delta="Above ✅" if ma50 and cp > ma50 else "Below ❌")
        m5.metric("200-Day MA", f"${ma200:.2f}" if ma200 else "N/A",
            delta="Above ✅" if ma200 and cp > ma200 else "Below ❌")

        # Bollinger Bands status
        if bb_upper and bb_lower:
            bb1,bb2,bb3 = st.columns(3)
            bb1.metric("BB Upper", f"${bb_upper:.2f}")
            bb2.metric("BB Mid",   f"${bb_mid:.2f}")
            bb3.metric("BB Lower", f"${bb_lower:.2f}")
            if cp > bb_upper: st.warning("⚠️ Price is above upper Bollinger Band — potentially overbought")
            elif cp < bb_lower: st.info("💡 Price is below lower Bollinger Band — potentially oversold")
            else: st.success("✅ Price is within normal Bollinger Band range")

        # Price chart
        st.markdown("#### Price History (1 Year)")
        chart_df = pd.DataFrame({"Price": closes, "MA20": [calc_ma(closes[:i+1],20) or closes[i] for i in range(len(closes))],
            "MA50": [calc_ma(closes[:i+1],50) or closes[i] for i in range(len(closes))]}, index=dates)
        st.line_chart(chart_df)

        # Volume chart
        st.markdown("#### Volume")
        vol_df = pd.DataFrame({"Volume": volumes}, index=dates)
        st.bar_chart(vol_df)

        # Signal summary
        st.markdown("#### 📡 Signal Summary")
        signals = []
        if rsi:
            if rsi < 30:   signals.append(("RSI", "🟢 Oversold — potential buy signal", "good"))
            elif rsi > 70: signals.append(("RSI", "🔴 Overbought — potential sell signal", "bad"))
            else:          signals.append(("RSI", f"🟡 Neutral ({rsi:.1f})", "neutral"))
        if ma50 and ma200:
            if ma50 > ma200: signals.append(("MA Cross", "🟢 Golden Cross — MA50 above MA200 (bullish)", "good"))
            else:            signals.append(("MA Cross", "🔴 Death Cross — MA50 below MA200 (bearish)", "bad"))
        if macd_line and signal:
            if macd_line > signal: signals.append(("MACD", "🟢 MACD above signal line (bullish momentum)", "good"))
            else:                   signals.append(("MACD", "🔴 MACD below signal line (bearish momentum)", "bad"))
        if bb_upper and bb_lower:
            if cp > bb_upper:   signals.append(("Bollinger", "🔴 Above upper band (overbought)", "bad"))
            elif cp < bb_lower: signals.append(("Bollinger", "🟢 Below lower band (oversold)", "good"))
            else:               signals.append(("Bollinger", "🟡 Within bands (neutral)", "neutral"))

        for name, desc, _ in signals:
            st.markdown(f"**{name}:** {desc}")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5: PEER COMPARISON
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🏢 Peer Comparison":
    import pandas as pd
    st.markdown("### 🏢 Peer / Competitor Comparison")

    if not tiingo_key or not anthropic_key:
        st.error("Both API keys required."); st.stop()

    pc1, pc2 = st.columns([3,1])
    with pc1: peer_ticker = st.text_input("Enter a stock ticker", placeholder="e.g. TSLA", label_visibility="visible")
    with pc2: peer_run = st.button("▶ Compare", type="primary", use_container_width=True)

    if peer_run and peer_ticker:
        ticker = peer_ticker.strip().upper()
        client = anthropic.Anthropic(api_key=anthropic_key)

        # First ask Claude who the peers are
        with st.spinner("Identifying peers…"):
            try:
                peers_resp = parse_json(ask_claude(client,
                    "You are a financial analyst. Return only valid JSON.",
                    f"""Who are the top 4-5 direct competitors or peers of {ticker}?
Respond ONLY with valid JSON: {{"company_name": "full name", "sector": "sector", "description": "1 sentence about what {ticker} does",
"peers": [{{"ticker":"TICK","name":"Company Name","why":"one sentence on why they are a peer"}}]}}"""))

                st.markdown(f"**{peers_resp.get('company_name', ticker)}** — {peers_resp.get('description','')}")
                peer_list = [p["ticker"] for p in peers_resp.get("peers",[])][:5]
                all_tickers = [ticker] + peer_list

            except Exception as e:
                st.error(f"Could not identify peers: {e}"); st.stop()

        # Fetch screener data for each
        peer_data = []
        with st.spinner("Fetching comparison data…"):
            for t in all_tickers:
                row = get_screener_data(t, tiingo_key)
                if row:
                    row["is_primary"] = (t == ticker)
                    peer_data.append(row)
                time.sleep(0.3)

        if peer_data:
            df_peers = pd.DataFrame(peer_data)
            df_peers = df_peers.sort_values("score", ascending=False)

            st.markdown("#### Side-by-Side Comparison")
            metrics_to_show = ["ticker","price","score","perf_1yr","rsi","div_yield","ma50","ma200"]
            df_disp = df_peers[metrics_to_show].copy()
            df_disp.columns = ["Ticker","Price","Score","1Y Return %","RSI","Div Yield %","MA50","MA200"]
            st.dataframe(df_disp, use_container_width=True, hide_index=True)

            # Chart comparison
            st.markdown("#### Score Comparison")
            score_df = df_peers[["ticker","score"]].set_index("ticker")
            st.bar_chart(score_df)

            st.markdown("#### 1-Year Return Comparison")
            ret_df = df_peers[["ticker","perf_1yr"]].set_index("ticker")
            st.bar_chart(ret_df)

            # Claude AI comparison summary
            with st.spinner("Generating AI comparison…"):
                try:
                    comparison_data = df_disp.to_string()
                    peer_names = ", ".join([f"{p['ticker']}" for p in peers_resp.get("peers",[])])
                    comp = parse_json(ask_claude(client,
                        "You are a financial analyst. Return only valid JSON.",
                        f"""Compare {ticker} vs its peers: {peer_names}
Data: {comparison_data}

Respond ONLY with valid JSON:
{{"winner":"ticker of best positioned stock","winner_rationale":"2-3 sentences",
"biggest_risk":"ticker with most risk and why",
"best_value":"ticker offering best value right now",
"key_insights":["insight 1","insight 2","insight 3"],
"recommendation":"which stock would you buy and why in 2-3 sentences"}}"""))
                    st.markdown("#### 🤖 AI Comparison Summary")
                    w1,w2,w3 = st.columns(3)
                    w1.metric("Best Positioned", comp.get("winner","N/A"))
                    w2.metric("Best Value", comp.get("best_value","N/A"))
                    w3.metric("Highest Risk", comp.get("biggest_risk","N/A"))
                    st.markdown(f"<div class='metric-card'><strong>Winner Rationale:</strong> {comp.get('winner_rationale','')}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='metric-card'><strong>Recommendation:</strong> {comp.get('recommendation','')}</div>", unsafe_allow_html=True)
                    st.markdown("#### Key Insights")
                    for ins in comp.get("key_insights",[]): st.markdown(f"• {ins}")
                except Exception as e: st.error(f"Comparison error: {e}")

            # Show peer descriptions
            st.markdown("#### Peer Details")
            for p in peers_resp.get("peers",[]):
                st.markdown(f"**{p['ticker']}** — {p['why']}")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6: EARNINGS CALENDAR
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📅 Earnings Calendar":
    import pandas as pd
    st.markdown("### 📅 Earnings Calendar")
    st.markdown("Track upcoming earnings dates for your watchlist and get AI estimates for how they'll come in.")

    if not anthropic_key or not tiingo_key:
        st.error("Both API keys required."); st.stop()

    st.markdown("**Enter your watchlist tickers (comma separated):**")
    default_watchlist = "AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, JPM, V, WMT"
    watchlist_input = st.text_area("Watchlist", value=default_watchlist, label_visibility="collapsed", height=80)
    cal_run = st.button("▶ Load Calendar", type="primary")

    if cal_run:
        tickers = [t.strip().upper() for t in watchlist_input.split(",") if t.strip()]
        client  = anthropic.Anthropic(api_key=anthropic_key)

        with st.spinner("Fetching earnings data and generating estimates…"):
            cal_results = []
            for t in tickers:
                try:
                    # Get current price
                    prices = tiingo_get_safe(f"/tiingo/daily/{t.lower()}/prices", tiingo_key, {
                        "startDate": (datetime.now()-timedelta(days=5)).strftime("%Y-%m-%d"),
                        "endDate":   datetime.now().strftime("%Y-%m-%d"),
                    })
                    cp_val = prices[-1].get("adjClose") or prices[-1].get("close") if prices else None

                    # Ask Claude for earnings estimate
                    est = parse_json(ask_claude(client,
                        "You are a financial analyst. Return only valid JSON.",
                        f"""For {t}, what is the next expected earnings date and your estimate?
Current price: ${cp_val:.2f if cp_val else 'N/A'}

Respond ONLY with valid JSON:
{{"next_earnings_date":"YYYY-MM-DD or 'Unknown'","quarter":"e.g. Q1 2025",
"eps_estimate":"your EPS estimate","revenue_estimate":"your revenue estimate",
"beat_miss_prediction":"Beat|Meet|Miss","confidence":"High|Medium|Low",
"key_watch":"most important metric to watch","days_until":"number or unknown"}}"""))

                    cal_results.append({
                        "ticker": t,
                        "price": f"${cp_val:.2f}" if cp_val else "N/A",
                        "next_date": est.get("next_earnings_date","Unknown"),
                        "quarter": est.get("quarter",""),
                        "eps_est": est.get("eps_estimate",""),
                        "rev_est": est.get("revenue_estimate",""),
                        "prediction": est.get("beat_miss_prediction",""),
                        "confidence": est.get("confidence",""),
                        "key_watch": est.get("key_watch",""),
                    })
                except Exception as e:
                    cal_results.append({"ticker":t,"price":"N/A","next_date":"Error","quarter":"","eps_est":"","rev_est":"","prediction":"","confidence":"","key_watch":str(e)[:50]})

        if cal_results:
            df_cal = pd.DataFrame(cal_results)
            df_cal_disp = df_cal.copy()
            df_cal_disp.columns = ["Ticker","Price","Next Earnings","Quarter","EPS Est","Rev Est","Beat/Meet/Miss","Confidence","Key Metric to Watch"]
            st.dataframe(df_cal_disp, use_container_width=True, hide_index=True)

            st.markdown("#### 🔮 Beat/Meet/Miss Predictions")
            beats = sum(1 for r in cal_results if r["prediction"]=="Beat")
            meets = sum(1 for r in cal_results if r["prediction"]=="Meet")
            misses= sum(1 for r in cal_results if r["prediction"]=="Miss")
            b1,b2,b3 = st.columns(3)
            b1.metric("Predicted Beats",  beats,  delta=f"{round(beats/len(cal_results)*100)}% of watchlist" if cal_results else "")
            b2.metric("Predicted Meets",  meets)
            b3.metric("Predicted Misses", misses, delta=f"Watch out" if misses > 0 else "")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 7: INSIDER ACTIVITY
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🕵️ Insider Activity":
    import pandas as pd
    st.markdown("### 🕵️ Insider Trading Activity")
    st.markdown("See recent insider buys and sells. Insider buying is often a bullish signal; heavy selling can be a warning sign.")
    st.caption("Data sourced from SEC Form 4 filings via OpenInsider. No API key required for this feature.")

    ins_ticker = st.text_input("Enter Ticker", placeholder="e.g. TSLA, AAPL, NVDA", label_visibility="visible")
    ins_run    = st.button("▶ Fetch Insider Activity", type="primary")

    if ins_run and ins_ticker:
        ticker = ins_ticker.strip().upper()
        client = anthropic.Anthropic(api_key=anthropic_key) if anthropic_key else None

        with st.spinner(f"Fetching insider data for {ticker}…"):
            try:
                # OpenInsider provides free CSV-style data
                url = f"http://openinsider.com/screener?s={ticker}&o=&pl=&ph=&ll=&lh=&fd=365&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=40&action=1"
                r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})

                if r.status_code == 200:
                    # Parse the HTML table
                    from html.parser import HTMLParser

                    class TableParser(HTMLParser):
                        def __init__(self):
                            super().__init__()
                            self.in_table = False; self.in_row = False; self.in_cell = False
                            self.rows = []; self.current_row = []; self.current_cell = ""
                        def handle_starttag(self, tag, attrs):
                            if tag == "tr": self.in_row = True; self.current_row = []
                            if tag in ("td","th"): self.in_cell = True; self.current_cell = ""
                        def handle_endtag(self, tag):
                            if tag == "td" or tag == "th":
                                self.current_row.append(self.current_cell.strip()); self.in_cell = False
                            if tag == "tr":
                                if self.current_row: self.rows.append(self.current_row); self.current_row = []
                        def handle_data(self, data):
                            if self.in_cell: self.current_cell += data

                    parser = TableParser()
                    parser.feed(r.text)

                    # Find rows with actual data (filter for ticker)
                    insider_rows = []
                    for row in parser.rows:
                        if len(row) >= 12 and ticker in " ".join(row):
                            insider_rows.append(row)

                    if insider_rows:
                        insiders = []
                        for row in insider_rows[:15]:
                            try:
                                trade_type = row[6] if len(row)>6 else ""
                                is_buy = "P" in trade_type or "Buy" in trade_type
                                insiders.append({
                                    "Date":      row[2][:10] if len(row)>2 else "",
                                    "Insider":   row[4]      if len(row)>4 else "",
                                    "Title":     row[5]      if len(row)>5 else "",
                                    "Type":      "🟢 Buy" if is_buy else "🔴 Sell",
                                    "Qty":       row[8]      if len(row)>8 else "",
                                    "Price":     row[9]      if len(row)>9 else "",
                                    "Value":     row[11]     if len(row)>11 else "",
                                })
                            except: pass

                        if insiders:
                            df_ins = pd.DataFrame(insiders)
                            st.dataframe(df_ins, use_container_width=True, hide_index=True)

                            buys  = sum(1 for x in insiders if "Buy" in x["Type"])
                            sells = sum(1 for x in insiders if "Sell" in x["Type"])
                            i1,i2,i3 = st.columns(3)
                            i1.metric("Insider Buys",  buys,  delta="Bullish signal" if buys > sells else "")
                            i2.metric("Insider Sells", sells, delta="Watch closely" if sells > buys else "")
                            i3.metric("Buy/Sell Ratio", f"{buys}:{sells}")

                            if buys > sells:
                                st.success(f"✅ Insiders are net **buyers** of {ticker} — generally a bullish signal")
                            elif sells > buys:
                                st.warning(f"⚠️ Insiders are net **sellers** of {ticker} — worth monitoring, though may be routine")
                            else:
                                st.info("📊 Balanced insider activity — no strong directional signal")

                            # AI interpretation
                            if client:
                                with st.spinner("Getting AI interpretation…"):
                                    try:
                                        interp = parse_json(ask_claude(client,
                                            "Financial analyst. Return only valid JSON.",
                                            f"""Insider trading summary for {ticker}: {buys} buys, {sells} sells in past year.
Notable activity: {json.dumps(insiders[:5])}

Respond with JSON: {{"signal":"Bullish|Neutral|Bearish","summary":"2-3 sentences interpreting the insider activity",
"key_observation":"most notable single transaction or pattern",
"recommendation":"what should an investor take away from this"}}"""))
                                        st.markdown("#### 🤖 AI Interpretation")
                                        sig = interp.get("signal","Neutral")
                                        sig_color = "#2e7d32" if sig=="Bullish" else "#c62828" if sig=="Bearish" else "#f57c00"
                                        st.markdown(f"**Signal:** <span style='color:{sig_color};font-weight:700'>{sig}</span>", unsafe_allow_html=True)
                                        st.markdown(f"<div class='metric-card'>{interp.get('summary','')}</div>", unsafe_allow_html=True)
                                        st.markdown(f"**Key Observation:** {interp.get('key_observation','')}")
                                        st.markdown(f"**Takeaway:** {interp.get('recommendation','')}")
                                    except: pass
                        else:
                            st.info(f"No recent insider transactions parsed for {ticker}.")
                    else:
                        st.info(f"No insider transactions found for {ticker} in the past year.")
                else:
                    st.warning(f"Could not reach OpenInsider (HTTP {r.status_code}). Try again shortly.")
            except Exception as e:
                st.error(f"Error fetching insider data: {e}")
                st.markdown("You can also check insider activity manually at [openinsider.com](http://openinsider.com)")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
st.caption("⚠️ For informational purposes only. Not financial advice. Always do your own research.")
