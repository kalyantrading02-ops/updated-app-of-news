import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from gnews import GNews
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from concurrent.futures import ThreadPoolExecutor, as_completed
import nltk

# ---------------------------------
# Setup
# ---------------------------------
nltk.download('vader_lexicon', quiet=True)

st.set_page_config(page_title="Stock News & Sentiment Dashboard", layout="wide")
st.title("📰 Stock Market News Dashboard")

# ---------------------------------
# Sidebar Filters
# ---------------------------------
st.sidebar.header("Filter Options")
time_period = st.sidebar.selectbox(
    "Select Time Period",
    ["Last Week", "Last Month", "Last 3 Months", "Last 6 Months"]
)

search_stock = st.sidebar.text_input("🔍 Search any Stock (optional)", "").strip()

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
# F&O Stock List
# ---------------------------------
fo_stocks = [
    "Reliance Industries", "TCS", "Infosys", "HDFC Bank", "ICICI Bank",
    "State Bank of India", "HCL Technologies", "Wipro", "Larsen & Toubro",
    "Tata Motors", "Bajaj Finance", "Axis Bank", "NTPC", "ITC",
    "Adani Enterprises", "Coal India", "Power Grid", "Maruti Suzuki",
    "Tech Mahindra", "Sun Pharma"
]

# If user searched a stock, add it at top
if search_stock:
    if search_stock not in fo_stocks:
        fo_stocks.insert(0, search_stock)

# ---------------------------------
# Cached News Fetch Function
# ---------------------------------
@st.cache_data(show_spinner=False)
def fetch_news(stock, start, end):
    try:
        gnews = GNews(language='en', country='IN', start_date=start, end_date=end)
        articles = gnews.get_news(stock)
        return articles
    except Exception as e:
        st.write(f"⚠️ Error fetching news for {stock}: {e}")
        return []

# ---------------------------------
# Parallel News Fetch
# ---------------------------------
def fetch_all_news(stocks, start, end):
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_stock = {executor.submit(fetch_news, s, start, end): s for s in stocks}
        for future in as_completed(future_to_stock):
            stock = future_to_stock[future]
            try:
                articles = future.result()
                results.append({"Stock": stock, "Articles": articles, "News Count": len(articles)})
            except Exception as e:
                st.write(f"⚠️ Error for {stock}: {e}")
                results.append({"Stock": stock, "Articles": [], "News Count": 0})
    return results

# ---------------------------------
# Sentiment Analyzer
# ---------------------------------
analyzer = SentimentIntensityAnalyzer()

def analyze_sentiment(text):
    score = analyzer.polarity_scores(text)["compound"]
    if score > 0.05:
        return "Positive", "🟢"
    elif score < -0.05:
        return "Negative", "🔴"
    else:
        return "Neutral", "🟡"

# ---------------------------------
# Tabs
# ---------------------------------
news_tab, trending_tab, sentiment_tab = st.tabs(["📰 News", "🔥 Trending Stocks", "💬 Sentiment"])

# ---------------------------------
# Tab 1: News
# ---------------------------------
with news_tab:
    st.header("🗞️ Latest News for Stocks")

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

# ---------------------------------
# Tab 2: Trending Stocks
# ---------------------------------
with trending_tab:
    st.header("🔥 Trending Stocks by News Count")

    counts_list = [{"Stock": r["Stock"], "News Count": r["News Count"]} for r in all_results if "News Count" in r]
    if not counts_list:
        st.warning("No news data available to display.")
    else:
        df_counts = pd.DataFrame(counts_list)
        df_counts = df_counts.sort_values("News Count", ascending=False)

        fig = px.bar(
            df_counts,
            x="Stock",
            y="News Count",
            color="News Count",
            color_continuous_scale="Bluered",
            title=f"Trending Stocks ({time_period})"
        )
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------
# Tab 3: Sentiment Analysis
# ---------------------------------
with sentiment_tab:
    st.header("💬 Sentiment Analysis from News Headlines")

    sentiment_data = []
    for res in all_results:
        stock = res["Stock"]
        for art in res["Articles"][:3]:  # top 3 per stock
            sentiment, emoji_icon = analyze_sentiment(art["title"])
            sentiment_data.append({"Stock": stock, "Headline": art["title"], "Sentiment": sentiment, "Emoji": emoji_icon})

    if sentiment_data:
        sentiment_df = pd.DataFrame(sentiment_data)
        st.dataframe(sentiment_df)
    else:
        st.warning("No news available for sentiment analysis.")

# ---------------------------------
# Footer
# ---------------------------------
st.markdown("---")
st.caption("📊 Data from Google News | Built with ❤️ using Streamlit, Plotly & NLTK VADER")
