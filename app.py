# stock_news_sentiment_dashboard.py
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st
import pandas as pd
import plotly.express as px

# GNews: depending on your package name it may be `gnews` or `gnewsclient` or `gnews_client`
# The class used below is GNews from the package `gnews` (pip: gnews-client or gnews)
from gnews import GNews

# NLTK VADER
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# -----------------------------
# INITIAL SETUP
# -----------------------------
nltk.download("vader_lexicon", quiet=True)
analyzer = SentimentIntensityAnalyzer()

st.set_page_config(page_title="Stock News & Sentiment Dashboard", layout="wide")

# -----------------------------
# SIDEBAR — THEME SWITCH (reliable)
# -----------------------------
st.sidebar.header("⚙️ Settings")
dark_mode = st.sidebar.checkbox("🌗 Dark Mode", value=True, help="Switch between Dark & Light Mode")

# -----------------------------
# APPLY DYNAMIC THEMES (simple)
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
      body {{ background: {bg_gradient}; color: {text_color}; transition: all 0.3s ease-in-out; }}
      .stApp {{ background: {bg_gradient} !important; color: {text_color} !important; }}
      h1, h2, h3, h4, h5 {{ color: {accent_color} !important; transition: color 0.3s ease-in-out; }}
      .stButton button {{ background-color: {accent_color} !important; color: black !important; border-radius: 6px; }}
      .stDataFrame {{ border-radius: 10px; background-color: rgba(255,255,255,0.02); }}
      .block-container {{ padding-top: 2rem; padding-bottom: 2rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# APP TITLE
# -----------------------------
st.title("💹 Stock Market News & Sentiment Dashboard")

# -----------------------------
# AUTO REFRESH EVERY 10 MIN (safe)
# -----------------------------
refresh_interval = 600  # seconds
if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = time.time()
else:
    # Only trigger a rerun when the interval has passed, and set the timestamp first
    if time.time() - st.session_state["last_refresh"] > refresh_interval:
        st.session_state["last_refresh"] = time.time()
        # NOTE: experimental_rerun / rerun can cause loops if used incorrectly.
        # We call it once to refresh caches and UI.
        st.experimental_rerun()

# -----------------------------
# SIDEBAR FILTERS
# -----------------------------
st.sidebar.header("📅 Filter Options")
time_period = st.sidebar.selectbox(
    "Select Time Period",
    ["Last Week", "Last Month", "Last 3 Months", "Last 6 Months"],
)

search_input = st.sidebar.text_input("🔍 Compare Stocks (comma separated)", "").strip()

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
# F&O STOCK LIST + custom
# -----------------------------
fo_stocks = [
    "Reliance Industries",
    "TCS",
    "Infosys",
    "HDFC Bank",
    "ICICI Bank",
    "State Bank of India",
    "HCL Technologies",
    "Wipro",
    "Larsen & Toubro",
    "Tata Motors",
    "Bajaj Finance",
    "Axis Bank",
    "NTPC",
    "ITC",
    "Adani Enterprises",
    "Coal India",
    "Power Grid",
    "Maruti Suzuki",
    "Tech Mahindra",
    "Sun Pharma",
]

custom_stocks = [s.strip() for s in search_input.split(",") if s.strip()]
# Put custom stocks at front if provided
for stock in reversed(custom_stocks):
    if stock not in fo_stocks:
        fo_stocks.insert(0, stock)

# -----------------------------
# PERFORMANCE BOOSTERS - NEWS FETCH & SENTIMENT
# -----------------------------
@st.cache_data(ttl=600, show_spinner=False)
def fetch_news_for_query(query: str, max_results: int = 10):
    """
    Fetches news for a query using GNews. Returns list of article dicts.
    This function does not try to parse dates; caller may filter by start/end.
    """
    try:
        gnews = GNews(language="en", country="IN", max_results=max_results)
        # gnews.get_news returns a list of dicts (title, url, publisher, published date, description)
        articles = gnews.get_news(query) or []
        return articles
    except Exception as e:
        # Return empty list on error but log to Streamlit
        st.error(f"Error fetching news for {query}: {e}")
        return []


def article_within_date(art, start_dt: datetime, end_dt: datetime):
    """
    Attempts to determine if an article falls within start_dt..end_dt.
    Tries common keys like 'published date', 'publishedDate', 'published_date', 'published'.
    If parsing fails or key missing, defaults to True (include).
    """
    date_candidates = [
        art.get("published date"),
        art.get("publishedDate"),
        art.get("published_date"),
        art.get("published"),
        art.get("publishedAt"),
    ]
    for d in date_candidates:
        if not d:
            continue
        # Try several parse strategies
        try:
            # Common GNews format may be ISO-like; try fromisoformat
            parsed = None
            if isinstance(d, str):
                try:
                    parsed = datetime.fromisoformat(d)
                except Exception:
                    # Fallback: try parsing common formats
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
                        try:
                            parsed = datetime.strptime(d, fmt)
                            break
                        except Exception:
                            continue
            elif isinstance(d, (int, float)):
                # timestamp
                parsed = datetime.fromtimestamp(d)
            if parsed:
                # Compare
                return start_dt <= parsed <= end_dt
        except Exception:
            continue
    # If we cannot determine the published date, include by default
    return True


@st.cache_data(ttl=600, show_spinner=False)
def fetch_all_news(stocks: list, start: datetime, end: datetime, max_results_per_stock: int = 10, max_workers: int = 8):
    """
    Fetch news for a list of stock queries in parallel, filter by date range when possible,
    and return structured results that include News Count.
    """
    results = []
    # Limit workers to a sane number
    max_workers = min(max_workers, len(stocks) or 1)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_news_for_query, s, max_results_per_stock): s for s in stocks}
        for future in as_completed(futures):
            stock = futures[future]
            try:
                articles = future.result() or []
                # Filter by date if possible
                filtered = [a for a in articles if article_within_date(a, start, end)]
                results.append({"Stock": stock, "Articles": filtered, "News Count": len(filtered)})
            except Exception:
                results.append({"Stock": stock, "Articles": [], "News Count": 0})
    return results


