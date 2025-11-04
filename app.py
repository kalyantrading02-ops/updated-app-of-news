import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from gnews import GNews
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from concurrent.futures import ThreadPoolExecutor, as_completed
import nltk
import time

# -----------------------------
# INITIAL SETUP
# -----------------------------
nltk.download('vader_lexicon', quiet=True)
st.set_page_config(page_title="Stock News & Sentiment Dashboard", layout="wide")
st.title("📰 Stock Market News Dashboard")

# Auto-refresh every 10 minutes
refresh_interval = 600  # seconds
if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = time.time()
elif time.time() - st.session_state["last_refresh"] > refresh_interval:
    st.session_state["last_refresh"] = time.time()
    st.rerun()

# -----------------------------
# SIDEBAR CONTROLS
# -----------------------------
st.sidebar.header("Filter Options")

time_period = st.sidebar.selectbox(
    "Select Time Period",
    ["Last Week", "Last Month", "Last 3 Months", "Last 6 Months"]
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
# F&O STOCK LIST
# -----------------------------
fo_stocks = [
    "Reliance Industries", "TCS", "Infosys", "HDFC Bank", "ICICI Bank",
    "State Bank of India", "HCL Technologies", "Wipro", "Larsen & Toubro",
    "Tata Motors", "Bajaj Finance", "Axis Bank", "NTPC", "ITC",
    "Adani Enterprises", "Coal India", "Power Grid", "Maruti Suzuki",
    "Tech Mahindra", "Sun Pharma"
]

# Add custom user stocks
custom_stocks = [s.strip() for s in search_input.split(",") if s.strip()]
for stock in custom_stocks:
    if stock not in fo_stocks:
        fo_stocks.insert(0, stock)

# -----------------------------
# CACHED FUNCTIONS
# -----------------------------
@st.cache_data(ttl=600, show_spinner=False)
def fetch_news(stock, start, end):
    try:
        gnews = GNews(language='en', country='IN', start_date=start, end_date=end)
        return gnews.get_news(stock) or []
    except Exception:
        return []

def fetch_all_news(stocks, start, end):
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_stock = {executor.submit(fetch_news, s, start, end): s for s in stocks}
        for future in as_completed(future_to_stock):
            stock = future_to_stock[future]
            try:
                articles = future.result()
                results.append({
                    "Stock": stock,
                    "Articles": articles,
                    "News Count": len(articles)
                })
            except Exception:
                results.append({"Stock": stock, "Articles": [], "News Count": 0})
    return results

# -----------------------------
# SENTIMENT ANALYSIS
# -----------------------------
analyzer = SentimentIntensityAnalyzer()

def analyze_sentiment(text):
    score = analyzer.polarity_scores(text)["compound"]
    if score > 0.2:
        return "Positive", "🟢"
    elif score < -0.2:
        return "Negative", "🔴"
    else:
        return "Neutral", "🟡"

# -----------------------------
# MAIN TABS
# -----------------------------
news_tab, trending_tab, sentiment_tab, compare_tab = st.tabs([
    "📰 News", "🔥 Trending Stocks", "💬 Sentiment", "📊 Compare Stocks"
])

# -----------------------------
# TAB 1 — NEWS
# -----------------------------
with news_tab:
    st.header("🗞️ Latest Market News")

    with st.spinner("Fetching news for F&O stocks..."):
        all_results = fetch_all_news(fo_stocks[:10], start_date, today)

    for res in all_results[:5]:
        stock = res["Stock"]
        articles = res["Articles"]
        st.subheader(f"🔹 {stock}")
        if articles:
            for art in articles[:5]:
                st.markdown(f"**[{art['title']}]({art['url']})** — *{art['publisher']['title']}*")
        else:
            st.warning(f"No news found for {stock}.")

# -----------------------------
# TAB 2 — TRENDING STOCKS (Unchanged)
# -----------------------------
with trending_tab:
    st.header("🔥 Trending Stocks by News Count")

    with st.spinner("Calculating trending stocks..."):
        all_results = fetch_all_news(fo_stocks, start_date, today)

    counts = [{"Stock": r["Stock"], "News Count": r["News Count"]} for r in all_results]
    df_counts = pd.DataFrame(counts).sort_values("News Count", ascending=False)

    fig = px.bar(
        df_counts,
        x="Stock",
        y="News Count",
        color="News Count",
        color_continuous_scale="Turbo",
        title=f"Trending Stocks ({time_period})"
    )
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# TAB 3 — SENTIMENT
# -----------------------------
with sentiment_tab:
    st.header("💬 Sentiment Analysis from News Headlines")

    with st.spinner("Analyzing sentiment for F&O stocks..."):
        sentiment_data = []
        all_results = fetch_all_news(fo_stocks[:10], start_date, today)
        for res in all_results:
            stock = res["Stock"]
            for art in res["Articles"][:3]:
                sentiment, emoji = analyze_sentiment(art["title"])
                sentiment_data.append({
                    "Stock": stock,
                    "Headline": art["title"],
                    "Sentiment": sentiment,
                    "Emoji": emoji
                })

    if sentiment_data:
        sentiment_df = pd.DataFrame(sentiment_data)
        st.dataframe(sentiment_df)

        # Download Option
        st.download_button(
            "📥 Download Sentiment Data",
            sentiment_df.to_csv(index=False).encode("utf-8"),
            "sentiment_data.csv",
            "text/csv"
        )
    else:
        st.warning("No sentiment data available.")

# -----------------------------
# TAB 4 — COMPARE STOCKS
# -----------------------------
with compare_tab:
    st.header("📊 Compare Selected Stocks")

    if custom_stocks:
        with st.spinner("Fetching comparison data..."):
            compare_results = fetch_all_news(custom_stocks, start_date, today)
            compare_data = []
            for res in compare_results:
                stock = res["Stock"]
                total = len(res["Articles"])
                pos, neg, neu = 0, 0, 0
                for art in res["Articles"][:5]:
                    s, _ = analyze_sentiment(art["title"])
                    if s == "Positive": pos += 1
                    elif s == "Negative": neg += 1
                    else: neu += 1
                compare_data.append({
                    "Stock": stock,
                    "Positive": pos,
                    "Negative": neg,
                    "Neutral": neu,
                    "Total News": total
                })

            compare_df = pd.DataFrame(compare_data)
            st.dataframe(compare_df)

            # Download comparison
            st.download_button(
                "📥 Download Comparison Data",
                compare_df.to_csv(index=False).encode("utf-8"),
                "compare_stocks.csv",
                "text/csv"
            )
    else:
        st.info("💡 Enter 2–3 stock names in the sidebar to compare sentiment.")

# -----------------------------
# FOOTER
# -----------------------------
st.markdown("---")
st.caption("📊 Data from Google News | Built with ❤️ using Streamlit, Plotly & NLTK VADER | Auto-refreshes every 10 minutes")
