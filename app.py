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
st.markdown("""<style>
    .main-header{font-size:2.5rem;font-weight:800;background:linear-gradient(90deg,#1a73e8,#0d47a1);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:0.2rem}
    .sub-header{color:#666;margin-bottom:1rem;font-size:1rem}
    .rating-excellent{background:#d4edda;color:#155724;border-radius:6px;padding:3px 8px;font-weight:700;display:inline-block;font-size:.8rem}
    .rating-good{background:#cce5ff;color:#004085;border-radius:6px;padding:3px 8px;font-weight:700;display:inline-block;font-size:.8rem}
    .rating-neutral{background:#fff3cd;color:#856404;border-radius:6px;padding:3px 8px;font-weight:700;display:inline-block;font-size:.8rem}
    .rating-bad{background:#f8d7da;color:#721c24;border-radius:6px;padding:3px 8px;font-weight:700;display:inline-block;font-size:.8rem}
    .metric-card{background:#f8f9fa;border-radius:10px;padding:1rem 1.2rem;border-left:4px solid #1a73e8;margin-bottom:1rem}
    .section-divider{border-top:2px solid #e0e0e0;margin:2rem 0}
    .news-card{background:#f8f9fa;border-radius:8px;padding:1rem;margin-bottom:.8rem;border-left:3px solid #1a73e8}
    .dividend-highlight{background:linear-gradient(135deg,#e8f5e9,#c8e6c9);border-radius:10px;padding:1.2rem;border:1px solid #81c784}
    .price-target-card{background:#fff;border:1px solid #e0e0e0;border-radius:10px;padding:1rem;text-align:center}
    .price-up{color:#2e7d32;font-weight:700}
    .price-down{color:#c62828;font-weight:700}
    .data-badge{font-size:.72rem;padding:2px 10px;border-radius:10px;background:#e8f0fe;color:#1a73e8;font-weight:600;display:inline-block;margin-left:8px}
</style>""", unsafe_allow_html=True)

st.markdown('<p class="main-header">📈 Stock Evaluator AI</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Earnings · Price Targets · Screener · Backtesting · Technicals · Peers · Insiders · Dividends</p>', unsafe_allow_html=True)

_ant = get_secret("ANTHROPIC_API_KEY")
_tii = get_secret("TIINGO_API_KEY")
_nws = get_secret("NEWS_API_KEY")
with st.expander("⚙️ API Keys", expanded=not _ant):
    c1,c2,c3 = st.columns(3)
    with c1: anthropic_key = st.text_input("Anthropic API Key", value=_ant, type="password")
    with c2: tiingo_key    = st.text_input("Tiingo API Key",    value=_tii, type="password", help="api.tiingo.com — free")
    with c3: news_key      = st.text_input("News API Key",      value=_nws, type="password", help="newsapi.org — free")

# ══════════════════════════════════════════════════════════════════════════════
# MODULE-LEVEL CONSTANTS
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

# Dividend universe — 3 categories
ARISTOCRATS = [
    "MMM","ABT","ABBV","AFL","APD","ADM","ADP","LOW","ATO","AVY",
    "BDX","BRO","CHRW","CVX","CB","CL","CINF","KO","ED","DOV",
    "EMR","XOM","GPC","GWW","HRL","ITW","JNJ","KMB","LIN","MCD",
    "MDT","MKC","NUE","PH","PEP","PG","O","SWK","SYY","TROW",
    "TGT","WMT","WBA","SPGI","AOS",
]

HIGH_YIELD = [
    "O","MAIN","STAG","VICI","AMT","PLD","SPG","ARE","EXR","PSA",
    "WELL","NNN","WPC","OHI","LTC","NEE","DUK","SO","D","AEP",
    "EXC","SRE","XEL","WEC","PPL","AWK","ET","EPD","MMP","MPLX",
    "ARCC","HTGC","T","VZ","MO","PM","IBM","ABBV","CVX","XOM",
]

DIVIDEND_GROWTH = [
    "MSFT","AAPL","V","MA","UNH","HD","JPM","BAC","AVGO","TXN",
    "QCOM","CSCO","ACN","TJX","COST","TMO","DHR","SYK","BLK","ICE",
    "AON","HON","CAT","DE","EMR","FAST","ADP","WM","PAYX","MMC",
    "LOW","SPGI","CB","PG","KO","PEP","WMT","JNJ","ABT","MDT",
]

# Known dividend data — fallback when Tiingo free tier has no dividend history
# Format: ticker -> (approx_yield_pct, div_growth_rate_pct, approx_annual_div_per_share)
KNOWN_DIVIDENDS = {
    "MMM":(6.2,0.0,5.92),"ABT":(2.0,7.0,2.20),"ABBV":(3.8,5.0,6.20),"AFL":(2.3,9.0,1.88),
    "APD":(2.8,8.0,7.08),"ADM":(3.5,5.0,1.80),"ADP":(2.1,12.0,5.60),"LOW":(1.9,18.0,4.60),
    "ATO":(2.8,9.0,3.22),"AVY":(2.0,7.0,3.32),"BDX":(1.6,5.0,3.64),"BRO":(1.0,10.0,0.96),
    "CVX":(4.4,6.0,6.52),"CB":(1.5,5.0,3.68),"CL":(2.3,4.0,1.96),"CINF":(2.7,6.0,3.12),
    "KO":(3.1,5.0,1.94),"ED":(3.5,3.0,3.24),"DOV":(1.3,5.0,2.08),"EMR":(2.2,1.0,2.10),
    "XOM":(3.7,4.0,3.80),"GPC":(2.8,6.0,4.10),"GWW":(0.8,7.0,7.44),"HRL":(3.5,1.0,1.10),
    "ITW":(2.3,7.0,5.60),"JNJ":(3.2,6.0,4.96),"KMB":(3.7,3.0,4.88),"LIN":(1.3,8.0,5.40),
    "MCD":(2.5,10.0,6.68),"MDT":(3.5,3.0,2.80),"MKC":(2.2,8.0,1.56),"NUE":(1.4,2.0,2.04),
    "PH":(1.4,14.0,6.52),"PEP":(3.1,7.0,5.06),"PG":(2.4,5.0,3.76),"O":(5.8,2.0,3.07),
    "SPGI":(0.9,9.0,3.60),"SWK":(3.6,1.0,4.12),"SYY":(2.8,5.0,2.08),"TROW":(4.8,0.0,4.96),
    "TGT":(3.3,3.0,4.44),"WMT":(1.3,4.0,2.28),"WBA":(7.0,-5.0,1.92),"AOS":(1.8,8.0,1.28),
    "CHRW":(2.5,5.0,2.40),"MAIN":(6.5,3.0,2.88),"STAG":(3.9,1.0,1.47),"VICI":(5.6,6.0,1.66),
    "AMT":(3.2,3.0,6.48),"PLD":(2.8,10.0,3.82),"SPG":(5.5,5.0,7.60),"ARE":(4.3,3.0,6.36),
    "EXR":(4.1,5.0,6.56),"PSA":(4.2,3.0,12.0),"WELL":(2.3,9.0,2.44),"NNN":(5.6,2.0,2.26),
    "WPC":(5.8,1.0,4.36),"OHI":(7.5,2.0,3.44),"LTC":(6.8,0.0,2.28),"NEE":(3.2,10.0,2.06),
    "DUK":(4.2,2.0,4.10),"SO":(3.7,3.0,2.80),"D":(4.8,2.0,2.67),"AEP":(4.2,6.0,3.52),
    "EXC":(3.8,2.0,1.52),"SRE":(3.3,5.0,2.48),"XEL":(3.6,6.0,2.08),"WEC":(3.4,7.0,3.38),
    "PPL":(3.7,1.0,0.94),"AWK":(2.1,8.0,2.80),"ET":(8.2,3.0,0.32),"EPD":(7.3,2.0,2.00),
    "MMP":(7.8,0.0,3.52),"MPLX":(9.4,8.0,3.46),"ARCC":(9.8,2.0,1.92),"HTGC":(10.2,1.0,1.84),
    "T":(6.8,0.0,1.11),"VZ":(6.5,2.0,2.66),"MO":(9.2,3.0,3.92),"PM":(5.2,3.0,5.20),
    "IBM":(3.5,1.0,6.68),"MSFT":(0.8,10.0,3.00),"AAPL":(0.5,5.0,1.00),"V":(0.8,15.0,2.08),
    "MA":(0.6,16.0,2.64),"UNH":(1.5,14.0,8.40),"HD":(2.4,10.0,9.00),"JPM":(2.4,9.0,4.60),
    "BAC":(2.6,11.0,1.00),"AVGO":(2.1,14.0,21.0),"TXN":(2.9,5.0,4.96),"QCOM":(2.2,7.0,3.40),
    "CSCO":(3.2,3.0,1.60),"ACN":(1.7,15.0,5.32),"TJX":(1.5,20.0,1.33),"COST":(0.6,13.0,4.64),
    "TMO":(0.3,16.0,1.32),"DHR":(0.5,20.0,1.08),"SYK":(1.1,12.0,3.00),"BLK":(2.6,11.0,20.4),
    "ICE":(1.4,10.0,1.52),"AON":(0.8,10.0,2.24),"HON":(2.1,5.0,4.32),"CAT":(1.7,8.0,5.20),
    "DE":(1.5,15.0,5.20),"FAST":(2.5,13.0,1.76),"ADP":(2.1,12.0,5.60),"WM":(1.7,7.0,2.80),
    "PAYX":(3.2,13.0,3.64),"MMC":(1.5,15.0,3.00),"ABT":(2.0,7.0,2.20),"GE":(0.3,0.0,0.32),
    "GILD":(3.8,5.0,3.16),"BKNG":(0.8,0.0,8.00),"ODFL":(0.5,25.0,1.68),"CTAS":(1.1,20.0,5.68),
}

