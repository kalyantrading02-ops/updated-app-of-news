# app.py
import time
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st
import pandas as pd
import plotly.express as px
from gnews import GNews
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# -----------------------------
# INITIAL SETUP
# -----------------------------
nltk.download("vader_lexicon", quiet=True)
st.set_page_config(page_title="Stock News & Sentiment Dashboard", layout="wide")
analyzer = SentimentIntensityAnalyzer()

# -----------------------------
# SIDEBAR — THEME SWITCH
# -----------------------------
st.sidebar.header("⚙️ Settings")
# Use checkbox for maximum compatibility
dark_mode = st.sidebar.checkbox("🌗 Dark Mode", value=True, help="Switch instantly between Dark & Light Mode")

# -----------------------------
# APPLY THEMES (CSS)
# -----------------------------
if dark_mode:
    bg_gradient = "linear-gradient(135deg, #0f2027, #203a43, #2c5364)"
    text_color = "#EAEAEA"
    accent_color = "#00E676"
    plot_theme = "plotly_dark"
else:
    bg_gradient = "linear-gradient(135deg, #FFFFFF, #E0E0E0, #F5F5F5)"
    text_color = "#111111"
    accent_color = "#0078FF"
    plot_theme = "plotly_white"

st.markdown(
    f"""
    <style>
    body {{ background: {bg_gradient}; color: {text_color}; }}
    .stApp {{ background: {bg_gradient} !important; color: {text_color} !important; }}
    h1, h2, h3, h4, h5 {{ color: {accent_color} !important; }}
    .stButton button {{ background-color: {accent_color} !important; color: black !important; border-radius: 6px; }}
    .stDataFrame {{ border-radius: 10px; background-color: rgba(255,255,255,0.02); }}
    .news-card {{ border-radius: 10px; padding: 12px; box-shadow: 0 6px 18px rgba(0,0,0,0.12); transition: transform .12s ease, box-shadow .12s ease; background: rgba(255,255,255,0.02); margin-bottom: 12px; }}
    .news-card:hover {{ transform: translateY(-4px); box-shadow: 0 10px 30px rgba(0,0,0,0.16); }}
    .headline {{ font-weight:600; font-size:16px; margin-bottom:6px; }}
    .meta {{ font-size:12px; color: #9aa0a6; margin-bottom:8px; }}
    .snip {{ font-size:13px; color: #dfe6ea; }}
    .badge {{ display:inline-block; padding:4px 8px; border-radius:999px; font-size:12px; margin-right:6px; }}
    .badge-source {{ background: rgba(255,255,255,0.04); color:inherit; }}
    .badge-pos {{ background: rgba(0,200,83,0.12); color:#00C853; }}
    .badge-neu {{ background: rgba(255,193,7,0.08); color:#FFC107; }}
    .badge-neg {{ background: rgba(239,83,80,0.08); color:#EF5350; }}
    .priority-high {{ background: rgba(239,83,80,0.12); color:#EF5350; padding:6px 10px; border-radius:8px; font-weight:600; }}
    .priority-med {{ background: rgba(255,193,7,0.08); color:#FFC107; padding:6px 10px; border-radius:8px; font-weight:600; }}
    .priority-low {{ background: rgba(128,128,128,0.06); color:#9aa0a6; padding:6px 10px; border-radius:8px; font-weight:600; }}
    .reason-chip {{ display:inline-block; margin:3px 4px; padding:4px 8px; border-radius:999px; font-size:12px; background: rgba(255,255,255,0.03); }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# TITLE
# -----------------------------
st.title("💹 Stock Market News & Sentiment Dashboard")

# -----------------------------
# AUTO REFRESH EVERY 10 MIN (robust)
# -----------------------------
refresh_interval = 600  # seconds
if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = time.time()
else:
    if time.time() - st.session_state["last_refresh"] > refresh_interval:
        st.session_state["last_refresh"] = time.time()
        # Try rerun in a version-robust way
        try:
            st.experimental_rerun()
        except Exception:
            try:
                st.rerun()
            except Exception:
                st.warning(
                    "Auto-refresh is unavailable in this Streamlit version. "
                    "Please manually refresh the page to get updated data."
                )
                st.stop()

# -----------------------------
# SIDEBAR FILTERS
# -----------------------------
st.sidebar.header("📅 Filter Options")
time_period = st.sidebar.selectbox("Select Time Period", ["Last Week", "Last Month", "Last 3 Months", "Last 6 Months"])

today = datetime.today()
if time_period == "Last Week":
    start_date = today - timedelta(days=7)
elif time_period == "Last Month":
    start_date = today - timedelta(days=30)
elif time_period == "Last 3 Months":
    start_date = today - timedelta(days=90)
else:
    start_date = today - timedelta(days=180)

# -----------------------------
# F&O STOCK LIST
# -----------------------------
fo_stocks = [
    "Reliance Industries", "TCS", "Infosys", "HDFC Bank", "ICICI Bank", "State Bank of India",
    "HCL Technologies", "Wipro", "Larsen & Toubro", "Tata Motors", "Bajaj Finance", "Axis Bank",
    "NTPC", "ITC", "Adani Enterprises", "Coal India", "Power Grid", "Maruti Suzuki",
    "Tech Mahindra", "Sun Pharma"
]

# -----------------------------
# CACHEABLE NEWS FETCHERS
# -----------------------------
@st.cache_data(ttl=600, show_spinner=False)
def fetch_news(stock, start, end, max_results=12):
    try:
        gnews = GNews(language="en", country="IN", max_results=max_results)
        try:
            gnews.start_date, gnews.end_date = start, end
        except Exception:
            # some versions of GNews client may not accept start/end assignment
            pass
        articles = gnews.get_news(stock) or []
        return articles
    except Exception:
        return []

@st.cache_data(ttl=600, show_spinner=False)
def fetch_all_news(stocks, start, end):
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_news, s, start, end): s for s in stocks}
        for future in as_completed(futures):
            stock = futures[future]
            try:
                articles = future.result() or []
                results.append({"Stock": stock, "Articles": articles, "News Count": len(articles)})
            except Exception:
                results.append({"Stock": stock, "Articles": [], "News Count": 0})
    return results

# -----------------------------
# SENTIMENT HELPER
# -----------------------------
def analyze_sentiment(text):
    if not text:
        text = ""
    score = analyzer.polarity_scores(text)["compound"]
    if score > 0.2:
        return "Positive", "🟢", score
    elif score < -0.2:
        return "Negative", "🔴", score
    else:
        return "Neutral", "🟡", score

# -----------------------------
# SCORING ENGINE (weights & keywords)
# -----------------------------
WEIGHTS = {
    "earnings_guidance": 30,
    "M&A_JV": 25,
    "management_change": 20,
    "buyback_dividend": 20,
    "contract_deal": 25,
    "block_insider": 25,
    "policy_regulation": 20,
    "analyst_move": 15,
    "numeric_mentioned": 10,
    "trusted_source": 15,
    "speculative_penalty": -15,
    "low_quality_penalty": -10,
    "max_corroboration_bonus": 20,
}

TRUSTED_SOURCES = {
    "reuters", "bloomberg", "times of india", "economictimes", "economic times", "livemint", "mint",
    "business standard", "business-standard", "cnbc", "ft", "financial times", "press release", "nse", "bse"
}
LOW_QUALITY_SOURCES = {"blog", "medium", "wordpress", "forum", "reddit", "quora"}

HIGH_PRIORITY_KEYWORDS = {
    "earnings": ["earnings", "quarter", "q1", "q2", "q3", "q4", "revenue", "profit", "loss", "guidance", "outlook", "beat", "miss", "results"],
    "MA": ["acquires", "acquisition", "merger", "demerger", "spin-off", "spin off", "joint venture", "jv"],
    "management": ["appoint", "resign", "ceo", "cfo", "chairman", "board", "director", "promoter", "coo", "md"],
    "corp_action": ["buyback", "dividend", "split", "bonus issue", "bonus", "rights issue", "rights", "share pledge", "pledge"],
    "contract": ["contract", "order", "tender", "deal", "agreement", "licence", "license", "wins order"],
    "regulatory": ["sebi", "investigation", "fraud", "lawsuit", "penalty", "fine", "regulation", "ban", "policy", "pli", "subsidy", "tariff"],
    "analyst": ["upgrade", "downgrade", "target", "recommendation", "brokerage", "analyst"],
    "block": ["block deal", "bulk deal", "blocktrade", "block-trade", "insider", "promoter buy", "promoter selling", "promoter sell"],
}

SPECULATIVE_WORDS = ["may", "might", "could", "rumour", "rumor", "reportedly", "alleged", "possible", "speculat"]

NUMERIC_PATTERNS = re.compile(
    r'[%₹$£€]|(?:\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b\s*(?:crore|lakh|billion|bn|mn|m|₹|rs\.|rs|rupee|ton|tons|mw|MW|GW))',
    re.IGNORECASE,
)

def norm(s):
    return (s or "").strip().lower()

def contains_any(text, keywords):
    t = norm(text)
    return any(k.lower() in t for k in keywords)

def is_trusted_source(pub):
    if not pub:
        return False
    p = norm(pub)
    for t in TRUSTED_SOURCES:
        if t in p:
            return True
    return False

def is_low_quality_source(pub):
    if not pub:
        return False
    p = norm(pub)
    return any(k in p for k in LOW_QUALITY_SOURCES)

def contains_numeric(text):
    if not text:
        return False
    return bool(NUMERIC_PATTERNS.search(text))

def parse_published_date(art):
    # try several common fields/formats; return datetime or None
    candidates = [art.get("published date"), art.get("publishedDate"), art.get("published_date"), art.get("published"), art.get("publishedAt"), art.get("timestamp"), art.get("time")]
    for c in candidates:
        if not c:
            continue
        if isinstance(c, datetime):
            return c
        try:
            return datetime.fromisoformat(c)
        except Exception:
            # try common formats
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(c, fmt)
                except Exception:
                    continue
    return None

def score_article(title, desc, publisher, matched_sources_with_times=None):
    raw = 0
    reasons = []
    text = f"{title} {desc}".lower()
