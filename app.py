import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from GoogleNews import GoogleNews
import emoji

# ---------------------------------
# App Title
# ---------------------------------
st.set_page_config(page_title="Stock News & Sentiment App", layout="wide")
st.title("📰 Stock Market News Dashboard")

# ---------------------------------
# Sidebar: Filters
# ---------------------------------
st.sidebar.header("Filter Options")

time_period = st.sidebar.selectbox(
    "Select Time Period",
    ["Last Week", "Last Month", "Last 3 Months", "Last 6 Months"]
)

fo_stocks = [
    "Reliance Industries", "TCS", "Infosys", "HDFC Bank", "ICICI Bank",
    "State Bank of India", "HCL Technologies", "Wipro", "Larsen & Toubro",
    "Tata Motors", "Bajaj Finance", "Axis Bank", "NTPC", "ITC", "Adani Enterprises",
    "Coal India", "Power Grid", "Maruti Suzuki", "Tech Mahindra", "Sun Pharma"
]

selected_stocks = st.sidebar.multiselect("Select Stocks", fo_stocks, default=["Reliance Industries"])

# ---------------------------------
# Convert time filter to date range
# ---------------------------------
today = datetime.today()

if time_period == "Last Week":
    start_date = today - timedelta(days=7)
elif time_period == "Last Month":
    start_date = today - timedelta(days=30)
elif time_period == "Last 3 Months":
    start_date = today - timedelta(days=90)
elif time_period == "Last 6 Months":
    start_date = today - timedelta(days=180)

# ---------------------------------
# Helper Function: Fetch News
# ---------------------------------
def fetch_news(stock, start, end):
    googlenews = GoogleNews(start=start.strftime("%m/%d/%Y"), end=end.strftime("%m/%d/%Y"))
    googlenews.search(stock)
    result = googlenews.result(sort=True)
    news_items = []

    for item in result:
        news_items.append({
            "Stock": stock,
            "Title": item.get("title", ""),
            "Media": item.get("media", ""),
            "Date": item.get("date", ""),
            "Link": item.get("link", "")
        })
    return news_items

# ---------------------------------
# Tabs Setup
# ---------------------------------
tabs = st.tabs(["📰 News", "🔥 Trending Stocks", "💬 Sentiment"])
news_tab, trending_tab, sentiment_tab = tabs

# ---------------------------------
# Tab 1: News
# ---------------------------------
with news_tab:
    st.header("🗞️ Latest Stock News")
    all_news = []

    for stock in selected_stocks:
        st.subheader(f"🔹 {stock}")
        news_data = fetch_news(stock, start_date, today)
        if news_data:
            df = pd.DataFrame(news_data)
            st.dataframe(df[["Title", "Media", "Date", "Link"]])
            all_news.extend(news_data)
        else:
            st.warning(f"No news found for {stock} in selected time range.")

# ---------------------------------
# Tab 2: Trending Stocks
# ---------------------------------
with trending_tab:
    st.header("🔥 Trending Stocks")
    if len(selected_stocks) > 1:
        trending_df = pd.DataFrame({"Stock": selected_stocks})
        trending_df["News Count"] = [len(fetch_news(stock, start_date, today)) for stock in selected_stocks]
        trending_df = trending_df.sort_values(by="News Count", ascending=False)
        st.bar_chart(trending_df.set_index("Stock"))
    else:
        st.info("Select at least two stocks to compare trends.")

# ---------------------------------
# Tab 3: Sentiment Analysis (Simple Demo)
# ---------------------------------
with sentiment_tab:
    st.header("💬 Sentiment Analysis")

    if len(selected_stocks) > 0:
        sentiment_results = []
        for stock in selected_stocks:
            # Dummy sentiment example (you can plug in a real NLP model)
            sentiment = "Positive" if len(stock) % 2 == 0 else "Neutral"
            emoji_icon = "🟢" if sentiment == "Positive" else "🟡"
            sentiment_results.append({"Stock": stock, "Sentiment": sentiment, "Emoji": emoji_icon})

        sentiment_df = pd.DataFrame(sentiment_results)
        st.dataframe(sentiment_df)
    else:
        st.warning("Please select stocks to analyze sentiment.")

# ---------------------------------
# Footer
# ---------------------------------
st.markdown("---")
st.caption("📊 Data sourced from Google News | Built with ❤️ using Streamlit")