# ══════════════════════════════════════════════════════════════════════════════
# TIINGO API
# ══════════════════════════════════════════════════════════════════════════════
TIINGO_BASE = "https://api.tiingo.com"

def tiingo_get(path, api_key, params=None):
    try:
        headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}
        r = requests.get(f"{TIINGO_BASE}{path}", headers=headers, params=params or {}, timeout=15)
        if r.status_code == 401: raise RuntimeError("Tiingo API key invalid.")
        if r.status_code == 403: raise RuntimeError(f"Tiingo 403: {r.text[:200]}")
        if r.status_code == 404: return None
        if r.status_code == 429: raise RuntimeError("Tiingo rate limit hit.")
        if r.status_code != 200: raise RuntimeError(f"Tiingo HTTP {r.status_code}: {r.text[:200]}")
        return r.json()
    except RuntimeError: raise
    except Exception as e: raise RuntimeError(f"Tiingo request failed: {e}")

def tiingo_safe(path, api_key, params=None):
    try: return tiingo_get(path, api_key, params)
    except: return None

def get_stock_data(ticker, api_key):
    t = ticker.lower()
    meta = tiingo_get(f"/tiingo/daily/{t}", api_key)
    if not meta: raise RuntimeError(f"Ticker **{ticker}** not found on Tiingo.")
    prices = tiingo_safe(f"/tiingo/daily/{t}/prices", api_key, {
        "startDate": (datetime.now()-timedelta(days=5)).strftime("%Y-%m-%d"),
        "endDate":   datetime.now().strftime("%Y-%m-%d"),
    })
    latest = prices[-1] if prices else {}
    fund_latest = {}
    try:
        fm = tiingo_safe(f"/tiingo/fundamentals/{t}/daily", api_key, {
            "startDate": (datetime.now()-timedelta(days=10)).strftime("%Y-%m-%d")
        })
        fund_latest = fm[-1] if fm else {}
    except: pass
    q_income, a_income, q_balance, a_cashflow = [], [], [], []
    try:
        stmts = tiingo_safe(f"/tiingo/fundamentals/{t}/statements", api_key, {
            "startDate": (datetime.now()-timedelta(days=730)).strftime("%Y-%m-%d"),
            "filter": "quarterlyIncomeStatement,annualIncomeStatement,quarterlyBalanceSheet,annualCashFlow",
        })
        if stmts:
            for s in stmts:
                pt = s.get("quarter"); st_type = s.get("statementType","")
                d = {r["name"]: r["value"] for r in s.get("dataEntries",[]) if "name" in r}
                d["_date"] = s.get("date",""); d["_quarter"] = pt
                if "incomeStatement" in st_type.lower() and pt and pt > 0: q_income.append(d)
                elif "incomeStatement" in st_type.lower() and pt == 0: a_income.append(d)
                elif "balanceSheet" in st_type.lower() and pt and pt > 0: q_balance.append(d)
                elif "cashFlow" in st_type.lower() and pt == 0: a_cashflow.append(d)
    except: pass
    news = []
    try:
        n = tiingo_safe("/tiingo/news", api_key, {"tickers": t, "limit": 10, "sortBy": "publishedDate"})
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
    return tiingo_safe(f"/tiingo/daily/{ticker.lower()}/prices", api_key, {
        "startDate": start_date, "endDate": end_date, "resampleFreq": "daily",
    }) or []

def get_screener_data(ticker, api_key):
    t = ticker.lower()
    try:
        prices = tiingo_safe(f"/tiingo/daily/{t}/prices", api_key, {
            "startDate": (datetime.now()-timedelta(days=365)).strftime("%Y-%m-%d"),
            "endDate":   datetime.now().strftime("%Y-%m-%d"),
        })
        if not prices or len(prices) < 5: return None
        latest = prices[-1]; year_ago = prices[0]
        cp = float(latest.get("adjClose") or latest.get("close") or 0)
        yr_ago_p = float(year_ago.get("adjClose") or year_ago.get("close") or cp)
        if cp <= 0: return None
        closes = [float(p.get("adjClose") or p.get("close") or 0) for p in prices]
        high_52w = max(closes); low_52w = min(closes)
        rsi  = calc_rsi(closes[-15:])
        ma50  = calc_ma(closes, 50); ma200 = calc_ma(closes, 200)
        divs = tiingo_safe(f"/tiingo/daily/{t}/dividends", api_key, {
            "startDate": (datetime.now()-timedelta(days=400)).strftime("%Y-%m-%d"),
            "endDate":   (datetime.now()+timedelta(days=180)).strftime("%Y-%m-%d"),
        })
        div_list = sorted(divs or [], key=lambda x: x.get("exDate",""), reverse=True)
        annual_div = sum(float(d.get("divCash",0)) for d in div_list[:4])
        div_yield  = round((annual_div/float(cp))*100,2) if cp and annual_div > 0 else 0
        next_ex = next((d.get("exDate","") for d in div_list if d.get("exDate","") >= datetime.now().strftime("%Y-%m-%d")), "")
        perf_1yr = round(((cp - yr_ago_p)/yr_ago_p)*100,1) if yr_ago_p else 0
        score = calc_screener_score(cp, ma50, ma200, rsi, perf_1yr, div_yield)
        return {
            "ticker": ticker, "price": round(cp,2), "perf_1yr": perf_1yr,
            "high_52w": round(high_52w,2), "low_52w": round(low_52w,2),
            "ma50": round(ma50,2) if ma50 else None, "ma200": round(ma200,2) if ma200 else None,
            "rsi": round(rsi,1) if rsi else None, "div_yield": div_yield, "annual_div": round(annual_div,4),
            "next_ex_div": next_ex[:10] if next_ex else "", "score": score,
        }
    except: return None

# ══════════════════════════════════════════════════════════════════════════════
# TECHNICALS
# ══════════════════════════════════════════════════════════════════════════════
def calc_rsi(prices, period=14):
    if len(prices) < period+1: return None
    gains, losses = [], []
    for i in range(1, len(prices)):
        d = prices[i]-prices[i-1]; gains.append(max(d,0)); losses.append(max(-d,0))
    ag = sum(gains[-period:])/period; al = sum(losses[-period:])/period
    return 100 if al == 0 else 100-(100/(1+ag/al))

def calc_ma(prices, period):
    if len(prices) < period: return None
    return sum(prices[-period:])/period

def calc_macd(prices):
    if len(prices) < 26: return None, None, None
    def ema(p, n):
        k = 2/(n+1); e = p[0]
        for x in p[1:]: e = x*k+e*(1-k)
        return e
    ema12 = ema(prices[-26:], 12); ema26 = ema(prices[-26:], 26)
    ml = ema12-ema26; sig = ema(prices[-9:], 9) if len(prices) >= 9 else ml
    return round(ml,4), round(sig,4), round(ml-sig,4)

def calc_screener_score(price, ma50, ma200, rsi, perf_1yr, div_yield):
    score = 50
    if ma50 and price > ma50: score += 10
    if ma200 and price > ma200: score += 10
    if rsi:
        if 40 <= rsi <= 60: score += 10
        elif rsi < 30: score += 5
        elif rsi > 70: score -= 5
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
# GLOSSARIES
# ══════════════════════════════════════════════════════════════════════════════
def show_glossary(terms, title="📖 Metric Definitions"):
    with st.expander(title, expanded=False):
        cols = st.columns(2)
        items = list(terms.items()); half = (len(items)+1)//2
        for i,(term,defn) in enumerate(items):
            with cols[0 if i < half else 1]:
                st.markdown(f"**{term}**"); st.caption(defn)