def analyze_sentiment(text: str):
    """
    Returns (label, emoji, score)
    """
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
# MAIN TABS
# -----------------------------
news_tab, trending_tab, sentiment_tab, compare_tab = st.tabs(
    ["📰 News", "🔥 Trending Stocks", "💬 Sentiment", "📊 Compare Stocks"]
)

# -----------------------------
# TAB 1 — NEWS SECTION
# -----------------------------
with news_tab:
    st.header("🗞️ Latest Market News for F&O Stocks")

    # Fetch top 10 stocks for the news listing to keep UI snappy
    top_for_listing = fo_stocks[:10]
    with st.spinner("Fetching the latest financial news..."):
        news_results = fetch_all_news(top_for_listing, start_date, today, max_results_per_stock=12, max_workers=6)

    for result in news_results:
        stock = result.get("Stock", "Unknown")
        articles = result.get("Articles", []) or []
        with st.expander(f"🔹 {stock} ({len(articles)} Articles)", expanded=False):
            if articles:
                for art in articles[:8]:
                    # Extract fields robustly
                    title = art.get("title") or art.get("titleText") or "No title"
                    url = art.get("url") or art.get("link") or "#"
                    publisher = (art.get("publisher") or {}).get("title") if isinstance(art.get("publisher"), dict) else art.get("publisher") or "Unknown Source"
                    # Try multiple published-date keys
                    published_date = (
                        art.get("published date") or art.get("publishedDate") or art.get("published") or art.get("publishedAt") or "N/A"
                    )
                    description = art.get("description") or art.get("snippet") or ""
                    # Show headline, source, date, and small snippet
                    st.markdown(
                        f"""**[{title}]({url})**  \n*{publisher}* | 🗓️ *{published_date}*  \n{description}"""
                    )
                    st.markdown("---")
            else:
                st.info("No news found for this stock in the selected time period.")

