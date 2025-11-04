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

# -----------------------------
# SIDEBAR — DARK MODE SWIPE TOGGLE
# -----------------------------
st.sidebar.header("⚙️ Settings")

# Streamlit toggle switch for instant dark/light mode
dark_mode = st.sidebar.toggle("🌗 Dark Mode", value=True, help="Switch instantly between Dark & Light Mode")

# -----------------------------
# APPLY DYNAMIC THEMES
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

# Custom CSS for instant theme switching
st.markdown(f"""
    <style>
        body {{
            background: {bg_gradient};
            color: {text_color};
            transition: all 0.3s ease-in-out;
        }}
        .stApp {{
            background: {bg_gradient} !important;
            color: {text_color} !important;
        }}
        h1, h2, h3, h4, h5 {{
            color: {accent_color} !important;
            transition: color 0.3s ease-in-out;
        }}
        .stTabs [data-baseweb="tab"] {{
            background-color: rgba(255,255,255,0.05);
            color: {text_color} !important;
            border-radius: 10px;
            padding: 8px 16px;
        }}
        .stTabs [data-baseweb="tab"]:hover {{
            background-color: rgba(255,255,255,0.15);
        }}
        .stButton button {{
            background-color: {accent_color} !important;
            color: black !important;
            border-radius: 6px;
        }}
        .stDataFrame {{
            border-radius: 10px;
            background-color: rgba(255,255,255,0.05);
        }}
        .block-container {{
            padding-top: 2rem;
            padding-bottom: 2rem;
        }}
    </style>
""", unsafe_allow_html=True)

# -----------------------------
# APP TITLE
# -----------------------------
st.title("💹 Stock Market News & Sentiment Dashboard")

# -----------------------------
# AUTO REFRESH EVERY 10 MIN
# -----------------------------
refresh_interval = 600  # 10 minutes
if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = time.time()
elif time.time() - st.session_state["last_refresh"] > refresh_interval:
    st.session_state["last_refresh"] = time.time()
    st.rerun()

# -----------------------------
# SIDEBAR FILTERS
# -----------------------------
st.sidebar.header("📅 Filter Options")
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

custom_stocks = [s.strip() for s in search_input.split(",") if s.strip()]
for stock in custom_stocks:
    if stock not in fo_stocks:
        fo_stocks.insert(0, stock)

# -----------------------------
# PERFORMANCE BOOSTERS
# -----------------------------
@st.cache_data(ttl=600, show_spinner=False)
def fetch_news(stock, start, end):
    try:
        gnews = GNews(language='en', country='IN', max_results=10)
        gnews.start_date, gnews.end_date = start, end
        return gnews.get_news(stock) or []
    except Exception:
        return []

def fetch_all_news(stocks, start, end):
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_news, s, start, end): s for s in stocks}
        for f in as_completed(futures):
            stock = futures[f]
            try:
                articles = f.result()
                results.append({"Stock": stock, "Articles": articles, "News Count": len(articles)})
            except Exception:
                results.append({"Stock": stock, "Articles": [], "News Count": 0})
    return results

# Sentiment Analysis
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
# TAB 1 — NEWS SECTION (Improved)
# -----------------------------
with news_tab:
    st.header("🗞️ Latest Market News for F&O Stocks")

    # Function to fetch news (cached for speed)
    @st.cache_data(ttl=600, show_spinner=False)
    def fetch_news(stock, start, end):
        try:
            gnews = GNews(language='en', country='IN', max_results=10)
            gnews.start_date, gnews.end_date = start, end
            return gnews.get_news(stock) or []
        except Exception:
            return []

    # Parallel fetching for speed
    from concurrent.futures import ThreadPoolExecutor, as_completed

    @st.cache_data(ttl=600, show_spinner=False)
    def fetch_all_news(stocks, start, end):
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_news, s, start, end): s for s in stocks}
            for future in as_completed(futures):
                stock = futures[future]
                try:
                    articles = future.result()
                    results.append({"Stock": stock, "Articles": articles})
                except Exception:
                    results.append({"Stock": stock, "Articles": []})
        return results

    # Fetch top 10 stocks
    with st.spinner("Fetching the latest financial news..."):
        news_results = fetch_all_news(fo_stocks[:10], start_date, today)

    # Display results cleanly
    for result in news_results:
        stock = result["Stock"]
        articles = result["Articles"]
        with st.expander(f"🔹 {stock} ({len(articles)} Articles)", expanded=False):
            if articles:
                for art in articles[:5]:
                    title = art["title"]
                    url = art["url"]
                    publisher = art["publisher"]["title"] if "publisher" in art and art["publisher"] else "Unknown Source"
                    published_date = art.get("published date", "N/A")
                    st.markdown(
                        f"""
                        **[{title}]({url})**  
                        🏢 *{publisher}* | 🗓️ *{published_date}*
                        """
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
        all_results = fetch_all_news(fo_stocks, start_date, today)

    counts = [{"Stock": r["Stock"], "News Count": r["News Count"]} for r in all_results]
    df_counts = pd.DataFrame(counts).sort_values("News Count", ascending=False)

    fig = px.bar(
        df_counts,
        x="Stock",
        y="News Count",
        color="News Count",
        color_continuous_scale="Turbo",
        title=f"Trending F&O Stocks ({time_period})",
        template=plot_theme
    )
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# TAB 3 — SENTIMENT
# -----------------------------
with sentiment_tab:
    st.header("💬 Sentiment Analysis")

    with st.spinner("Analyzing sentiment..."):
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
        st.dataframe(sentiment_df, use_container_width=True)
        st.download_button(
            "📥 Download Sentiment Data",
            sentiment_df.to_csv(index=False).encode("utf-8"),
            "sentiment_data.csv",
            "text/csv"
        )
    else:
        st.warning("No sentiment data found.")

# -----------------------------
# TAB 4 — COMPARE STOCKS
# -----------------------------
with compare_tab:
    st.header("📊 Compare Stock Sentiment")

    if custom_stocks:
        with st.spinner("Comparing..."):
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
            st.dataframe(compare_df, use_container_width=True)
            st.download_button(
                "📥 Download Comparison Data",
                compare_df.to_csv(index=False).encode("utf-8"),
                "compare_stocks.csv",
                "text/csv"
            )
    else:
        st.info("💡 Enter 2–3 stock names in sidebar to compare sentiment.")

# -----------------------------
# FOOTER
# -----------------------------
st.markdown("---")
st.caption(f"📊 Data Source: Google News | Mode: {'Dark' if dark_mode else 'Light'} | Auto-refresh every 10 min | Built with ❤️ using Streamlit & Plotly")
