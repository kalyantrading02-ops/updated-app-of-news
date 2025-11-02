# app.py - F&O News + Sentiment Dashboard
import streamlit as st
import feedparser
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import quote
import yfinance as yf
import plotly.express as px
from textblob import TextBlob
from streamlit_autorefresh import st_autorefresh

# ---------------------------
# Page Config
# ---------------------------
st.set_page_config(page_title="F&O News + Sentiment Dashboard", layout="wide", page_icon="📰")

# ---------------------------
# F&O Stock List
# ---------------------------
FNO_MAP = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "AXISBANK": "AXISBANK.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "LT": "LT.NS",
    "ITC": "ITC.NS",
    "HINDUNILVR": "HINDUNILVR.NS",
    "HCLTECH": "HCLTECH.NS",
    "TECHM": "TECHM.NS",
    "WIPRO": "WIPRO.NS",
    "ADANIENT": "ADANIENT.NS",
    "ADANIPORTS": "ADANIPORTS.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "ULTRACEMCO": "ULTRACEMCO.NS",
    "BAJFINANCE": "BAJFINANCE.NS",
    "BAJAJFINSV": "BAJAJFINSV.NS",
    "TATAMOTORS": "TATAMOTORS.NS",
    "TATASTEEL": "TATASTEEL.NS",
    "ONGC": "ONGC.NS",
    "COALINDIA": "COALINDIA.NS",
    "POWERGRID": "POWERGRID.NS",
    "NTPC": "NTPC.NS",
    "ASIANPAINT": "ASIANPAINT.NS",
    "MARUTI": "MARUTI.NS",
    "HEROMOTOCO": "HEROMOTOCO.NS",
    "EICHERMOT": "EICHERMOT.NS",
    "BPCL": "BPCL.NS",
    "IOC": "IOC.NS",
    "HDFCLIFE": "HDFCLIFE.NS",
    "INDUSINDBK": "INDUSINDBK.NS",
    "DIVISLAB": "DIVISLAB.NS",
    "SUNPHARMA": "SUNPHARMA.NS"
}

ALL_STOCKS = list(FNO_MAP.keys())

# ---------------------------
# Sidebar
# ---------------------------
st.sidebar.title("⚙️ Controls")

period = st.sidebar.selectbox("🗓 Time Range", ["Last 1 Week", "Last 1 Month", "Last 3 Months", "Last 6 Months"])
days_map = {"Last 1 Week": 7, "Last 1 Month": 30, "Last 3 Months": 90, "Last 6 Months": 180}
since_date = datetime.now() - timedelta(days=days_map[period])
st.sidebar.write(f"📅 Showing news since: {since_date.strftime('%d %b %Y')}")

selected = st.sidebar.multiselect("Select Stocks (multi-select)", ALL_STOCKS, default=["RELIANCE", "TCS", "INFY"])

refresh_minutes = st.sidebar.number_input("Auto-refresh every (minutes, 0 = off)", min_value=0, max_value=60, value=0, step=1)
if refresh_minutes and refresh_minutes > 0:
    count = st_autorefresh(interval=refresh_minutes * 60 * 1000, key="autorefresh")
    st.sidebar.caption(f"Auto-refreshed {count} times")

dark_mode = st.sidebar.checkbox("🌙 Dark mode", value=False)
if dark_mode:
    st.markdown("""
        <style>
        .stApp { background-color: #0e1117; color: #e6edf3; }
        .stDataFrame { color: #e6edf3; }
        </style>
    """, unsafe_allow_html=True)

fetch_now = st.sidebar.button("🔄 Fetch News Now")

# ---------------------------
# Helper Functions
# ---------------------------
@st.cache_data(ttl=300)
def fetch_news_for_stock(stock):
    """Fetch Google News RSS feed for given stock"""
    safe_q = quote(f"{stock} stock India")
    url = f"https://news.google.com/rss/search?q={safe_q}&hl=en-IN&gl=IN&ceid=IN:en"
    return feedparser.parse(url)

@st.cache_data(ttl=300)
def get_live_price(ticker):
    """Fetch current price using yfinance"""
    try:
        data = yf.Ticker(ticker).history(period="1d")
        if data.empty:
            return None
        close = data["Close"].iloc[-1]
        openp = data["Open"].iloc[-1]
        change = ((close - openp) / openp) * 100 if openp != 0 else 0
        return {"price": round(close, 2), "change_pct": round(change, 2)}
    except Exception:
        return None

def get_sentiment(text):
    """Analyze sentiment using TextBlob"""
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    if polarity > 0.1:
        return "Positive", "🟢"
    elif polarity < -0.1:
        return "Negative", "🔴"
    else:
        return "Neutral", "🟡"

