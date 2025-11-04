# app.py
# Streamlit Stock News Dashboard with robust handling when TextBlob is missing.
# Features: VADER sentiment (always), optional TextBlob sentiment (if installed),
# cached API calls, search box for custom stocks, and parallel news fetching.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from gnews import GNews
import concurrent.futures
import random
import nltk

# Try to import TextBlob; if missing, degrade gracefully.
TEXTBLOB_AVAILABLE = True
try:
    from textblob import TextBlob
except Exception:
    TEXTBLOB_AVAILABLE = False

# Try to import VADER; download lexicon if not present
try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
except Exception:
    try:
        nltk.download("vader_lexicon")
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
    except Exception:
        # If vader can't be loaded, we'll fail later with clear message
        SentimentIntensityAnalyzer = None

# Ensure punkt for TextBlob (if available)
if TEXTBLOB_AVAILABLE:
    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        try:
            nltk.download("punkt")
        except Exception:
            # continue; TextBlob may still work without punkt for simple usage
            pass

# ---------------------------------
# Streamlit page config
# ---------------------------------
st.set_page_config(page_title="Stock News & Sentiment Dashboard", layout="wide")
st.title("📰 Stock Market News Dashboard — Robust TextBlob Handling")

# If TextBlob not available, inform user how to add it
if not TEXTBLOB_AVAILABLE:
    st.warning(
        "TextBlob package not found in the environment. "
        "The app will still run using VADER. "
        "To enable TextBlob sentiment, add `textblob` to your requirements.txt and redeploy."
    )

if SentimentIntensityAnalyzer is None:
    st.error(
        "VADER Sentiment Analyzer could not be loaded. "
        "Ensure `nltk` is installed and the 'vader_lexicon' resource is available."
    )

# ---------------------------------
# Sidebar controls
# ---------------------------------
st.sidebar.header("Filter & Options")

time_period = st.sidebar.selectbox(
    "Select Time Period",
    ["Last Week", "Last Month", "Last 3 Months", "Last 6 Months"]
)

# Build sentiment model options depending on availability
sentiment_options = ["VADER (fast, rule-based)"]
if TEXTBLOB_AVAILABLE:
    sentiment_options.append("TextBlob (polarity)")

sentiment_model = st.sidebar.selectbox("Sentiment Analyzer", sentiment_options)

max_articles_per_stock = st.sidebar.slider("Max articles per stock (each stock)", 1, 20, 5)
parallel_workers = st.sidebar.slider("Parallel workers (threads)", 2, 20, 8)

st.sidebar.markdown("---")
st.sidebar.subheader("Add / Search Stock")
custom_stock_input = st.sidebar.text_input("Type a stock or company name (e.g. 'Reliance Industries')", "")
add_stock_button = st.sidebar.button("Add to list")

# ---------------------------------
# Default list of F&O Stocks (NSE)
# ---------------------------------
default_fo_stocks = [
    "Reliance Industries", "TCS", "Infosys", "HDFC Bank", "ICICI Bank",
    "State Bank of India", "HCL Technologies", "Wipro", "Larsen & Toubro",
    "Tata Motors", "Bajaj Finance", "Axis Bank", "NTPC", "ITC",
    "Adani Enterprises", "Coal India", "Power Grid", "Maruti Suzuki",
    "Tech Mahindra", "Sun Pharma"
]

if "fo_stocks" not in st.session_state:
    st.session_state.fo_stocks = default_fo_stocks.copy()

if add_stock_button and custom_stock_input.strip():
    st.session_state.fo_stocks.insert(0, custom_stock_input.strip())
    st.success(f"Added '{custom_stock_input.strip()}' to the list")

st.sidebar.markdown("**Current tracked stocks (top 30 shown):**")
for idx, s in enumerate(st.session_state.fo_stocks[:30]):
    col1, col2 = st.sidebar.columns([8, 2])
    col1.write(s)
    if col2.button("Remove", key=f"rm_{idx}"):
        st.session_state.fo_stocks.pop(idx)
        st.experimental_rerun()

# ---------------------------------
# Date range calculation
# ---------------------------------
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

# ---------------------------------
# Caching helpers
# ---------------------------------
@st.cache_data(show_spinner=False)
def make_gnews_client():
    return GNews(language="en", country="IN")

@st.cache_data(show_spinner=False)
def fetch_articles_for_query(query: str, start: str, end: str, max_articles: int):
    client = make_gnews_client()
    try:
        articles = client.get_news(query)
        return articles[:max_articles] if articles else []
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def compute_sentiment_for_text(text: str, model: str):
    text = (text or "").strip()
    if not text:
        return {"score": 0.0, "label": "Neutral"}

    if model == "VADER":
        if SentimentIntensityAnalyzer is None:
            return {"score": 0.0, "label": "Neutral"}
        sid = SentimentIntensityAnalyzer()
        scores = sid.polarity_scores(text)
        compound = scores.get("compound", 0.0)
        if compound >= 0.05:
            label = "Positive"
        elif compound <= -0.05:
            label = "Negative"
        else:
            label = "Neutral"
        return {"score": compound, "label": label}
    else:  # TextBlob path (only used if TEXTBLOB_AVAILABLE is True)
        if not TEXTBLOB_AVAILABLE:
            # fallback to neutral if user somehow selected TextBlob but it's unavailable
            return {"score": 0.0, "label": "Neutral"}
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity
        if polarity > 0.05:
            label = "Positive"
        elif polarity < -0.05:
            label = "Negative"
        else:
            label = "Neutral"
        return {"score": polarity, "label": label}

