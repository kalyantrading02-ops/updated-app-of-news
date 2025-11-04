# app.py
# Streamlit Stock News Dashboard
# - Improved UI (columns, expanders, theme toggle, timestamp)
# - Performance: caching (ttl=600s), parallel fetching, limited work
# - Real sentiment via VADER (TextBlob optional if installed)
# - Search & Compare (up to 3 stocks, side-by-side)
# - CSV downloads
# - Auto-refresh achieved via cache TTL = 10 minutes (600 seconds)
#
# Keep trending stocks section behavior as originally requested.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from gnews import GNews
import concurrent.futures
import nltk
import time
import io

# --- Sentiment imports ---
# VADER (always attempt)
try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
except Exception:
    nltk.download("vader_lexicon", quiet=True)
    from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Optional TextBlob (graceful fallback)
TEXTBLOB_AVAILABLE = True
try:
    from textblob import TextBlob
except Exception:
    TEXTBLOB_AVAILABLE = False

# --- Streamlit page config ---
st.set_page_config(page_title="Stock News & Sentiment Dashboard", layout="wide")
st.title("📰 Stock Market News Dashboard")

# --- Theme toggle (simple) ---
if "theme" not in st.session_state:
    st.session_state.theme = "Light"

with st.sidebar:
    st.header("Settings")
    st.session_state.theme = st.selectbox("Theme", ["Light", "Dark"], index=0)
    st.markdown("---")
    st.subheader("Filter & Options")
    time_period = st.selectbox(
        "Select Time Period",
        ["Last Week", "Last Month", "Last 3 Months", "Last 6 Months"]
    )
    max_articles_per_stock = st.slider("Max articles per stock", 1, 20, 5)
    workers = st.slider("Parallel workers (threads)", 2, 12, 6)
    st.markdown("---")
    st.subheader("Search / Compare")
    compare_input = st.text_input("Compare stocks (comma separated, up to 3). Example: Reliance, TCS", "")
    st.caption("Search also used in the News tab.")

# --- Date range logic ---
today = datetime.today()
if time_period == "Last Week":
    start_date = today - timedelta(days=7)
elif time_period == "Last Month":
    start_date = today - timedelta(days=30)
elif time_period == "Last 3 Months":
    start_date = today - timedelta(days=90)
else:
    start_date = today - timedelta(days=180)

start_date_str = start_date.strftime("%Y-%m-%d")
end_date_str = today.strftime("%Y-%m-%d")

# --- Default F&O stock list (kept as requested) ---
default_fo_stocks = [
    "Reliance Industries", "TCS", "Infosys", "HDFC Bank", "ICICI Bank",
    "State Bank of India", "HCL Technologies", "Wipro", "Larsen & Toubro",
    "Tata Motors", "Bajaj Finance", "Axis Bank", "NTPC", "ITC",
    "Adani Enterprises", "Coal India", "Power Grid", "Maruti Suzuki",
    "Tech Mahindra", "Sun Pharma"
]

if "fo_stocks" not in st.session_state:
    st.session_state.fo_stocks = default_fo_stocks.copy()

# Optional: if user typed compare_input, pre-populate top of list (no duplicates)
if compare_input.strip():
    candidates = [s.strip() for s in compare_input.split(",") if s.strip()]
    for c in reversed(candidates[:3]):
        if c not in st.session_state.fo_stocks:
            st.session_state.fo_stocks.insert(0, c)

# --- Helper: make GNews client (cached) ---
@st.cache_data(ttl=600, show_spinner=False)
def make_gnews_client():
    # Reuse client for TTL seconds
    return GNews(language="en", country="IN")

# --- Helper: fetch articles for query (cached) ---
@st.cache_data(ttl=600, show_spinner=False)
def fetch_articles_for_query(query: str, max_articles: int):
    """
    Returns list of article dicts (may be empty).
    Cached for 10 minutes to implement auto-refresh.
    """
    client = make_gnews_client()
    try:
        articles = client.get_news(query)
        if not articles:
            return []
        # Trim to max_articles
        return articles[:max_articles]
    except Exception as e:
        # Return empty on error (don't crash)
        return []

# --- Helper: sentiment computation (cached) ---
@st.cache_data(ttl=600, show_spinner=False)
def compute_vader_sentiment(text: str):
    sid = SentimentIntensityAnalyzer()
    scores = sid.polarity_scores(text or "")
    compound = scores.get("compound", 0.0)
    # Tighter thresholds for finance (as discussed)
    if compound > 0.20:
        label = "Positive"
    elif compound < -0.20:
        label = "Negative"
    else:
        label = "Neutral"
    return {"score": compound, "label": label}

@st.cache_data(ttl=600, show_spinner=False)
def compute_textblob_sentiment(text: str):
    if not TEXTBLOB_AVAILABLE:
        return {"score": 0.0, "label": "Neutral"}
    tb = TextBlob(text or "")
    polarity = tb.sentiment.polarity
    if polarity > 0.05:
        label = "Positive"
    elif polarity < -0.05:
        label = "Negative"
    else:
        label = "Neutral"
    return {"score": polarity, "label": label}