def build_news_df(stocks, since_date):
    """Fetch and prepare news dataframe with sentiment"""
    all_rows = []
    for s in stocks:
        feed = fetch_news_for_stock(s)
        for e in feed.entries:
            try:
                if "published_parsed" not in e:
                    continue
                pub = datetime(*e.published_parsed[:6])
                if pub < since_date:
                    continue
                title = e.title
                link = e.link
                source = getattr(e, "source", "Google News")
                sentiment, emoji = get_sentiment(title)
                all_rows.append({
                    "Stock": s,
                    "Title": title,
                    "Sentiment": sentiment,
                    "Emoji": emoji,
                    "Source": source,
                    "Published": pub,
                    "Link": link
                })
            except Exception:
                continue
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df = df.sort_values(by="Published", ascending=False).reset_index(drop=True)
    return df

# ---------------------------
# Tabs
# ---------------------------
tab1, tab2, tab3 = st.tabs(["📰 News Feed", "📊 Trending Stocks", "💬 Sentiment Analysis"])
news_tab, trending_tab, sentiment_tab = tabs

# ---------------------------
# TAB 1: NEWS
# ---------------------------
with news_tab:
    st.header("📰 Latest F&O News with Sentiment")
    if not selected:
        st.info("Select at least one stock from the sidebar.")
    else:
        with st.spinner("Fetching latest news..."):
            df = build_news_df(selected, since_date)
            prices = {s: get_live_price(FNO_MAP[s]) for s in selected}

        if df.empty:
            st.warning("No news found for the selected stocks or time range.")
        else:
            for _, r in df.iterrows():
                price_info = prices.get(r["Stock"], {})
                price_str = f"₹{price_info.get('price', '—')} ({price_info.get('change_pct', '—')}%)"
                st.markdown(
                    f"**{r['Emoji']} {r['Stock']}** — {r['Sentiment']} | {r['Title']}  \n"
                    f"📅 {r['Published'].strftime('%Y-%m-%d %H:%M')} | 💰 {price_str}  \n"
                    f"[🔗 Read full article]({r['Link']})"
                )
                st.markdown("---")

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("💾 Download CSV", data=csv, file_name="fno_news_sentiment.csv", mime="text/csv")

# ---------------- Trending Stocks Tab ----------------
with tab2:
    st.header("📊 Trending Stocks (Most Mentioned)")
    st.caption("Automatically analyses most-mentioned NSE/BSE F&O stocks in news")

    time_range = st.selectbox(
        "🕒 Select Time Range",
        ["1 Week", "1 Month", "3 Months", "6 Months"]
    )

    # Define F&O stocks (short list for demo; you can expand this)
    fno_stocks = [
        "Reliance Industries", "HDFC Bank", "Infosys", "ICICI Bank", "TCS",
        "State Bank of India", "Larsen & Toubro", "Axis Bank", "Bharti Airtel",
        "Maruti Suzuki", "ITC", "Kotak Mahindra Bank", "Wipro", "HCL Technologies",
        "Tata Motors", "NTPC", "Adani Enterprises", "Hindustan Unilever"
    ]

    since_date = get_since_date(time_range)
    st.write(f"Fetching news since **{since_date.strftime('%d %b %Y')}**...")

    all_news = []
    progress = st.progress(0)
    for i, s in enumerate(fno_stocks):
        feed = fetch_news_for_stock(s)
        for e in feed.entries[:5]:  # limit to top 5 per stock
            all_news.append({"Stock": s, "Title": e.title})
        progress.progress((i + 1) / len(fno_stocks))

    # Count mentions
    df_trend = pd.DataFrame(all_news)
    trend = df_trend["Stock"].value_counts().reset_index()
    trend.columns = ["Stock", "Mentions"]

    st.subheader("Top 10 Most Mentioned Stocks")
    st.bar_chart(trend.set_index("Stock").head(10))

    with st.expander("View Full Mention List"):
        st.dataframe(trend)

# ---------------------------
# TAB 3: SENTIMENT OVERVIEW
# ---------------------------
with sentiment_tab:
    st.header("📈 Sentiment Overview")
    df_sent = build_news_df(selected, since_date)
    if df_sent.empty:
        st.warning("No sentiment data available.")
    else:
        df_sent["Date"] = df_sent["Published"].dt.date
        daily = df_sent.groupby(["Date", "Sentiment"]).size().unstack(fill_value=0).reset_index()
        fig2 = px.line(daily, x="Date", y=["Positive", "Neutral", "Negative"], title="Daily Sentiment Trend")
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Sentiment Distribution")
        dist = df_sent["Sentiment"].value_counts().reset_index()
        dist.columns = ["Sentiment", "Count"]
        st.dataframe(dist)

st.markdown("---")
st.caption("Built with Streamlit • News via Google RSS • Sentiment via TextBlob • Live data from Yahoo Finance")