def sentiment_emoji(label: str):
    return {"Positive": "🟢", "Neutral": "🟡", "Negative": "🔴"}.get(label, "🟡")

# ---------------------------------
# UI Tabs
# ---------------------------------
news_tab, trending_tab, sentiment_tab = st.tabs(["📰 News", "🔥 Trending Stocks", "💬 Sentiment"])

# ---------------------------------
# Parallel fetch wrapper
# ---------------------------------
def fetch_counts_parallel(stock_list, start_s, end_s, max_articles_per_stock, workers=8):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(fetch_articles_for_query, stock, start_s, end_s, max_articles_per_stock): stock
            for stock in stock_list
        }
        for future in concurrent.futures.as_completed(futures):
            stock = futures[future]
            try:
                articles = future.result()
                count = len(articles) if articles else 0
                results.append({"Stock": stock, "News Count": count, "Articles": articles})
            except Exception:
                results.append({"Stock": stock, "News Count": 0, "Articles": []})
    return results

# ---------------------------------
# Tab 1: News
# ---------------------------------
with news_tab:
    st.header("🗞️ Latest News — Top Stocks & Search")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Quick Search")
        search_input = st.text_input("Search company / keyword (press Enter)", "")
        search_btn = st.button("Search Now", key="search_btn")
    with col2:
        st.subheader("Options")
        show_only_with_news = st.checkbox("Show only stocks with news", value=False)
        top_n_display = st.number_input("Show top N stocks (by news)", min_value=1, max_value=50, value=10)

    stocks_to_check = st.session_state.fo_stocks.copy()

    if search_input.strip() or search_btn:
        query = search_input.strip() or search_input
        with st.spinner(f"Fetching news for '{query}'..."):
            articles = fetch_articles_for_query(query, start_date_str, end_date_str, max_articles_per_stock)
            if not articles:
                st.warning(f"No news found for '{query}' in selected range ({start_date_str} → {end_date_str}).")
            else:
                st.subheader(f"Search results for: {query}")
                for art in articles:
                    title = art.get("title", "No title")
                    url = art.get("url", "")
                    publisher = art.get("publisher", {}).get("title", "Unknown")
                    published = art.get("published", "")
                    st.markdown(f"**[{title}]({url})** — *{publisher}* • {published}")
                st.divider()

    with st.spinner("Fetching counts for tracked stocks..."):
        counts_list = fetch_counts_parallel(stocks_to_check[:50], start_date_str, end_date_str, max_articles_per_stock, workers=parallel_workers)

    df_counts = pd.DataFrame(counts_list).sort_values("News Count", ascending=False)
    if show_only_with_news:
        df_counts = df_counts[df_counts["News Count"] > 0]

    st.subheader(f"Top {top_n_display} tracked stocks by news count ({time_period})")
    st.dataframe(df_counts[["Stock", "News Count"]].head(top_n_display).reset_index(drop=True))

    st.subheader("Expand a stock to view fetched articles")
    for idx, row in df_counts.head(top_n_display).iterrows():
        stock = row["Stock"]
        articles = row.get("Articles", []) or []
        with st.expander(f"{stock} — {len(articles)} articles"):
            if not articles:
                st.write("No articles found.")
            else:
                for art in articles:
                    title = art.get("title", "No title")
                    url = art.get("url", "")
                    publisher = art.get("publisher", {}).get("title", "Unknown")
                    published = art.get("published", "")
                    desc = art.get("description", "") or art.get("summary", "")
                    st.markdown(f"**[{title}]({url})** — *{publisher}* • {published}")
                    if desc:
                        st.write(desc)
                    st.markdown("---")

