import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from gnews import GNews
import random

# ---------------------------------
# App Title
# ---------------------------------
st.set_page_config(page_title="Stock News & Sentiment Dashboard", layout="wide")
st.title("📰 Stock Market News Dashboard")

# ---------------------------------
# Sidebar: Time Range Selector
# ---------------------------------
st.sidebar.header("Filter Options")
time_period = st.sidebar.selectbox(
    "Select Time Period",
    ["Last Week", "Last Month", "Last 3 Months", "Last 6 Months"]
)

# ---------------------------------
# Date Range Logic
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

# ---------------------------------
# List of F&O Stocks (NSE)
# ---------------------------------
fo_stocks = [
    "Reliance Industries", "TCS", "Infosys", "HDFC Bank", "ICICI Bank",
    "State Bank of India", "HCL Technologies", "Wipro", "Larsen & Toubro",
    "Tata Motors", "Bajaj Finance", "Axis Bank", "NTPC", "ITC",
    "Adani Enterprises", "Coal India", "Power Grid", "Maruti Suzuki",
    "Tech Mahindra", "Sun Pharma"
]

# ---------------------------------
# Helper Function to Fetch News
# ---------------------------------
def fetch_news_count(stock, start, end):
    try:
        googlenews = GNews(language='en', country='IN', start_date=start, end_date=end)
        news = googlenews.get_news(stock)
        return len(news)
    except Exception:
        return 0

# ---------------------------------
# Tabs Setup
# ---------------------------------
news_tab, trending_tab, sentiment_tab = st.tabs(["📰 News", "🔥 Trending Stocks", "💬 Sentiment"])

# ---------------------------------
# Tab 1: News
# ---------------------------------
with news_tab:
    st.header("🗞️ Latest News for Top Stocks")

    gnews = GNews(language='en', country='IN', start_date=start_date, end_date=today)
    all_news = []

    for stock in fo_stocks[:5]:  # Show top 5 for speed
        st.subheader(f"🔹 {stock}")
        articles = gnews.get_news(stock)
        if articles:
            for art in articles[:5]:
                st.markdown(f"**[{art['title']}]({art['url']})** — *{art['publisher']['title']}*")
            all_news.extend(articles)
        else:
            st.warning(f"No news found for {stock} in selected range.")

# ---------------------------------
# Tab 2: Trending Stocks (Colored Bar Chart)
# ---------------------------------
with trending_tab:
    st.header("🔥 Trending Stocks Based on News Coverage")

    progress = st.progress(0)
    news_counts = []

    for i, stock in enumerate(fo_stocks):
        count = fetch_news_count(stock, start_date, today)
        news_counts.append({"Stock": stock, "News Count": count})
        progress.progress((i + 1) / len(fo_stocks))

    trending_df = pd.DataFrame(news_counts)
    trending_df = trending_df.sort_values(by="News Count", ascending=False)

    # Use Plotly for colored bars
    import plotly.express as px
    fig = px.bar(
        trending_df,
        x="Stock",
        y="News Count",
        color="News Count",
        color_continuous_scale="Bluered",
        title=f"Trending Stocks ({time_period})",
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------
# Tab 3: Sentiment Analysis (Demo)
# ---------------------------------
with sentiment_tab:
    st.header("💬 Sentiment Analysis (Demo)")

    sample_data = []
    for stock in trending_df.head(10)["Stock"]:
        sentiment = random.choice(["Positive", "Neutral", "Negative"])
        emoji_icon = {"Positive": "🟢", "Neutral": "🟡", "Negative": "🔴"}[sentiment]
        sample_data.append({"Stock": stock, "Sentiment": sentiment, "Emoji": emoji_icon})

    sentiment_df = pd.DataFrame(sample_data)
    st.dataframe(sentiment_df)

# ---------------------------------
# Footer
# ---------------------------------
st.markdown("---")
st.caption("📊 Data from Google News | Built with ❤️ using Streamlit and Plotly")