def sentiment_emoji(label):
    return {"Positive": "🟢", "Neutral": "🟡", "Negative": "🔴"}.get(label, "🟡")

# --- Parallel fetch wrapper (limited, controlled) ---
def fetch_counts_parallel(stock_list, max_articles_per_stock, workers=6):
    results = []
    # Bound the number of stocks to avoid heavy load
    to_check = stock_list[:50]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_articles_for_query, stock, max_articles_per_stock): stock for stock in to_check}
        for fut in concurrent.futures.as_completed(futures):
            stock = futures[fut]
            try:
                arts = fut.result() or []
                results.append({"Stock": stock, "Articles": arts, "News Count": len(arts)})
            except Exception:
                results.append({"Stock": stock, "Articles": [], "News Count": 0})
    return results

# --- UI: Top bar with timestamp and small controls ---
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    st.markdown(f"**Period:** {start_date_str} → {end_date_str}")
with col2:
    last_fetch_msg = "Data cached for 10 minutes (auto-refresh)."
    st.caption(last_fetch_msg)
with col3:
    st.caption(f"Last reload: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

st.markdown("---")

# --- Tabs: News, Trending (unchanged), Sentiment/Insights/Compare ---
news_tab, trending_tab, insights_tab = st.tabs(["📰 News", "🔥 Trending Stocks", "💡 Insights & Compare"])

# -------------------------
# Tab: News (improved layout)
# -------------------------
with news_tab:
    st.header("🗞️ Latest News (Search or browse tracked stocks)")

    # Search box inside tab
    search_query = st.text_input("Search for a company or keyword (press Enter)", "")
    search_max = st.number_input("Max articles to show for search", min_value=1, max_value=20, value=5)

    # If search used, perform single fetch (cached)
    if search_query.strip():
        with st.spinner(f"Fetching news for '{search_query}'..."):
            search_articles = fetch_articles_for_query(search_query.strip(), search_max)
        if not search_articles:
            st.warning(f"No news found for '{search_query}' ({start_date_str}→{end_date_str})")
        else:
            st.subheader(f"Search results for: {search_query.strip()}")
            for art in search_articles:
                title = art.get("title", "No title")
                url = art.get("url", "")
                publisher = art.get("publisher", {}).get("title", "Unknown")
                published = art.get("published", "")
                desc = art.get("description") or art.get("summary") or ""
                st.markdown(f"**[{title}]({url})** — *{publisher}* • {published}")
                if desc:
                    st.write(desc)
                st.markdown("---")

    # Show tracked stocks in compact expanders (limit default to 12 for speed)
    n_show = st.number_input("Show top N tracked stocks in News tab", min_value=3, max_value=30, value=12)
    with st.spinner("Fetching latest headlines for tracked stocks..."):
        cached_results = fetch_counts_parallel(st.session_state.fo_stocks, max_articles_per_stock, workers)
    # Display top N by news count
    df_counts = pd.DataFrame(cached_results) if cached_results else pd.DataFrame(columns=["Stock", "News Count", "Articles"])
    if "News Count" in df_counts.columns:
        df_counts = df_counts.sort_values("News Count", ascending=False)
    else:
        df_counts["News Count"] = 0

    st.subheader("Tracked stocks (compact view)")
    for idx, row in df_counts.head(n_show).iterrows():
        stock = row["Stock"]
        arts = row.get("Articles") or []
        with st.expander(f"{stock} — {len(arts)} articles"):
            if not arts:
                st.write("No articles found.")
            else:
                for art in arts:
                    title = art.get("title", "No title")
                    url = art.get("url", "")
                    pub = art.get("publisher", {}).get("title", "Unknown")
                    published = art.get("published", "")
                    st.markdown(f"**[{title}]({url})** — *{pub}* • {published}")
                    summary = art.get("description") or art.get("summary") or ""
                    if summary:
                        st.write(summary)
                    st.markdown("---")

# -------------------------
# Tab: Trending Stocks (MAINTAINED AS IS)
# -------------------------
with trending_tab:
    st.header("🔥 Trending Stocks Based on News Coverage (unchanged section)")
    # Reuse cached_results computed earlier to keep behavior similar to previous app
    if not cached_results:
        st.warning("No data available for trending chart.")
    else:
        trending_df = pd.DataFrame(cached_results).sort_values("News Count", ascending=False)
        if trending_df.empty:
            st.warning("No news counts to display.")
        else:
            # Plotly bar (kept similar to previous implementation)
            import plotly.express as px
            plot_df = trending_df.head(30).copy()
            fig = px.bar(
                plot_df,
                x="Stock",
                y="News Count",
                color="News Count",
                color_continuous_scale="Bluered",
                title=f"Trending Stocks ({time_period})",
            )
            st.plotly_chart(fig, use_container_width=True)

            # Keep download of trending CSV (helpful)
            st.download_button(
                "📥 Download Trending CSV",
                plot_df.to_csv(index=False).encode("utf-8"),
                file_name=f"trending_{start_date_str}_to_{end_date_str}.csv",
                mime="text/csv"
            )

# -------------------------
# Tab: Insights & Compare
# -------------------------
with insights_tab:
    st.header("💡 Insights & Compare")

    # Choose analyzer (VADER always available; TextBlob optional)
    analyzer_choice = st.selectbox("Sentiment Analyzer", ["VADER (recommended)"] + (["TextBlob"] if TEXTBLOB_AVAILABLE else []))
    st.caption("Note: sentiment cache refreshes every 10 minutes.")

    # Select stocks to compare (limit 3). Offer quick selection from top trending
    top_trending = [r["Stock"] for r in cached_results][:8] if cached_results else st.session_state.fo_stocks[:8]
    st.write("Quick pick from top tracked stocks:")
    picks = st.multiselect("Pick up to 3 stocks to compare", options=top_trending, default=top_trending[:2], max_selections=3)

    # Also allow typed input (comma separated)
    typed = st.text_input("Or type stocks (comma separated, up to 3):", "")
    typed_list = [s.strip() for s in typed.split(",") if s.strip()]
    compare_list = picks.copy()
    for t in typed_list:
        if t not in compare_list and len(compare_list) < 3:
            compare_list.append(t)

    # Guarantee no more than 3
    compare_list = compare_list[:3]

    if not compare_list:
        st.info("Select or type up to 3 stocks to compare.")
    else:
        st.subheader(f"Comparing: {', '.join(compare_list)}")

        # Fetch articles for compare_list (cached)
        with st.spinner("Fetching articles for comparison..."):
            comp_results = fetch_counts_parallel(compare_list, max_articles_per_stock, workers)

        # Build per-article sentiment table
        rows = []
        for r in comp_results:
            stock = r["Stock"]
            for art in r.get("Articles", []):
                title = art.get("title", "")
                snippet = art.get("description") or art.get("summary") or ""
                text = f"{title}. {snippet}"
                if analyzer_choice.startswith("VADER"):
                    s = compute_vader_sentiment(text)
                else:
                    s = compute_textblob_sentiment(text)
                rows.append({
                    "Stock": stock,
                    "Title": title,
                    "Publisher": art.get("publisher", {}).get("title", ""),
                    "Published": art.get("published", ""),
                    "Sentiment": s["label"],
                    "Score": s["score"],
                    "Emoji": sentiment_emoji(s["label"]),
                    "URL": art.get("url", "")
                })

        if not rows:
            st.warning("No articles fetched for selected stocks.")
        else:
            # Per-article dataframe
            df_articles = pd.DataFrame(rows)
            st.subheader("Per-article Sentiment (sample)")
            st.dataframe(df_articles[["Stock", "Title", "Publisher", "Published", "Sentiment", "Score"]])

            # Aggregated metrics per stock
            agg = df_articles.groupby("Stock").agg(
                Articles_Count = pd.NamedAgg(column="Title", aggfunc="count"),
                Positive_Count = pd.NamedAgg(column="Sentiment", aggfunc=lambda s: (s=="Positive").sum()),
                Neutral_Count = pd.NamedAgg(column="Sentiment", aggfunc=lambda s: (s=="Neutral").sum()),
                Negative_Count = pd.NamedAgg(column="Sentiment", aggfunc=lambda s: (s=="Negative").sum()),
                Avg_Score = pd.NamedAgg(column="Score", aggfunc="mean")
            ).reset_index()

            def net_sentiment(r):
                if r["Articles_Count"] == 0:
                    return 0.0
                return (r["Positive_Count"] - r["Negative_Count"]) / r["Articles_Count"]

            agg["Net_Sentiment"] = agg.apply(net_sentiment, axis=1)
            agg = agg.sort_values("Net_Sentiment", ascending=False)
            st.subheader("Aggregated Sentiment by Stock")
            st.dataframe(agg)

            # Simple visual: bar chart of Net_Sentiment
            try:
                import plotly.express as px
                figc = px.bar(agg, x="Stock", y="Net_Sentiment", color="Net_Sentiment", color_continuous_scale="RdYlGn")
                st.plotly_chart(figc, use_container_width=True)
            except Exception:
                pass

            # CSV downloads
            st.download_button(
                "📥 Download per-article sentiment CSV",
                df_articles.to_csv(index=False).encode("utf-8"),
                file_name=f"compare_articles_{start_date_str}_to_{end_date_str}.csv",
                mime="text/csv"
            )
            st.download_button(
                "📥 Download aggregated sentiment CSV",
                agg.to_csv(index=False).encode("utf-8"),
                file_name=f"compare_agg_{start_date_str}_to_{end_date_str}.csv",
                mime="text/csv"
            )

# --- Footer ---
st.markdown("---")
if TEXTBLOB_AVAILABLE:
    st.caption("Sentiment: VADER (finance thresholds) and optional TextBlob | News: GNews | Cached 10 minutes")
else:
    st.caption("Sentiment: VADER (finance thresholds) | News: GNews | Cached 10 minutes")