# -----------------------------
# TAB 2 — TRENDING STOCKS
# -----------------------------
with trending_tab:
    st.header("🔥 Trending F&O Stocks by News Mentions")
    with st.spinner("Analyzing trends..."):
        all_results = fetch_all_news(fo_stocks, start_date, today, max_results_per_stock=8, max_workers=8)
        counts = [
            {"Stock": r.get("Stock", "Unknown"), "News Count": r.get("News Count", len(r.get("Articles", [])))}
            for r in all_results
        ]
        df_counts = pd.DataFrame(counts).sort_values("News Count", ascending=False)
        if df_counts.empty:
            st.info("No news counts available for the selected timeframe.")
        else:
            fig = px.bar(
                df_counts,
                x="Stock",
                y="News Count",
                color="News Count",
                color_continuous_scale="Turbo",
                title=f"Trending F&O Stocks ({time_period})",
                template=plot_theme,
            )
            st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# TAB 3 — SENTIMENT
# -----------------------------
with sentiment_tab:
    st.header("💬 Sentiment Analysis")
    with st.spinner("Analyzing sentiment..."):
        sentiment_data = []
        all_results = fetch_all_news(fo_stocks[:12], start_date, today, max_results_per_stock=8, max_workers=6)
        for res in all_results:
            stock = res.get("Stock", "Unknown")
            for art in res.get("Articles", [])[:5]:
                title = art.get("title") or ""
                description = art.get("description") or ""
                combined = f"{title}. {description}"
                sentiment, emoji, score = analyze_sentiment(combined)
                sentiment_data.append(
                    {"Stock": stock, "Headline": title, "Sentiment": sentiment, "Emoji": emoji, "Score": score}
                )
        if sentiment_data:
            sentiment_df = pd.DataFrame(sentiment_data).sort_values(by=["Stock", "Score"], ascending=[True, False])
            st.dataframe(sentiment_df, use_container_width=True)
            csv_bytes = sentiment_df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download Sentiment Data", csv_bytes, "sentiment_data.csv", "text/csv")
        else:
            st.warning("No sentiment data found for the selected timeframe.")

# -----------------------------
# TAB 4 — COMPARE STOCKS
# -----------------------------
with compare_tab:
    st.header("📊 Compare Stock Sentiment")
    if custom_stocks:
        with st.spinner("Comparing..."):
            compare_results = fetch_all_news(custom_stocks, start_date, today, max_results_per_stock=12, max_workers=4)
            compare_data = []
            for res in compare_results:
                stock = res.get("Stock", "Unknown")
                articles = res.get("Articles", []) or []
                total = len(articles)
                pos = neg = neu = 0
                for art in articles[:10]:
                    title = art.get("title", "")
                    description = art.get("description", "")
                    s_label, _, _ = analyze_sentiment(f"{title}. {description}")
                    if s_label == "Positive":
                        pos += 1
                    elif s_label == "Negative":
                        neg += 1
                    else:
                        neu += 1
                compare_data.append({"Stock": stock, "Positive": pos, "Negative": neg, "Neutral": neu, "Total News": total})
            compare_df = pd.DataFrame(compare_data).sort_values("Positive", ascending=False)
            if compare_df.empty:
                st.info("No comparison data available.")
            else:
                st.dataframe(compare_df, use_container_width=True)
                st.download_button(
                    "📥 Download Comparison Data", compare_df.to_csv(index=False).encode("utf-8"), "compare_stocks.csv", "text/csv"
                )
    else:
        st.info("💡 Enter 1–3 stock names in sidebar to compare sentiment (comma separated).")

# -----------------------------
# FOOTER
# -----------------------------
st.markdown("---")
st.caption(
    f"📊 Data Source: Google News | Mode: {'Dark' if dark_mode else 'Light'} | Auto-refresh every 10 min | Built with ❤️ using Streamlit & Plotly"
)
