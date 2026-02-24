# 📈 Stock Evaluator AI

An AI-powered stock analysis tool built with Streamlit and Claude AI. Enter any stock ticker and get:

- **📊 Earnings Scorecard** — Rated across 10 categories (Revenue, EPS, Cash Flow, etc.)
- **💡 Insights & Price Targets** — AI outlook with price targets for next day → next year
- **📰 Stock in the News** — News sentiment, upcoming earnings estimates, excitement/caution flags
- **💰 Dividend Analysis** — Ex-div dates, yield analysis, capture recommendations

---

## 🚀 Quick Start (Local)

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/stock-evaluator.git
cd stock-evaluator
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up API keys
```bash
cp .env.example .env
```
Edit `.env` and add your keys:
```
ANTHROPIC_API_KEY=your_key_here
NEWS_API_KEY=your_key_here
```

### 4. Run the app
```bash
streamlit run app.py
```

Open your browser to `http://localhost:8501`

---

## 🔑 Getting API Keys

### Anthropic API Key (required)
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up / log in
3. Go to **API Keys** → **Create Key**
4. Copy and paste into the app or your `.env` file
5. New accounts receive free credits to get started

### News API Key (optional but recommended)
1. Go to [newsapi.org](https://newsapi.org)
2. Click **Get API Key** — free account gives 100 requests/day
3. Copy and paste into the app or your `.env` file

### Stock Data
All stock, earnings, and dividend data comes from **Yahoo Finance via yfinance** — completely free, no API key needed.

---

## ☁️ Deploy to Streamlit Cloud (free)

1. **Push to GitHub**: Upload all files in this folder to a new GitHub repository.

2. **Go to [share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub.

3. **Click "New app"**, select your repo, set the main file to `app.py`.

4. **Add secrets**: In the Streamlit Cloud dashboard, go to your app's settings → **Secrets**, and add:
   ```toml
   ANTHROPIC_API_KEY = "your_anthropic_api_key_here"
   NEWS_API_KEY = "your_newsapi_key_here"
   ```

5. **Deploy!** Your app will be live at a public URL you can share.

> Note: Even without secrets set in Streamlit Cloud, users can enter their own API keys directly in the app interface.

---

## 📁 File Structure

```
stock-evaluator/
├── app.py                          # Main Streamlit application
├── requirements.txt                # Python dependencies
├── .env.example                    # API key template (copy to .env)
├── .gitignore                      # Prevents secrets from being committed
├── .streamlit/
│   └── secrets.toml.example        # Streamlit Cloud secrets template
└── README.md                       # This file
```

---

## ⚠️ Disclaimer

This tool is for **informational and educational purposes only**. Nothing in this app constitutes financial advice. Always do your own research and consult a qualified financial advisor before making investment decisions.

---

## 🛠️ Built With

- [Streamlit](https://streamlit.io) — UI framework
- [Anthropic Claude](https://anthropic.com) — AI analysis engine
- [yfinance](https://github.com/ranaroussi/yfinance) — Stock data
- [NewsAPI](https://newsapi.org) — News articles
