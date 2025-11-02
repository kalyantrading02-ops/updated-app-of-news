import streamlit as st
import feedparser
from textblob import TextBlob
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import re

# -----------------------------
# Streamlit Page Config
# -----------------------------
st.set_page_config(page_title="F&O Stock News Dashboard", layout="wide")
st.title("📊 F&O Stocks News & Sentiment Dashboard")

# -----------------------------
# Sidebar Options
# -----------------------------
st.sidebar.header("📰 News Filters")
period = st.sidebar.selectbox(
    "Select Time Period",
    ["Last Week", "Last Month", "Last 3 Months", "Last 6 Months"]
)

refresh_rate = st.sidebar.slider("⏱️ Auto-refresh every (minutes)", 0, 60, 0)

if refresh_rate > 0:
    st.experimental_rerun()

period_days = {
    "Last Week": 7,
    "Last Month": 30,
    "Last 3 Months": 90,
    "Last 6 Months": 180,
}
since_date = datetime.now() - timedelta(days=period_days[period])

# -----------------------------
# Helper Functions
# -----------------------------
def fetch_news_for_stock(stock):
    """Fetch Google News for a specific stock."""
    search_terms = (
        f"{stock} shareholding pattern OR management OR corporate actions "
        f"OR order wins OR capacity expansion OR new projects "
        f"OR credit rating OR audit report OR insider deals OR bulk deals"
    )
    feed_url = f"https://news.google.com/rss/search?q={search_terms}+when:6m&hl=en-IN&gl=IN&ceid=IN:en"
    return feedparser.parse(feed_url)

def get_sentiment(text):
    """Use TextBlob to assign sentiment."""
    try:
        score = TextBlob(text).sentiment.polarity
        if score > 0.05:
            return "Positive"
        elif score < -0.05:
            return "Negative"
        else:
            return "Neutral"
    except Exception:
        return "Neutral"

def build_news_df(stocks, since_date):
    """Build combined DataFrame of all news for given stocks."""
    news_data = []
    for s in stocks:
        feed = fetch_news_for_stock(s)
        if not feed or not hasattr(feed, "entries"):
            continue
        for e in feed.entries:
            title = e.title
            link = e.link
            published = getattr(e, "published", datetime.now().strftime("%Y-%m-%d"))
            published_date = datetime.strptime(published[:16], "%a, %d %b %Y") if "," in published else datetime.now()
            if published_date.date() < since_date.date():
                continue
            sentiment = get_sentiment(title)
            news_data.append({
                "Stock": s,
                "Title": title,
                "Link": link,
                "Date": published_date.date(),
                "Sentiment": sentiment,
            })
    return pd.DataFrame(news_data)

# -----------------------------
# Stock List (NSE F&O Major Stocks)
# -----------------------------
stocks_list = [
    "Reliance Industries", "HDFC Bank", "ICICI Bank", "Infosys", "TCS", "Axis Bank",
    "SBI", "Bharti Airtel", "Kotak Mahindra Bank", "Larsen & Toubro", "ITC",
    "Hindustan Unilever", "Adani Enterprises", "Maruti Suzuki", "Wipro", "NTPC",
    "Power Grid", "Bajaj Finance", "HCL Technologies", "Tech Mahindra",
    "UltraTech Cement", "Tata Motors", "Grasim", "Sun Pharma", "Nestle India",
    "Tata Steel", "JSW Steel", "Coal India", "ONGC", "HDFC Life", "Asian Paints"
]

# -----------------------------
# Tabs Layout
# -----------------------------
tab1, tab2, tab3 = st.tabs(["📰 News", "📈 Trending", "💬 Sentiment Analysis"])

# -----------------------------
# Build News Data
# -----------------------------
with st.spinner("Fetching latest news..."):
    df = build_news_df(stocks_list, since_date)

if df.empty:
    st.warning("No news found for selected period.")
else:
    # Sentiment Emoji Mapping
    sentiment_emojis = {"Positive": "🟢", "Neutral": "🟡", "Negative": "🔴"}
    df["Emoji"] = df["Sentiment"].map(sentiment_emojis).fillna("⚪")

# -----------------------------
# 📰 TAB 1: News Headlines
# -----------------------------
with tab1:
    st.subheader("Latest F&O Stock News (Investor-Focused)")
    if not df.empty:
        for _, r in df.iterrows():
            emoji = r.get("Emoji", "⚪")
            st.markdown(
                f"**{emoji} {r['Stock']}** — *{r['Sentiment']}*  \n"
                f"[{r['Title']}]({r['Link']})  \n"
                f"🗓️ {r['Date']}",
                unsafe_allow_html=True,
            )
    else:
        st.info("No relevant investor-focused news found.")

# -----------------------------
# 📈 TAB 2: Trending Stocks
# -----------------------------
with tab2:
    st.subheader("Trending Stocks (Most Mentioned)")
    if not df.empty:
        top_trending = df["Stock"].value_counts().reset_index()
        top_trending.columns = ["Stock", "Mentions"]
        fig = px.bar(
            top_trending.head(15),
            x="Stock",
            y="Mentions",
            title="🔥 Top 15 Most Mentioned Stocks in News",
            text="Mentions"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trending data available yet.")

# -----------------------------
# 💬 TAB 3: Sentiment Analysis
# -----------------------------
with tab3:
    st.subheader("Sentiment Distribution")
    if not df.empty and "Sentiment" in df.columns:
        # Pie Chart
        sentiment_counts = df["Sentiment"].value_counts().reset_index()
        sentiment_counts.columns = ["Sentiment", "Count"]
        fig1 = px.pie(
            sentiment_counts,
            names="Sentiment",
            values="Count",
            title="Overall Sentiment Distribution",
            color="Sentiment",
            color_discrete_map={"Positive": "green", "Neutral": "gold", "Negative": "red"}
        )
        st.plotly_chart(fig1, use_container_width=True)

        # Daily Trend Chart (Safe)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
        daily = (
            df.groupby(["Date", "Sentiment"])
            .size()
            .unstack(fill_value=0)
            .reindex(columns=["Positive", "Neutral", "Negative"], fill_value=0)
            .reset_index()
        )

        for col in ["Positive", "Neutral", "Negative"]:
            if col not in daily.columns:
                daily[col] = 0

        fig2 = px.line(
            daily,
            x="Date",
            y=["Positive", "Neutral", "Negative"],
            title="📈 Daily Sentiment Trend",
            markers=True
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Not enough sentiment data to show analysis.")