# ---------------------------------
# Tab 2: Trending Stocks
# ---------------------------------
with trending_tab:
    st.header("🔥 Trending Stocks Based on News Coverage")

    with st.spinner("Computing trending stocks..."):
        counts_list = fetch_counts_parallel(st.session_state.fo_stocks[:50], start_date_str, end_date_str, max_articles_per_stock, workers=parallel_workers)

    trending_df = pd.DataFrame(counts_list).sort_values(by="News Count", ascending=False)
    st.write(f"Showing top 30 trending stocks for the period: {start_date_str} → {end_date_str}")
    if trending_df.empty:
        st.warning("No news data available for the selected stocks / date range.")
    else:
        import plotly.express as px
        plot_df = trending_df.head(30).copy()
        fig = px.bar(
            plot_df,
            x="Stock",
            y="News Count",
            color="News Count",
            color_continuous_scale="Bluered",
            title=f"Trending Stocks ({time_period}) — Top {min(30, len(plot_df))}",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.download_button(
        label="Download trending CSV",
        data=trending_df.to_csv(index=False),
        file_name=f"trending_stocks_{start_date_str}_to_{end_date_str}.csv",
        mime="text/csv",
    )

# ---------------------------------
# Tab 3: Sentiment analysis
# ---------------------------------
with sentiment_tab:
    st.header("💬 Sentiment Analysis (Real)")

    analyzer_choice = "VADER" if sentiment_model.startswith("VADER") else "TextBlob"
    if analyzer_choice == "TextBlob" and not TEXTBLOB_AVAILABLE:
        st.error("TextBlob was selected but it's not available. Falling back to VADER.")
        analyzer_choice = "VADER"

    st.write(f"Using **{analyzer_choice}** for sentiment. (Max {max_articles_per_stock} articles per stock)")

    analyze_top_n = st.number_input("Analyze top N stocks by news count", min_value=1, max_value=50, value=10)
    analyze_stocks = trending_df.head(analyze_top_n)["Stock"].tolist() if not trending_df.empty else st.session_state.fo_stocks[:analyze_top_n]
    st.write(f"Analyzing: {', '.join(analyze_stocks)}")

    with st.spinner("Fetching articles for sentiment analysis..."):
        articles_results = fetch_counts_parallel(analyze_stocks, start_date_str, end_date_str, max_articles_per_stock, workers=parallel_workers)

    aggregated = []
    for item in articles_results:
        stock = item["Stock"]
        articles = item.get("Articles", []) or []
        if not articles:
            aggregated.append({"Stock": stock, "Article Title": None, "Publisher": None, "Published": None, "Snippet": None, "Sentiment": "Neutral", "Score": 0.0})
            continue
        for art in articles:
            title = art.get("title") or ""
            publisher = art.get("publisher", {}).get("title", "")
            published = art.get("published", "")
            snippet = art.get("description", "") or art.get("summary", "") or ""
            text_for_sentiment = f"{title}. {snippet}"
            sentiment_res = compute_sentiment_for_text(text_for_sentiment, analyzer_choice)
            emoji = sentiment_emoji(sentiment_res["label"])
            aggregated.append({
                "Stock": stock,
                "Article Title": title,
                "Publisher": publisher,
                "Published": published,
                "Snippet": snippet,
                "Sentiment": sentiment_res["label"],
                "Score": sentiment_res["score"],
                "Emoji": emoji,
                "URL": art.get("url", "")
            })

    sentiment_df = pd.DataFrame(aggregated)

    if sentiment_df.empty:
        st.warning("No article data to analyze for sentiment.")
    else:
        st.subheader("Per-article Sentiment (sample)")
        st.dataframe(sentiment_df[["Stock", "Article Title", "Publisher", "Published", "Sentiment", "Score", "Emoji"]].head(200))

        agg_stock = sentiment_df.groupby("Stock").agg(
            Articles_Count=pd.NamedAgg(column="Article Title", aggfunc=lambda s: s.count()),
            Positive_Count=pd.NamedAgg(column="Sentiment", aggfunc=lambda s: (s == "Positive").sum()),
            Neutral_Count=pd.NamedAgg(column="Sentiment", aggfunc=lambda s: (s == "Neutral").sum()),
            Negative_Count=pd.NamedAgg(column="Sentiment", aggfunc=lambda s: (s == "Negative").sum()),
            Avg_Score=pd.NamedAgg(column="Score", aggfunc="mean"),
        ).reset_index()

        def net_sentiment(row):
            if row["Articles_Count"] == 0:
                return 0.0
            return (row["Positive_Count"] - row["Negative_Count"]) / row["Articles_Count"]

        agg_stock["Net_Sentiment"] = agg_stock.apply(net_sentiment, axis=1)
        agg_stock = agg_stock.sort_values("Net_Sentiment", ascending=False)

        st.subheader("Aggregated Sentiment by Stock")
        st.dataframe(agg_stock)

        try:
            import plotly.express as px
            fig2 = px.bar(
                agg_stock,
                x="Stock",
                y="Net_Sentiment",
                color="Net_Sentiment",
                color_continuous_scale="RdYlGn",
                title=f"Net Sentiment per Stock ({analyzer_choice})",
            )
            st.plotly_chart(fig2, use_container_width=True)
        except Exception:
            st.write("Plotting library not available to show charts.")

        st.download_button(
            label="Download per-article sentiment CSV",
            data=sentiment_df.to_csv(index=False),
            file_name=f"sentiment_articles_{start_date_str}_to_{end_date_str}.csv",
            mime="text/csv",
        )
        st.download_button(
            label="Download aggregated sentiment CSV",
            data=agg_stock.to_csv(index=False),
            file_name=f"sentiment_aggregated_{start_date_str}_to_{end_date_str}.csv",
            mime="text/csv",
        )

# ---------------------------------
# Footer
# ---------------------------------
st.markdown("---")
st.caption("📊 Data from Google News | Sentiment via VADER / TextBlob | Built with ❤️ using Streamlit")

# End of file