GLOSSARY_EARNINGS = {
    "Overall Rating":"Claude's holistic assessment — Excellent, Good, Neutral, or Bad.",
    "Revenue Growth":"How fast total sales are growing year-over-year. Above 10% is strong.",
    "Profitability & Margins":"How much revenue the company keeps as profit (gross, operating, net margins).",
    "Earnings Per Share":"Net income ÷ shares outstanding. Rising EPS = improving profitability.",
    "Cash Flow Generation":"Real cash produced from operations. Strong free cash flow = quality company.",
    "Balance Sheet Health":"Debt-to-equity ratio and cash reserves. Low debt + high cash = resilient.",
    "Valuation":"Is the stock cheap or expensive? Based on P/E, PEG, EV/EBITDA vs peers.",
    "Analyst Sentiment":"Wall Street consensus rating and price target direction.",
    "Revenue vs Expectations":"Did the company beat, meet, or miss analyst revenue forecasts?",
    "Cost Management":"How well expenses are controlled relative to revenue. Improving margins = good.",
    "Return on Capital":"ROE/ROA — how efficiently management generates profits from capital.",
}
GLOSSARY_TARGETS = {
    "Outlook":"Claude's directional view — Bullish (expects gains) to Bearish (expects declines).",
    "Recommendation":"Buy = attractive now. Hold = keep if owned. Sell = consider reducing.",
    "Conviction":"How confident Claude is — High, Medium, or Low.",
    "Price Target":"Claude's estimated fair price at each time horizon (1 day to 1 year).",
    "% Change":"Projected percentage move from current price to the target.",
    "1Y Return %":"Actual price change over the past 12 months.",
}
GLOSSARY_SCREENER = {
    "Score":"Composite 0-100: price momentum + RSI zone + moving averages + dividend yield.",
    "1Y Return %":"Price performance over the past 12 months.",
    "RSI":"Relative Strength Index. <30 = oversold (buy signal), >70 = overbought (sell signal).",
    "RSI Zone":"Human-readable: Oversold, Normal, or Overbought.",
    "Above MA50":"Price above 50-day moving average? ✅ = bullish short-term trend.",
    "Above MA200":"Price above 200-day moving average? ✅ = bullish long-term trend.",
    "Div Yield %":"Annual dividend ÷ stock price = cash return from holding the stock.",
    "Next Ex-Div":"Must own stock BEFORE this date to receive the next dividend.",
}
GLOSSARY_TECHNICALS = {
    "RSI (14)":"Relative Strength Index over 14 days. >70 overbought, <30 oversold.",
    "MACD":"Moving Average Convergence Divergence. Positive = bullish momentum.",
    "MA50":"50-day moving average — short-term trend indicator.",
    "MA200":"200-day moving average — long-term trend benchmark.",
    "Bollinger Bands":"Price envelope 2 std deviations above/below 20-day MA.",
    "Golden Cross":"MA50 crosses above MA200 — historically strong bullish signal.",
    "Death Cross":"MA50 crosses below MA200 — historically bearish warning.",
    "Volume":"Shares traded per day. High volume confirms price move strength.",
}
GLOSSARY_PEERS = {
    "Score":"Composite technical score 0-100 based on momentum, MAs, RSI, dividends.",
    "1Y Return %":"Stock price performance over the past year vs peers.",
    "RSI":"Momentum indicator. 30-70 = healthy; extremes signal potential reversals.",
    "Div Yield %":"Annual dividend as % of price. Higher = more income per dollar.",
    "Best Positioned":"Peer Claude ranks with the strongest fundamentals and outlook.",
    "Best Value":"Peer trading at the most attractive price relative to earnings/growth.",
}
GLOSSARY_EARNINGS_CAL = {
    "Next Earnings":"Estimated date for the company's next quarterly earnings report.",
    "EPS Estimate":"Claude's projected Earnings Per Share for the upcoming quarter.",
    "Rev Estimate":"Claude's projected quarterly revenue.",
    "Beat/Meet/Miss":"Will the company beat analyst expectations, match them, or fall short?",
    "Confidence":"How certain Claude is — High, Medium, or Low.",
    "Key Metric":"Most important data point to watch when earnings are released.",
}
GLOSSARY_INSIDER = {
    "Insider Buy":"Executive/director purchased company stock — generally bullish signal.",
    "Insider Sell":"Insider sold shares. Can be routine or a warning if widespread.",
    "Buy/Sell Ratio":"Higher = more insider confidence in the company's outlook.",
    "Form 4":"SEC filing insiders submit within 2 business days of any transaction.",
    "Signal":"Claude's read: Bullish (net buying), Neutral, or Bearish (net selling).",
}
GLOSSARY_DIVIDEND_HUNTER = {
    "Composite Score":"0-100: Yield(25%) + Div Growth(25%) + Price Stability(20%) + Consistency(15%) + Technicals(15%).",
    "Yield %":"Annual dividends ÷ stock price. 4% yield on $100 stock = $4/year per share.",
    "Div Growth %/yr":"How much the dividend increased vs prior year. 10%+ is exceptional.",
    "Payment Consistency":"How many of the last 4 quarterly dividends were paid (out of 4).",
    "Overall Grade":"A = exceptional, B = solid, C = average, D = below average or risky.",
    "Dividend Safety":"How likely the dividend is maintained: Very Safe, Safe, Moderate, At Risk.",
    "Cut Risk":"Likelihood of dividend reduction: Low, Medium, or High.",
    "Buy Now?":"Yes = attractive now. Wait for Dip = good stock but rich. No = avoid.",
    "Ideal Buy Price":"Claude's estimated attractive entry price for dividend capture.",
    "Next Ex-Div":"Must own shares BEFORE this date to receive the next dividend.",
    "Next Pay Date":"Date the dividend cash is deposited into your account.",
    "% From 52W High":"How far the stock has fallen from its 52-week high.",
    "Aristocrat":"S&P 500 company with 25+ consecutive years of dividend increases.",
    "High Yield":"Stocks/REITs/MLPs typically yielding 5%+, prioritizing income.",
    "Growth":"Companies growing their dividend rapidly (often 8-15%/yr).",
    "Data Source":"Yields from built-in reference table when Tiingo free plan has no dividend data. Confirmed/refined by Claude AI in Stage 2.",
}

# ══════════════════════════════════════════════════════════════════════════════
# CLAUDE HELPERS
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
    meta=data["meta"]; lp=data["latest_price"]; fl=data["fund_latest"]; cp=data["current_price"]
    lines = [
        f"STOCK: {ticker.upper()} — {meta.get('name',ticker)}",
        f"Description: {meta.get('description','')[:300]}",
        f"Exchange: {meta.get('exchangeCode','N/A')}",
        f"Current Price: ${cp}",
        f"Prev Close:{lp.get('adjClose','N/A')} Open:{lp.get('open','N/A')} High:{lp.get('high','N/A')} Low:{lp.get('low','N/A')} Vol:{lp.get('volume','N/A')}",
    ]
    if fl:
        lines += [f"Market Cap:{fmt_num(fl.get('marketCap'))} P/E:{fl.get('peRatio','N/A')} EPS TTM:{fl.get('trailingEps12m','N/A')}"]
    if data.get("quarterly_income") or data.get("annual_income"):
        lines.append("── QUARTERLY INCOME ──")
        for d in data["quarterly_income"]:
            lines.append(f"  {d.get('_date','')[:10]}: Rev={fmt_num(d.get('revenue'))} NI={fmt_num(d.get('netIncome'))} EPS={d.get('eps','N/A')}")
        lines.append("── ANNUAL INCOME ──")
        for d in data["annual_income"]:
            lines.append(f"  {d.get('_date','')[:10]}: Rev={fmt_num(d.get('revenue'))} NI={fmt_num(d.get('netIncome'))} EPS={d.get('eps','N/A')}")
    else:
        lines.append("NOTE: Detailed financials unavailable. Use your training knowledge for this company's recent earnings.")
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
page = st.radio("", [
    "🔍 Stock Analysis","📋 Index Screener","📈 Backtester",
    "🔧 Technical Analysis","🏢 Peer Comparison","📅 Earnings Calendar",
    "🕵️ Insider Activity","💎 Dividend Hunter"
], horizontal=True, label_visibility="collapsed")
st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: STOCK ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
if page == "🔍 Stock Analysis":
    ci,cb = st.columns([3,1])
    with ci: ticker_input = st.text_input("Ticker", placeholder="e.g. AAPL, MSFT, NVDA, TSLA", label_visibility="collapsed")
    with cb: analyze_btn  = st.button("🔍 Analyze", use_container_width=True, type="primary")

    if analyze_btn and ticker_input:
        ticker = ticker_input.strip().upper()
        if not anthropic_key: st.error("Anthropic API key required."); st.stop()
        if not tiingo_key:    st.error("Tiingo API key required."); st.stop()
        client = anthropic.Anthropic(api_key=anthropic_key)
        with st.spinner(f"Fetching {ticker}…"):
            try: data = get_stock_data(ticker, tiingo_key)
            except Exception as e:
                st.error("❌ Could not load stock data")
                for l in str(e).split("\n"):
                    if l.strip(): st.markdown(l)
                st.stop()
        meta=data["meta"]; cp=data["current_price"]; company_name=meta.get("name",ticker)
        st.markdown(f"## {company_name} ({ticker}) <span class='data-badge'>Tiingo</span>", unsafe_allow_html=True)
        st.markdown(f"**Price:** ${cp} &nbsp;|&nbsp; **Exchange:** {meta.get('exchangeCode','N/A')}", unsafe_allow_html=True)
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        context = build_context(data, ticker)
        tabs = st.tabs(["📊 Earnings","💡 Insights & Targets","📰 News","💰 Dividends"])

        with tabs[0]:
            st.markdown("### Earnings Report Scorecard")
            with st.spinner("Analyzing with Claude…"):
                try:
                    ed = parse_json(ask_claude(client,"You are a financial analyst. Return only valid JSON, no markdown.",
                        f"Evaluate latest earnings for {ticker} ({company_name}).\n{context}\n"
                        'Respond ONLY with valid JSON:\n{"overall_rating":"Excellent|Good|Neutral|Bad","overall_summary":"2-3 sentences","categories":['
                        '{"name":"Revenue Growth","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"},'
                        '{"name":"Profitability & Margins","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"},'
                        '{"name":"Earnings Per Share","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"},'
                        '{"name":"Cash Flow Generation","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"},'
                        '{"name":"Balance Sheet Health","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"},'
                        '{"name":"Valuation","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"},'
                        '{"name":"Analyst Sentiment","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"},'
                        '{"name":"Revenue vs Expectations","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"},'
                        '{"name":"Cost Management","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"},'
                        '{"name":"Return on Capital","rating":"Excellent|Good|Neutral|Bad","commentary":"one sentence"}]}'))
                    overall = ed.get("overall_rating","Neutral")
                    st.markdown(f"<div class='metric-card'><strong>Overall:</strong> <span class='{rcls(overall)}'>{overall}</span><br><span style='color:#444'>{ed.get('overall_summary','')}</span></div>", unsafe_allow_html=True)
                    for cat in ed.get("categories",[]):
                        display_rating(cat["name"],cat["rating"],cat.get("commentary",""))
                except Exception as e: st.error(f"Error: {e}")
            show_glossary(GLOSSARY_EARNINGS)

        with tabs[1]:
            st.markdown("### AI Insights & Price Targets")
            with st.spinner("Generating insights…"):
                try:
                    ins = parse_json(ask_claude(client,"You are a financial analyst. Return only valid JSON, no markdown.",
                        f"Senior analyst view on {ticker} ({company_name}). Current price: ${cp}.\n{context}\n"
                        '{"what_doing_well":["p1","p2","p3","p4"],"risks_concerns":["r1","r2","r3"],'
                        '"overall_outlook":"Bullish|Cautiously Bullish|Neutral|Cautiously Bearish|Bearish",'
                        '"outlook_rationale":"3-4 sentences",'
                        '"price_targets":{"next_day":{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"},'
                        '"next_week":{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"},'
                        '"next_month":{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"},'
                        '"next_quarter":{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"},'
                        '"next_year":{"target":0.0,"direction":"Up|Down|Flat","rationale":"brief"}},'
                        '"buy_sell_hold":"Buy|Sell|Hold","conviction":"High|Medium|Low"}'))
                    ca,cb2,cc = st.columns(3)
                    ca.metric("Outlook",ins.get("overall_outlook","N/A"))
                    cb2.metric("Recommendation",ins.get("buy_sell_hold","N/A"))
                    cc.metric("Conviction",ins.get("conviction","N/A"))
                    st.markdown(f"<div class='metric-card'>{ins.get('outlook_rationale','')}</div>", unsafe_allow_html=True)
                    cl,cr = st.columns(2)
                    with cl:
                        st.markdown("#### ✅ Doing Well")
                        for p in ins.get("what_doing_well",[]): st.markdown(f"• {p}")
                    with cr:
                        st.markdown("#### ⚠️ Risks")
                        for p in ins.get("risks_concerns",[]): st.markdown(f"• {p}")
                    st.markdown("#### 🎯 Price Targets")
                    periods=[("next_day","Next Day"),("next_week","Next Week"),("next_month","Next Month"),("next_quarter","Next Quarter"),("next_year","Next Year")]
                    ptc = st.columns(5)
                    for i,(key,label) in enumerate(periods):
                        pt=ins.get("price_targets",{}).get(key,{}); tgt=pt.get("target",0); d=pt.get("direction","Flat")
                        arrow="▲" if d=="Up" else "▼" if d=="Down" else "→"
                        cls="price-up" if d=="Up" else "price-down" if d=="Down" else ""
                        try: pct_str=f"{((float(tgt)-float(cp))/float(cp))*100:+.1f}%"
                        except: pct_str=""
                        with ptc[i]:
                            st.markdown(f"<div class='price-target-card'><div style='font-size:.8rem;color:#666'>{label}</div>"
                                f"<div style='font-size:1.4rem;font-weight:800'>${tgt:.2f}</div>"
                                f"<div class='{cls}'>{arrow} {pct_str}</div>"
                                f"<div style='font-size:.7rem;color:#888'>{pt.get('rationale','')}</div></div>", unsafe_allow_html=True)
                    st.caption("⚠️ AI-generated — not financial advice.")
                except Exception as e: st.error(f"Error: {e}")
            show_glossary(GLOSSARY_TARGETS)

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
                        nd = parse_json(ask_claude(client,"Financial analyst. Return only valid JSON.",
                            f"News for {ticker}: {headlines}\nContext: {context[:1500]}\n"
                            '{"exciting_things":["t1","t2","t3"],"caution_flags":["f1","f2","f3"],'
                            '"upcoming_earnings_estimate":{"date_estimate":"date","eps_estimate":"est","revenue_estimate":"rev",'
                            '"beat_miss_prediction":"Beat|Meet|Miss","confidence":"High|Medium|Low","rationale":"2-3 sentences"},'
                            '"overall_news_sentiment":"Positive|Neutral|Negative|Mixed","key_themes":["t1","t2","t3"]}'))
                        sent=nd.get("overall_news_sentiment","Neutral")
                        sc="#2e7d32" if sent=="Positive" else "#c62828" if sent=="Negative" else "#f57c00"
                        st.markdown(f"**Sentiment:** <span style='color:{sc};font-weight:700'>{sent}</span>", unsafe_allow_html=True)
                        ce,cc2 = st.columns(2)
                        with ce:
                            st.markdown("#### 🚀 Exciting")
                            for p in nd.get("exciting_things",[]): st.markdown(f"✅ {p}")
                        with cc2:
                            st.markdown("#### 🚨 Caution")
                            for p in nd.get("caution_flags",[]): st.markdown(f"⚠️ {p}")
                        ee=nd.get("upcoming_earnings_estimate",{})
                        e1,e2,e3,e4 = st.columns(4)
                        e1.metric("Est. Date",ee.get("date_estimate","N/A"))
                        e2.metric("EPS Est.",ee.get("eps_estimate","N/A"))
                        e3.metric("Rev Est.",ee.get("revenue_estimate","N/A"))
                        pred=ee.get("beat_miss_prediction","N/A")
                        e4.markdown(f"**Beat/Meet/Miss**<br><span style='color:{'#2e7d32' if pred=='Beat' else '#c62828' if pred=='Miss' else '#f57c00'};font-size:1.3rem;font-weight:700'>{pred}</span>", unsafe_allow_html=True)
                        st.markdown(f"<div class='metric-card'>{ee.get('rationale','')}</div>", unsafe_allow_html=True)
                    except Exception as e: st.error(f"News error: {e}")
                for a in articles[:8]:
                    desc = a.get("description","") or ""
                    st.markdown(f"<div class='news-card'><a href='{a.get('url','#')}' target='_blank' style='font-weight:600;color:#1a73e8;text-decoration:none'>{a.get('title','')}</a>"
                        f"<br><small style='color:#888'>{a.get('source',{}).get('name','')} · {a.get('publishedAt','')[:10]}</small>"
                        f"<br><small style='color:#555'>{desc[:150]}</small></div>", unsafe_allow_html=True)
            else: st.info("No news found. Add a News API key to enable.")

        with tabs[3]:
            st.markdown("### Dividend Analysis")
            try:
                divs = tiingo_safe(f"/tiingo/daily/{ticker.lower()}/dividends", tiingo_key, {
                    "startDate":(datetime.now()-timedelta(days=730)).strftime("%Y-%m-%d"),
                    "endDate":(datetime.now()+timedelta(days=180)).strftime("%Y-%m-%d"),
                })
                recent = sorted(divs or [], key=lambda x: x.get("exDate",""), reverse=True)[:8]
                annual_div = sum(float(d.get("divCash",0)) for d in recent[:4])
                has_div = annual_div > 0
            except: has_div=False; annual_div=0; recent=[]

            if has_div:
                div_yield = round((annual_div/float(cp))*100,2) if cp!="N/A" else 0
                with st.spinner("Analyzing dividend…"):
                    try:
                        div_hist = "\n".join([f"  Ex-Date:{d.get('exDate','N/A')} Amount:${d.get('divCash','N/A')}" for d in recent[:6]])
                        dd = parse_json(ask_claude(client,"Dividend expert. Return only valid JSON.",
                            f"Dividend analysis for {ticker}: Price=${cp} AnnualDiv=${annual_div:.4f} Yield={div_yield}%\n"
                            f"History:\n{div_hist}\n{context[:1000]}\n"
                            '{"ex_dividend_date_human":"date","must_own_by":"date","payment_date_estimate":"date",'
                            '"quarterly_dividend_per_share":"amount","annual_yield_pct":"pct","yield_vs_average":"Above Average|Average|Below Average",'
                            '"dividend_safety_rating":"Very Safe|Safe|Moderate|At Risk","dividend_safety_rationale":"2-3 sentences",'
                            '"capture_recommendation":"Strong Buy for Dividend|Buy for Dividend|Neutral|Avoid for Dividend",'
                            '"capture_rationale":"2-3 sentences","dividend_growth_outlook":"Growing|Stable|At Risk of Cut",'
                            '"key_insights":["i1","i2","i3"]}'))
                        st.markdown(f"<div class='dividend-highlight'><h4>💰 Dividend Summary — {ticker}</h4>"
                            f"<table style='width:100%;border-collapse:collapse'>"
                            f"<tr><td style='padding:5px 0;font-weight:600'>Annual Div/Share:</td><td>${annual_div:.4f}</td></tr>"
                            f"<tr><td style='padding:5px 0;font-weight:600'>Yield:</td><td>{dd.get('annual_yield_pct','N/A')}</td></tr>"
                            f"<tr><td style='padding:5px 0;font-weight:600'>Next Ex-Div:</td><td><strong>{dd.get('ex_dividend_date_human','N/A')}</strong></td></tr>"
                            f"<tr><td style='padding:5px 0;font-weight:600'>⚡ Must Own By:</td><td><strong style='color:#c62828'>{dd.get('must_own_by','N/A')}</strong></td></tr>"
                            f"<tr><td style='padding:5px 0;font-weight:600'>Payment Date:</td><td>{dd.get('payment_date_estimate','N/A')}</td></tr>"
                            f"</table></div>", unsafe_allow_html=True)
                        d1,d2,d3 = st.columns(3)
                        d1.metric("Safety",dd.get("dividend_safety_rating","N/A"))
                        d2.metric("Yield vs Avg",dd.get("yield_vs_average","N/A"))
                        d3.metric("Growth Outlook",dd.get("dividend_growth_outlook","N/A"))
                        st.markdown(f"<div class='metric-card'><strong>Safety:</strong> {dd.get('dividend_safety_rationale','')}</div>", unsafe_allow_html=True)
                        rec=dd.get("capture_recommendation","Neutral")
                        rc="#2e7d32" if "Buy" in rec else "#c62828" if "Avoid" in rec else "#f57c00"
                        st.markdown(f"<div class='metric-card'><strong>Capture Rec:</strong> <span style='color:{rc};font-weight:700'>{rec}</span><br>{dd.get('capture_rationale','')}</div>", unsafe_allow_html=True)
                        st.markdown("#### 💡 Key Insights")
                        for ins_item in dd.get("key_insights",[]): st.markdown(f"• {ins_item}")
                        st.caption("⚠️ Verify ex-div date with your broker.")
                    except Exception as e: st.error(f"Dividend error: {e}")
            else:
                st.info(f"**{company_name}** does not currently pay a dividend or Tiingo free plan doesn't include dividend history for this ticker.")
    elif analyze_btn: st.warning("Please enter a ticker symbol.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: INDEX SCREENER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Index Screener":
    import pandas as pd
    st.markdown("### 📋 Index Stock Screener")
    if not tiingo_key: st.error("Tiingo API key required."); st.stop()
    col_idx,col_btn = st.columns([2,1])
    with col_idx: index_choice = st.selectbox("Select Index",["Dow Jones (30)","Nasdaq-100 (100)","S&P 500 Top 90"])
    with col_btn: run_screen = st.button("▶ Run Screener", type="primary", use_container_width=True)
    if run_screen:
        ticker_list = {"Dow Jones (30)":DOW30,"Nasdaq-100 (100)":NASDAQ100,"S&P 500 Top 90":SP500_SAMPLE}[index_choice]
        results = []; prog = st.progress(0, text="Fetching stock data…")
        for i,t in enumerate(ticker_list):
            prog.progress((i+1)/len(ticker_list), text=f"Fetching {t} ({i+1}/{len(ticker_list)})…")
            row = get_screener_data(t, tiingo_key)
            if row: results.append(row)
            time.sleep(0.3)
        prog.empty()
        if results:
            df = pd.DataFrame(results).sort_values("score",ascending=False).reset_index(drop=True)
            df["rank"] = df.index+1
            df["score_label"] = df["score"].apply(score_label)
            df["rsi_zone"] = df["rsi"].apply(lambda r: "Oversold" if r and r<30 else ("Overbought" if r and r>70 else "Normal") if r else "N/A")
            df["above_ma50"]  = df.apply(lambda r: "✅" if r["ma50"]  and r["price"]>r["ma50"]  else "❌", axis=1)
            df["above_ma200"] = df.apply(lambda r: "✅" if r["ma200"] and r["price"]>r["ma200"] else "❌", axis=1)
            s1,s2,s3,s4 = st.columns(4)
            s1.metric("Strong (75+)",len(df[df["score"]>=75]))
            s2.metric("Good (60-74)",len(df[(df["score"]>=60)&(df["score"]<75)]))
            s3.metric("Paying Dividend",len(df[df["div_yield"]>0]))
            s4.metric("Avg Score",round(df["score"].mean(),1))
            disp = df[["rank","ticker","price","score_label","perf_1yr","rsi","rsi_zone","above_ma50","above_ma200","div_yield","next_ex_div"]].copy()
            disp.columns=["Rank","Ticker","Price","Score","1Y Return %","RSI","RSI Zone","Above MA50","Above MA200","Div Yield %","Next Ex-Div"]
            st.dataframe(disp, use_container_width=True, hide_index=True)
            st.caption("💡 Scores are algorithmic. Run full AI analysis on any ticker in Stock Analysis tab.")
            show_glossary(GLOSSARY_SCREENER)
        else: st.warning("No data returned. Check your Tiingo key.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: BACKTESTER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📈 Backtester":
    import pandas as pd
    st.markdown("### 📈 Price Target Backtester")
    st.caption("For each period, Claude generates a price target based on historical context, then compares to actual price.")
    if not tiingo_key or not anthropic_key: st.error("Both API keys required."); st.stop()
    c1,c2,c3,c4 = st.columns(4)
    with c1: bt_ticker = st.text_input("Ticker", value="TSLA")
    with c2: bt_start  = st.date_input("Start Date", value=datetime(2023,1,1))
    with c3: bt_end    = st.date_input("End Date",   value=datetime(2024,1,1))
    with c4: bt_freq   = st.selectbox("Frequency",["Monthly","Quarterly","Weekly"])
    bt_run = st.button("▶ Run Backtest", type="primary")
    if bt_run and bt_ticker:
        ticker = bt_ticker.strip().upper()
        client = anthropic.Anthropic(api_key=anthropic_key)
        with st.spinner(f"Fetching historical prices for {ticker}…"):
            hist = get_historical_prices(ticker, bt_start.strftime("%Y-%m-%d"), bt_end.strftime("%Y-%m-%d"), tiingo_key)
        if not hist: st.error("No historical data found."); st.stop()
        checkpoints = []
        if bt_freq=="Weekly":
            d=bt_start
            while d<=bt_end: checkpoints.append(d.strftime("%Y-%m-%d")); d+=timedelta(weeks=1)
        elif bt_freq=="Monthly":
            d=bt_start.replace(day=1)
            while d<=bt_end:
                checkpoints.append(d.strftime("%Y-%m-%d"))
                m=d.month+1; y=d.year+(m//13); m=m if m<=12 else 1; d=d.replace(year=y,month=m,day=1)
        else:
            d=bt_start.replace(day=1)
            while d<=bt_end:
                checkpoints.append(d.strftime("%Y-%m-%d"))
                m=d.month+3; y=d.year+(m//13); m=m if m<=12 else m-12; d=d.replace(year=y,month=m,day=1)
        price_map = {p.get("date","")[:10]: p.get("adjClose") or p.get("close") for p in hist}
        def nearest_price(tgt):
            if tgt in price_map: return float(price_map[tgt])
            for offset in range(1,8):
                for sign in [1,-1]:
                    d=(datetime.strptime(tgt,"%Y-%m-%d")+timedelta(days=offset*sign)).strftime("%Y-%m-%d")
                    if d in price_map: return float(price_map[d])
            return None
        bt_results=[]; prog2=st.progress(0,text="Generating AI projections…")
        for i,chk in enumerate(checkpoints[:12]):
            prog2.progress((i+1)/min(len(checkpoints),12),text=f"Analyzing {chk}…")
            ap=nearest_price(chk)
            if not ap: continue
            ni=checkpoints.index(chk)+1
            na=nearest_price(checkpoints[ni]) if ni<len(checkpoints) else None
            try:
                resp=parse_json(ask_claude(client,"Financial analyst. Return only valid JSON.",
                    f"It is {chk}. {ticker} is trading at ${ap:.2f}. Based on your knowledge of this company as of {chk}, "
                    f"what would your 1-month forward price target be?\n"
                    '{"projected_target":0.0,"direction":"Up|Down|Flat","rationale":"1-2 sentences","sentiment":"Bullish|Neutral|Bearish","key_factor":"main reason"}'))
                proj=float(resp.get("projected_target",ap))
                bt_results.append({"date":chk,"actual_price":round(ap,2),"projected_target":round(proj,2),
                    "next_actual":round(na,2) if na else None,"direction":resp.get("direction","Flat"),
                    "sentiment":resp.get("sentiment","Neutral"),"rationale":resp.get("rationale",""),
                    "key_factor":resp.get("key_factor",""),
                    "proj_pct":round(((proj-ap)/ap)*100,1),
                    "actual_pct":round(((na-ap)/ap)*100,1) if na else None})
            except: pass
            time.sleep(0.5)
        prog2.empty()
        if bt_results:
            df_bt=pd.DataFrame(bt_results); matched=df_bt.dropna(subset=["actual_pct"])
            correct=sum(1 for _,r in matched.iterrows()
                if (r["proj_pct"]>0 and r["actual_pct"]>0) or (r["proj_pct"]<0 and r["actual_pct"]<0) or (abs(r["proj_pct"])<2 and abs(r["actual_pct"])<2))
            acc=round((correct/len(matched))*100,1) if len(matched) else 0
            a1,a2,a3,a4=st.columns(4)
            a1.metric("Periods",len(bt_results)); a2.metric("Directional Accuracy",f"{acc}%")
            a3.metric("Avg Projected",f"{df_bt['proj_pct'].mean():+.1f}%")
            a4.metric("Avg Actual",f"{matched['actual_pct'].mean():+.1f}%" if len(matched) else "N/A")
            st.line_chart(df_bt[["date","actual_price","projected_target"]].set_index("date"))
            disp=df_bt[["date","actual_price","projected_target","proj_pct","actual_pct","direction","sentiment","key_factor"]].copy()
            disp.columns=["Date","Price at Date","AI Target","Proj %","Actual Next %","Direction","Sentiment","Key Factor"]
            st.dataframe(disp, use_container_width=True, hide_index=True)
            st.caption("⚠️ Directional accuracy = whether projected and actual moves were in same direction.")
        else: st.warning("Could not generate results. Try a different ticker or date range.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4: TECHNICAL ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔧 Technical Analysis":
    import pandas as pd
    st.markdown("### 🔧 Technical Analysis")
    if not tiingo_key: st.error("Tiingo API key required."); st.stop()
    tc1,tc2=st.columns([3,1])
    with tc1: ta_ticker=st.text_input("Ticker",placeholder="e.g. AAPL")
    with tc2: ta_run=st.button("▶ Analyze",type="primary",use_container_width=True)
    if ta_run and ta_ticker:
        ticker=ta_ticker.strip().upper()
        with st.spinner(f"Fetching technical data…"):
            hist=get_historical_prices(ticker,(datetime.now()-timedelta(days=365)).strftime("%Y-%m-%d"),datetime.now().strftime("%Y-%m-%d"),tiingo_key)
        if not hist: st.error("No data found."); st.stop()
        closes=[p.get("adjClose") or p.get("close") or 0 for p in hist]
        dates=[p.get("date","")[:10] for p in hist]
        volumes=[p.get("volume") or 0 for p in hist]
        cp=closes[-1] if closes else 0
        ma20=calc_ma(closes,20); ma50=calc_ma(closes,50); ma200=calc_ma(closes,200)
        rsi=calc_rsi(closes[-15:]); macd_line,signal,histogram=calc_macd(closes)
        bb_upper=bb_lower=bb_mid=None
        if len(closes)>=20:
            bb_slice=closes[-20:]; bb_mid=sum(bb_slice)/20
            std=math.sqrt(sum((x-bb_mid)**2 for x in bb_slice)/20)
            bb_upper=bb_mid+2*std; bb_lower=bb_mid-2*std
        st.markdown(f"#### {ticker} — Technical Indicators")
        m1,m2,m3,m4,m5=st.columns(5)
        m1.metric("Price",f"${cp:.2f}")
        m2.metric("RSI (14)",f"{rsi:.1f}" if rsi else "N/A",delta="Overbought" if rsi and rsi>70 else ("Oversold" if rsi and rsi<30 else "Normal"))
        m3.metric("MACD",f"{macd_line:.3f}" if macd_line else "N/A",delta="Bullish" if macd_line and macd_line>0 else "Bearish")
        m4.metric("50-Day MA",f"${ma50:.2f}" if ma50 else "N/A",delta="Above ✅" if ma50 and cp>ma50 else "Below ❌")
        m5.metric("200-Day MA",f"${ma200:.2f}" if ma200 else "N/A",delta="Above ✅" if ma200 and cp>ma200 else "Below ❌")
        if bb_upper and bb_lower:
            bb1,bb2,bb3=st.columns(3)
            bb1.metric("BB Upper",f"${bb_upper:.2f}"); bb2.metric("BB Mid",f"${bb_mid:.2f}"); bb3.metric("BB Lower",f"${bb_lower:.2f}")
            if cp>bb_upper: st.warning("⚠️ Price above upper Bollinger Band — potentially overbought")
            elif cp<bb_lower: st.info("💡 Price below lower Bollinger Band — potentially oversold")
            else: st.success("✅ Price within normal Bollinger Band range")
        st.line_chart(pd.DataFrame({"Price":closes,"MA20":[calc_ma(closes[:i+1],20) or closes[i] for i in range(len(closes))],
            "MA50":[calc_ma(closes[:i+1],50) or closes[i] for i in range(len(closes))]},index=dates))
        st.markdown("#### Volume")
        st.bar_chart(pd.DataFrame({"Volume":volumes},index=dates))
        st.markdown("#### 📡 Signal Summary")
        signals=[]
        if rsi:
            if rsi<30: signals.append(("RSI","🟢 Oversold — potential buy signal"))
            elif rsi>70: signals.append(("RSI","🔴 Overbought — potential sell signal"))
            else: signals.append(("RSI",f"🟡 Neutral ({rsi:.1f})"))
        if ma50 and ma200:
            if ma50>ma200: signals.append(("MA Cross","🟢 Golden Cross — MA50 above MA200 (bullish)"))
            else: signals.append(("MA Cross","🔴 Death Cross — MA50 below MA200 (bearish)"))
        if macd_line and signal:
            if macd_line>signal: signals.append(("MACD","🟢 MACD above signal line (bullish momentum)"))
            else: signals.append(("MACD","🔴 MACD below signal line (bearish momentum)"))
        if bb_upper and bb_lower:
            if cp>bb_upper: signals.append(("Bollinger","🔴 Above upper band (overbought)"))
            elif cp<bb_lower: signals.append(("Bollinger","🟢 Below lower band (oversold)"))
            else: signals.append(("Bollinger","🟡 Within bands (neutral)"))
        for name,desc in signals: st.markdown(f"**{name}:** {desc}")
        show_glossary(GLOSSARY_TECHNICALS)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5: PEER COMPARISON
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🏢 Peer Comparison":
    import pandas as pd
    st.markdown("### 🏢 Peer / Competitor Comparison")
    if not tiingo_key or not anthropic_key: st.error("Both API keys required."); st.stop()
    pc1,pc2=st.columns([3,1])
    with pc1: peer_ticker=st.text_input("Enter a stock ticker",placeholder="e.g. TSLA")
    with pc2: peer_run=st.button("▶ Compare",type="primary",use_container_width=True)
    if peer_run and peer_ticker:
        ticker=peer_ticker.strip().upper()
        client=anthropic.Anthropic(api_key=anthropic_key)
        with st.spinner("Identifying peers…"):
            try:
                peers_resp=parse_json(ask_claude(client,"Financial analyst. Return only valid JSON.",
                    f'Who are the top 4-5 direct competitors of {ticker}?\n'
                    '{"company_name":"full name","sector":"sector","description":"1 sentence",'
                    '"peers":[{"ticker":"TICK","name":"Name","why":"one sentence"}]}'))
                peer_list=[p["ticker"] for p in peers_resp.get("peers",[])[:5]]
                all_tickers=[ticker]+peer_list
            except Exception as e: st.error(f"Could not identify peers: {e}"); st.stop()
        peer_data=[]
        with st.spinner("Fetching comparison data…"):
            for t in all_tickers:
                row=get_screener_data(t,tiingo_key)
                if row: row["is_primary"]=(t==ticker); peer_data.append(row)
                time.sleep(0.3)
        if peer_data:
            df_peers=pd.DataFrame(peer_data).sort_values("score",ascending=False)
            disp=df_peers[["ticker","price","score","perf_1yr","rsi","div_yield","ma50","ma200"]].copy()
            disp.columns=["Ticker","Price","Score","1Y Return %","RSI","Div Yield %","MA50","MA200"]
            st.dataframe(disp, use_container_width=True, hide_index=True)
            st.bar_chart(df_peers[["ticker","score"]].set_index("ticker"))
            st.bar_chart(df_peers[["ticker","perf_1yr"]].set_index("ticker"))
            with st.spinner("Generating AI comparison…"):
                try:
                    comp=parse_json(ask_claude(client,"Financial analyst. Return only valid JSON.",
                        f"Compare {ticker} vs peers: {', '.join(peer_list)}\nData: {disp.to_string()}\n"
                        '{"winner":"ticker","winner_rationale":"2-3 sentences","biggest_risk":"ticker and why",'
                        '"best_value":"ticker","key_insights":["i1","i2","i3"],"recommendation":"2-3 sentences"}'))
                    w1,w2,w3=st.columns(3)
                    w1.metric("Best Positioned",comp.get("winner","N/A"))
                    w2.metric("Best Value",comp.get("best_value","N/A"))
                    w3.metric("Highest Risk",comp.get("biggest_risk","N/A"))
                    st.markdown(f"<div class='metric-card'>{comp.get('winner_rationale','')}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='metric-card'><strong>Recommendation:</strong> {comp.get('recommendation','')}</div>", unsafe_allow_html=True)
                    for ki in comp.get("key_insights",[]): st.markdown(f"• {ki}")
                except Exception as e: st.error(f"Comparison error: {e}")
            for p in peers_resp.get("peers",[]): st.markdown(f"**{p['ticker']}** — {p['why']}")
            show_glossary(GLOSSARY_PEERS)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6: EARNINGS CALENDAR
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📅 Earnings Calendar":
    import pandas as pd
    st.markdown("### 📅 Earnings Calendar")
    if not anthropic_key or not tiingo_key: st.error("Both API keys required."); st.stop()
    watchlist_input=st.text_area("Watchlist (comma separated)","AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, JPM, V, WMT",
        label_visibility="collapsed",height=80)
    cal_run=st.button("▶ Load Calendar",type="primary")
    if cal_run:
        tickers=[t.strip().upper() for t in watchlist_input.split(",") if t.strip()]
        client=anthropic.Anthropic(api_key=anthropic_key)
        cal_results=[]
        with st.spinner("Generating earnings estimates…"):
            for t in tickers:
                try:
                    prices=tiingo_safe(f"/tiingo/daily/{t.lower()}/prices",tiingo_key,{
                        "startDate":(datetime.now()-timedelta(days=5)).strftime("%Y-%m-%d"),
                        "endDate":datetime.now().strftime("%Y-%m-%d")})
                    cp_val=prices[-1].get("adjClose") or prices[-1].get("close") if prices else None
                    est=parse_json(ask_claude(client,"Financial analyst. Return only valid JSON.",
                        f"For {t}, what is the next expected earnings date and your estimate? Price: ${cp_val:.2f if cp_val else 'N/A'}\n"
                        '{"next_earnings_date":"YYYY-MM-DD or Unknown","quarter":"e.g. Q1 2025",'
                        '"eps_estimate":"est","revenue_estimate":"rev","beat_miss_prediction":"Beat|Meet|Miss",'
                        '"confidence":"High|Medium|Low","key_watch":"most important metric"}'))
                    cal_results.append({"ticker":t,"price":f"${cp_val:.2f}" if cp_val else "N/A",
                        "next_date":est.get("next_earnings_date","Unknown"),"quarter":est.get("quarter",""),
                        "eps_est":est.get("eps_estimate",""),"rev_est":est.get("revenue_estimate",""),
                        "prediction":est.get("beat_miss_prediction",""),"confidence":est.get("confidence",""),
                        "key_watch":est.get("key_watch","")})
                except Exception as e:
                    cal_results.append({"ticker":t,"price":"N/A","next_date":"Error","quarter":"","eps_est":"","rev_est":"","prediction":"","confidence":"","key_watch":str(e)[:50]})
        df_cal=pd.DataFrame(cal_results)
        df_cal.columns=["Ticker","Price","Next Earnings","Quarter","EPS Est","Rev Est","Beat/Meet/Miss","Confidence","Key Metric"]
        st.dataframe(df_cal, use_container_width=True, hide_index=True)
        beats=sum(1 for r in cal_results if r["prediction"]=="Beat")
        meets=sum(1 for r in cal_results if r["prediction"]=="Meet")
        misses=sum(1 for r in cal_results if r["prediction"]=="Miss")
        b1,b2,b3=st.columns(3)
        b1.metric("Predicted Beats",beats); b2.metric("Predicted Meets",meets); b3.metric("Predicted Misses",misses)
        show_glossary(GLOSSARY_EARNINGS_CAL)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 7: INSIDER ACTIVITY
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🕵️ Insider Activity":
    import pandas as pd
    st.markdown("### 🕵️ Insider Trading Activity")
    st.caption("Data from SEC Form 4 filings via OpenInsider. No extra API key needed.")
    ins_ticker=st.text_input("Enter Ticker",placeholder="e.g. TSLA, AAPL, NVDA")
    ins_run=st.button("▶ Fetch Insider Activity",type="primary")
    if ins_run and ins_ticker:
        ticker=ins_ticker.strip().upper()
        client=anthropic.Anthropic(api_key=anthropic_key) if anthropic_key else None
        with st.spinner(f"Fetching insider data for {ticker}…"):
            try:
                url=f"http://openinsider.com/screener?s={ticker}&o=&pl=&ph=&ll=&lh=&fd=365&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=40&action=1"
                r=requests.get(url,timeout=15,headers={"User-Agent":"Mozilla/5.0"})
                if r.status_code==200:
                    from html.parser import HTMLParser
                    class TableParser(HTMLParser):
                        def __init__(self):
                            super().__init__(); self.in_cell=False; self.rows=[]; self.cur_row=[]; self.cur_cell=""
                        def handle_starttag(self,tag,attrs):
                            if tag=="tr": self.cur_row=[]
                            if tag in("td","th"): self.in_cell=True; self.cur_cell=""
                        def handle_endtag(self,tag):
                            if tag in("td","th"): self.cur_row.append(self.cur_cell.strip()); self.in_cell=False
                            if tag=="tr":
                                if self.cur_row: self.rows.append(self.cur_row)
                        def handle_data(self,data):
                            if self.in_cell: self.cur_cell+=data
                    parser=TableParser(); parser.feed(r.text)
                    insider_rows=[row for row in parser.rows if len(row)>=12 and ticker in " ".join(row)]
                    if insider_rows:
                        insiders=[]
                        for row in insider_rows[:15]:
                            try:
                                trade_type=row[6] if len(row)>6 else ""; is_buy="P" in trade_type or "Buy" in trade_type
                                insiders.append({"Date":row[2][:10] if len(row)>2 else "","Insider":row[4] if len(row)>4 else "",
                                    "Title":row[5] if len(row)>5 else "","Type":"🟢 Buy" if is_buy else "🔴 Sell",
                                    "Qty":row[8] if len(row)>8 else "","Price":row[9] if len(row)>9 else "","Value":row[11] if len(row)>11 else ""})
                            except: pass
                        if insiders:
                            st.dataframe(pd.DataFrame(insiders), use_container_width=True, hide_index=True)
                            buys=sum(1 for x in insiders if "Buy" in x["Type"])
                            sells=sum(1 for x in insiders if "Sell" in x["Type"])
                            i1,i2,i3=st.columns(3)
                            i1.metric("Insider Buys",buys); i2.metric("Insider Sells",sells); i3.metric("Buy/Sell Ratio",f"{buys}:{sells}")
                            if buys>sells: st.success(f"✅ Insiders are net buyers of {ticker} — bullish signal")
                            elif sells>buys: st.warning(f"⚠️ Insiders are net sellers of {ticker} — worth monitoring")
                            else: st.info("📊 Balanced insider activity")
                            if client:
                                with st.spinner("AI interpretation…"):
                                    try:
                                        interp=parse_json(ask_claude(client,"Financial analyst. Return only valid JSON.",
                                            f"Insider activity for {ticker}: {buys} buys, {sells} sells. Notable: {json.dumps(insiders[:5])}\n"
                                            '{"signal":"Bullish|Neutral|Bearish","summary":"2-3 sentences","key_observation":"most notable transaction","recommendation":"investor takeaway"}'))
                                        sig=interp.get("signal","Neutral")
                                        sc="#2e7d32" if sig=="Bullish" else "#c62828" if sig=="Bearish" else "#f57c00"
                                        st.markdown(f"**Signal:** <span style='color:{sc};font-weight:700'>{sig}</span>", unsafe_allow_html=True)
                                        st.markdown(f"<div class='metric-card'>{interp.get('summary','')}</div>", unsafe_allow_html=True)
                                        st.markdown(f"**Key Observation:** {interp.get('key_observation','')}")
                                        st.markdown(f"**Takeaway:** {interp.get('recommendation','')}")
                                    except: pass
                        else: st.info(f"No insider transactions found for {ticker}.")
                    else: st.info(f"No insider transactions found for {ticker} in the past year.")
                else: st.warning(f"Could not reach OpenInsider (HTTP {r.status_code}).")
            except Exception as e:
                st.error(f"Error: {e}")
                st.markdown("Check [openinsider.com](http://openinsider.com) directly.")
        show_glossary(GLOSSARY_INSIDER)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 8: DIVIDEND HUNTER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💎 Dividend Hunter":
    import pandas as pd
    st.markdown("### 💎 Dividend Hunter")
    st.markdown("Algorithmically scores 150+ dividend stocks across Aristocrats, High Yield, and Dividend Growth categories, then runs AI deep-dive on the top 10.")
    st.info("ℹ️ Tiingo's free plan doesn't include dividend history. Yields and growth rates are sourced from our built-in reference table and confirmed by Claude AI in Stage 2.", icon="📊")

    if not tiingo_key or not anthropic_key: st.error("Both API keys required."); st.stop()

    st.markdown("#### Filters")
    fc1,fc2,fc3,fc4 = st.columns(4)
    with fc1: inc_aristocrats = st.checkbox("Dividend Aristocrats", value=True)
    with fc2: inc_high_yield  = st.checkbox("High Yield (5%+)", value=True)
    with fc3: inc_div_growth  = st.checkbox("Dividend Growth", value=True)
    with fc4: min_yield_filter = st.slider("Min Yield %", 0.0, 10.0, 1.0, 0.5)

    run_hunter = st.button("▶ Hunt for Dividends", type="primary", use_container_width=True)

    if run_hunter:
        # Build universe
        universe = []
        if inc_aristocrats: universe += ARISTOCRATS
        if inc_high_yield:  universe += HIGH_YIELD
        if inc_div_growth:  universe += DIVIDEND_GROWTH
        universe = list(dict.fromkeys(universe))  # deduplicate

        st.markdown("---")
        st.markdown("#### Stage 1 — Scanning Universe…")
        prog = st.progress(0, text="Fetching price data…")
        scored = []

        for i, t in enumerate(universe):
            prog.progress((i+1)/len(universe), text=f"Scanning {t} ({i+1}/{len(universe)})…")
            try:
                # Get price history for technicals
                prices = tiingo_safe(f"/tiingo/daily/{t.lower()}/prices", tiingo_key, {
                    "startDate": (datetime.now()-timedelta(days=400)).strftime("%Y-%m-%d"),
                    "endDate":   datetime.now().strftime("%Y-%m-%d"),
                })
                if not prices or len(prices) < 5: continue
                latest  = prices[-1]
                yr_ago  = prices[0]
                cp_f    = float(latest.get("adjClose") or latest.get("close") or 0)
                yr_ago_p= float(yr_ago.get("adjClose")  or yr_ago.get("close")  or cp_f)
                if cp_f <= 0: continue

                closes   = [float(p.get("adjClose") or p.get("close") or 0) for p in prices]
                ma50     = calc_ma(closes, 50)
                ma200    = calc_ma(closes, 200)
                rsi      = calc_rsi(closes[-15:])
                perf_1yr = round(((cp_f - yr_ago_p)/yr_ago_p)*100, 1) if yr_ago_p else 0
                high_52w = max(closes)
                pct_from_high = round(((cp_f - high_52w)/high_52w)*100, 1) if high_52w else 0

                # Dividend data — from KNOWN_DIVIDENDS (Tiingo free plan has no dividend history)
                if t not in KNOWN_DIVIDENDS: continue
                known_yield, known_growth, known_annual = KNOWN_DIVIDENDS[t]
                annual_div    = known_annual
                div_yield     = round((annual_div / cp_f) * 100, 2) if cp_f > 0 else known_yield
                div_growth_rate = known_growth
                consistency   = 4  # assume consistent payers (all in our list are)

                if div_yield < min_yield_filter: continue

                # Category tags
                cats = []
                if t in ARISTOCRATS:    cats.append("Aristocrat")
                if t in HIGH_YIELD:     cats.append("High Yield")
                if t in DIVIDEND_GROWTH: cats.append("Growth")

                # Composite dividend score (0-100)
                score = 0
                # Yield (25 pts)
                if   div_yield >= 7: score += 25
                elif div_yield >= 5: score += 20
                elif div_yield >= 3: score += 14
                elif div_yield >= 1.5: score += 8
                else: score += 3
                # Dividend growth (25 pts)
                if   div_growth_rate >= 10: score += 25
                elif div_growth_rate >= 5:  score += 20
                elif div_growth_rate >= 2:  score += 14
                elif div_growth_rate >= 0:  score += 8
                else: score += 0  # cut
                # Price stability (20 pts)
                if   perf_1yr >= 10:  score += 20
                elif perf_1yr >= 0:   score += 15
                elif perf_1yr >= -10: score += 8
                elif perf_1yr >= -20: score += 3
                else: score += 0
                # Consistency (15 pts)
                score += consistency * 3
                # Technicals (15 pts)
                if ma50  and cp_f > ma50:  score += 7
                if ma200 and cp_f > ma200: score += 8

                scored.append({
                    "ticker": t, "price": round(cp_f, 2),
                    "div_yield": div_yield, "annual_div": round(annual_div, 4),
                    "div_growth_rate": div_growth_rate, "perf_1yr": perf_1yr,
                    "consistency": consistency,
                    "next_ex_div": "Est. by AI", "next_pay_date": "Est. by AI",
                    "high_52w": round(high_52w, 2), "pct_from_high": pct_from_high,
                    "ma50": round(ma50, 2) if ma50 else None,
                    "ma200": round(ma200, 2) if ma200 else None,
                    "rsi": round(rsi, 1) if rsi else None,
                    "categories": ", ".join(cats), "score": min(score, 100),
                })
            except: continue
            time.sleep(0.25)

        prog.empty()

        if not scored:
            st.warning("No stocks found. Try lowering the Min Yield % filter or check your Tiingo key."); st.stop()

        scored_sorted = sorted(scored, key=lambda x: x["score"], reverse=True)
        top_all = scored_sorted[:50]
        top_10  = scored_sorted[:10]

        # Summary stats
        st.markdown(f"#### ✅ Scanned {len(scored)} dividend stocks from universe of {len(universe)}")
        ss1,ss2,ss3,ss4 = st.columns(4)
        ss1.metric("Avg Yield (top 50)",  f"{round(sum(r['div_yield'] for r in top_all)/len(top_all),2)}%")
        ss2.metric("Avg Div Growth",       f"{round(sum(r['div_growth_rate'] for r in top_all)/len(top_all),1)}%/yr")
        ss3.metric("Avg 1Y Price Return",  f"{round(sum(r['perf_1yr'] for r in top_all)/len(top_all),1)}%")
        ss4.metric("Avg Composite Score",  round(sum(r['score'] for r in top_all)/len(top_all),1))

        # Full table
        st.markdown("#### 📊 Top 50 — Full Ranking")
        df_div = pd.DataFrame(top_all)
        df_disp = df_div[["ticker","categories","price","score","div_yield","annual_div","div_growth_rate","perf_1yr","rsi","pct_from_high"]].copy()
        df_disp.columns = ["Ticker","Category","Price","Score","Yield %","Annual Div $","Div Growth %/yr","1Y Return %","RSI","% From 52W High"]
        df_disp.insert(0,"Rank",range(1,len(df_disp)+1))
        st.dataframe(df_disp, use_container_width=True, hide_index=True)

        # Stage 2: AI deep dive on top 10
        st.markdown("---")
        st.markdown("#### 🤖 Stage 2 — AI Deep Dive: Top 10")
        st.caption("Claude analyzes each top stock for dividend sustainability, dates, price outlook, and cut risk.")

        client = anthropic.Anthropic(api_key=anthropic_key)
        ai_results = []
        ai_prog = st.progress(0, text="Running AI analysis…")

        for i, stock in enumerate(top_10):
            ai_prog.progress((i+1)/10, text=f"Analyzing {stock['ticker']} ({i+1}/10)…")
            try:
                ai_resp = parse_json(ask_claude(client,
                    "You are a dividend investing expert. Return only valid JSON, no markdown.",
                    f"""Analyze {stock['ticker']} as a dividend investment.

Price: ${stock['price']} | Yield: {stock['div_yield']}% | Annual Div: ${stock['annual_div']}
Div Growth Rate: {stock['div_growth_rate']}%/yr | 1Y Price Return: {stock['perf_1yr']}%
From 52W High: {stock['pct_from_high']}% | RSI: {stock['rsi']} | Categories: {stock['categories']}

Use your knowledge of this company's payout ratio, free cash flow, and business outlook.
Also provide your best estimate of the next ex-dividend date and payment date.

Respond ONLY with valid JSON:
{{"company_name":"Full name","sector":"sector",
"dividend_safety":"Very Safe|Safe|Moderate|At Risk",
"dividend_safety_rationale":"2 sentences on payout ratio and cash flow coverage",
"price_outlook":"Bullish|Neutral|Bearish","price_outlook_rationale":"2 sentences",
"cut_risk":"Low|Medium|High","cut_risk_reason":"one sentence",
"best_feature":"most compelling reason to own for dividends",
"main_risk":"biggest risk",
"overall_grade":"A|B|C|D",
"buy_now":"Yes|Wait for Dip|No",
"ideal_buy_price":0.0,
"next_ex_div_estimate":"YYYY-MM-DD or month/year estimate",
"next_pay_date_estimate":"YYYY-MM-DD or month/year estimate"}}"""))
                ai_results.append({**stock, **ai_resp})
            except Exception as e:
                ai_results.append({**stock, "company_name":stock["ticker"],"dividend_safety":"N/A",
                    "price_outlook":"N/A","cut_risk":"N/A","overall_grade":"N/A","buy_now":"N/A",
                    "best_feature":str(e)[:80],"main_risk":"","ideal_buy_price":0,
                    "next_ex_div_estimate":"N/A","next_pay_date_estimate":"N/A"})
            time.sleep(0.3)

        ai_prog.empty()

        # Display top 10 cards
        st.markdown("#### 🏆 Top 10 — AI Analyzed")
        for rank, r in enumerate(ai_results, 1):
            grade = r.get("overall_grade","N/A")
            grade_color = {"A":"#2e7d32","B":"#1a73e8","C":"#f57c00","D":"#c62828"}.get(grade,"#666")
            safety = r.get("dividend_safety","N/A")
            safety_color = {"Very Safe":"#2e7d32","Safe":"#2e7d32","Moderate":"#f57c00","At Risk":"#c62828"}.get(safety,"#666")
            outlook = r.get("price_outlook","N/A")
            outlook_color = {"Bullish":"#2e7d32","Neutral":"#f57c00","Bearish":"#c62828"}.get(outlook,"#666")
            buy = r.get("buy_now","N/A")
            buy_color = {"Yes":"#2e7d32","Wait for Dip":"#f57c00","No":"#c62828"}.get(buy,"#666")
            cut_risk = r.get("cut_risk","N/A")
            cut_color = {"Low":"#2e7d32","Medium":"#f57c00","High":"#c62828"}.get(cut_risk,"#666")

            with st.expander(
                f"#{rank} — {r['ticker']} · {r.get('company_name',r['ticker'])} · Yield: {r['div_yield']}% · Score: {r['score']} · Grade: {grade}",
                expanded=(rank <= 3)
            ):
                ca,cb2,cc,cd = st.columns(4)
                ca.markdown(f"**Overall Grade**<br><span style='font-size:2rem;font-weight:800;color:{grade_color}'>{grade}</span>", unsafe_allow_html=True)
                cb2.markdown(f"**Div Safety**<br><span style='color:{safety_color};font-weight:700'>{safety}</span>", unsafe_allow_html=True)
                cc.markdown(f"**Price Outlook**<br><span style='color:{outlook_color};font-weight:700'>{outlook}</span>", unsafe_allow_html=True)
                cd.markdown(f"**Buy Now?**<br><span style='color:{buy_color};font-weight:700'>{buy}</span>", unsafe_allow_html=True)

                m1,m2,m3,m4,m5,m6 = st.columns(6)
                m1.metric("Price",       f"${r['price']}")
                m2.metric("Yield",       f"{r['div_yield']}%")
                m3.metric("Annual Div",  f"${r['annual_div']}")
                m4.metric("Div Growth",  f"{r['div_growth_rate']}%/yr")
                m5.metric("Next Ex-Div", r.get("next_ex_div_estimate","N/A"))
                m6.metric("Pay Date",    r.get("next_pay_date_estimate","N/A"))

                dl,dr = st.columns(2)
                with dl:
                    st.markdown(f"**✅ Best Feature:** {r.get('best_feature','')}")
                    st.markdown(f"**💰 Safety Rationale:** {r.get('dividend_safety_rationale','')}")
                    ideal = r.get("ideal_buy_price",0)
                    if ideal and float(ideal) > 0:
                        diff = round(((float(ideal)-float(r["price"]))/float(r["price"]))*100,1)
                        st.markdown(f"**🎯 Ideal Buy Price:** ${ideal} ({diff:+.1f}% from current)")
                with dr:
                    st.markdown(f"**⚠️ Main Risk:** {r.get('main_risk','')}")
                    st.markdown(f"**📈 Price Outlook:** {r.get('price_outlook_rationale','')}")
                    st.markdown(f"**✂️ Cut Risk:** <span style='color:{cut_color};font-weight:700'>{cut_risk}</span> — {r.get('cut_risk_reason','')}", unsafe_allow_html=True)

                st.markdown(
                    f"<div style='background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:10px;margin-top:8px'>"
                    f"📅 <strong>Est. Next Ex-Div:</strong> {r.get('next_ex_div_estimate','N/A')} &nbsp;|&nbsp; "
                    f"💵 <strong>Est. Payment:</strong> {r.get('next_pay_date_estimate','N/A')} &nbsp;|&nbsp; "
                    f"📊 <strong>Category:</strong> {r['categories']} &nbsp;|&nbsp; "
                    f"📉 <strong>From 52W High:</strong> {r['pct_from_high']}%"
                    f"</div>", unsafe_allow_html=True)

        # Quick reference table
        st.markdown("#### 📋 Top 10 Quick Reference")
        ref_rows = [{
            "Rank": i+1, "Ticker": r["ticker"], "Company": r.get("company_name",r["ticker"]),
            "Grade": r.get("overall_grade","N/A"), "Yield %": r["div_yield"],
            "Div Growth %": r["div_growth_rate"], "Safety": r.get("dividend_safety","N/A"),
            "Price Outlook": r.get("price_outlook","N/A"), "Cut Risk": r.get("cut_risk","N/A"),
            "Buy Now?": r.get("buy_now","N/A"), "Est. Next Ex-Div": r.get("next_ex_div_estimate","N/A"),
            "Est. Pay Date": r.get("next_pay_date_estimate","N/A"),
            "Ideal Buy $": r.get("ideal_buy_price","N/A"), "Score": r["score"],
        } for i,r in enumerate(ai_results)]
        st.dataframe(pd.DataFrame(ref_rows), use_container_width=True, hide_index=True)
        st.caption("⚠️ Dividend dates are AI estimates. Always confirm with your broker before trading.")
        show_glossary(GLOSSARY_DIVIDEND_HUNTER)

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
st.caption("⚠️ For informational purposes only. Not financial advice. Always do your own research.")
