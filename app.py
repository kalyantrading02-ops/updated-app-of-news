# app.py - F&O News Dashboard (upgraded)
import streamlit as st
import feedparser
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import quote
import yfinance as yf
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import time

# ---------------------------
# Page config
# ---------------------------
st.set_page_config(page_title="F&O News + Sentiment Dashboard", layout="wide", page_icon="📈")

# ---------------------------
# Ensure NLTK VADER is available
# ---------------------------
try:
    _ = SentimentIntensityAnalyzer()
except Exception:
    with st.spinner("Downloading sentiment models (first run)..."):
        nltk.download("vader_lexicon")
    # re-initialize
    _ = SentimentIntensityAnalyzer()

sia = SentimentIntensityAnalyzer()

# ---------------------------
# F&O stock list (names + tickers for yfinance)
# You can extend this dictionary with more tickers/names
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

ALL_STOCK_SYMBOLS = list(FNO_MAP.keys())

# ---------------------------
# Sidebar controls
# ---------------------------
st.sidebar.title("⚙️ Controls")

period = st.sidebar.selectbox("🗓 Time Range", ["Last 1 Week", "Last 1 Month", "Last 3 Months", "Last 6 Months"])
days_map = {"Last 1 Week": 7, "Last 1 Month": 30, "Last 3 Months": 90, "Last 6 Months": 180}
days = days_map[period]
since_date = datetime.now() - timedelta(days=days)
st.sidebar.write(f"Showing articles since: {since_date.strftime('%d %b %Y')}")

# allow multi-select to compare or fetch multiple stocks
selected = st.sidebar.multiselect("Select Stocks (multi-select)", ALL_STOCK_SYMBOLS, default=["RELIANCE", "TCS", "INFY"])

# search box (matches inside stock symbol or name)
search_text = st.sidebar.text_input("Search stock (symbol/name) - optional", "")

# auto-refresh control (minutes)
refresh_minutes = st.sidebar.number_input("Auto-refresh every (minutes, 0 = off)", min_value=0, max_value=60, value=0, step=1)
if refresh_minutes and refresh_minutes > 0:
    # st_autorefresh returns an int that increments on refresh
    count = st_autorefresh(interval=refresh_minutes * 60 * 1000, key="autorefresh")
    st.sidebar.caption(f"Auto-refreshed {count} times")

# dark mode toggle (basic)
dark_mode = st.sidebar.checkbox("Dark mode (basic)", value=False)
if dark_mode:
    st.markdown(
        """
        <style>
        .stApp { background-color: #0e1117; color: #e6edf3; }
        .stDataFrame { color: #e6edf3; }
        </style>
        """,
        unsafe_allow_html=True
    )

# Fetch button (explicit)
fetch_now = st.sidebar.button("🔄 Fetch News Now")

# ---------------------------
# Utility: safe url builder + fetcher
# ---------------------------
@st.cache_data(ttl=300)
def fetch_feed_for_query(query_text):
    safe_query = quote(f"{query_text} stock India")
    url = f"https://news.google.com/rss/search?q={safe_query}&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(url)
    return feed

@st.cache_data(ttl=300)
def get_live_price(ticker):
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.history(period="1d")
        if info is None or info.empty:
            return None
        last_row = info.tail(1)
        price = float(last_row["Close"].iloc[0])
        prev_open = float(last_row["Open"].iloc[0])
        change_pct = ((price - prev_open) / prev_open) * 100 if prev_open != 0 else 0
        return {"price": round(price, 2), "change_pct": round(change_pct, 2)}
    except Exception:
        return None

def analyze_sentiment(text):
    # return dict of compound, pos, neu, neg and label
    scores = sia.polarity_scores(text)
    compound = scores["compound"]
    if compound >= 0.05:
        label = "Positive"
    elif compound <= -0.05:
        label = "Negative"
    else:
        label = "Neutral"
    scores["label"] = label
    return scores

# ---------------------------
# Core: build news dataframe for selected stocks
# ---------------------------
def build_news_df(stocks_list, since_dt, search_term=""):
    rows = []
    for s in stocks_list:
        # allow search filter on symbol
        if search_term:
            if search_term.lower() not in s.lower():
                continue
        display_name = s  # symbol e.g., "RELIANCE"
        feed = fetch_feed_for_query(display_name)
        entries = getattr(feed, "entries", []) or []
        for e in entries:
            try:
                published_parsed = e.get("published_parsed")
                if not published_parsed:
                    continue
                pub_dt = datetime(*published_parsed[:6])
                if pub_dt < since_dt:
                    continue
                title = e.get("title", "")
                link = e.get("link", "")
                source = e.get("source", {}).get("title", "") if isinstance(e.get("source", {}), dict) else e.get("source", "")
                sentiment = analyze_sentiment(title)
                rows.append({
                    "Stock": display_name,
                    "Title": title,
                    "Source": source or "Google News",
                    "Published": pub_dt,
                    "Link": link,
                    "SentimentCompound": sentiment["compound"],
                    "SentimentLabel": sentiment["label"]
                })
            except Exception:
                # skip malformed entry
                continue
    if not rows:
        return pd.DataFrame(columns=["Stock","Title","Source","Published","Link","SentimentCompound","SentimentLabel"])
    df = pd.DataFrame(rows)
    df = df.sort_values(by="Published", ascending=False).reset_index(drop=True)
    return df

# ---------------------------
# UI: Tabs
# ---------------------------
tabs = st.tabs(["News", "Trending", "Sentiment"])
news_tab, trend_tab, sentiment_tab = tabs

# Trigger fetch when user presses button or on load when selected stocks present
do_fetch = fetch_now or (not fetch_now and selected)

# ---------------------------
# TAB 1: News
# ---------------------------
with news_tab:
    st.header("📰 News")
    st.write("Fetched from Google News RSS. Shows sentiment + live price where available.")

    if not selected:
        st.info("Select at least one stock from the sidebar to fetch news.")
    else:
        if do_fetch:
            with st.spinner("Fetching news... this may take a moment for many stocks"):
                df_news = build_news_df(selected, since_date, search_text)
                # fetch live prices for displayed unique tickers
                tickers = {}
                for sym in df_news["Stock"].unique() if not df_news.empty else []:
                    yf_ticker = FNO_MAP.get(sym)
                    if yf_ticker:
                        tickers[sym] = get_live_price(yf_ticker)
                    else:
                        tickers[sym] = None

            if df_news.empty:
                st.warning("No articles found for selected stocks/time range.")
            else:
                # show a count summary
                st.success(f"Found {len(df_news)} articles for {len(df_news['Stock'].unique())} stocks.")
                # show filter for label and source
                cols_filter = st.columns([1,1,2])
                with cols_filter[0]:
                    label_filter = st.selectbox("Filter by Sentiment", ["All","Positive","Neutral","Negative"])
                with cols_filter[1]:
                    source_filter = st.text_input("Filter by Source (contains)", value="")
                with cols_filter[2]:
                    stock_filter = st.selectbox("Filter by Stock", ["All"] + sorted(df_news["Stock"].unique().tolist()))

                df_disp = df_news.copy()
                if label_filter != "All":
                    df_disp = df_disp[df_disp["SentimentLabel"] == label_filter]
                if source_filter:
                    df_disp = df_disp[df_disp["Source"].str.contains(source_filter, case=False, na=False)]
                if stock_filter != "All":
                    df_disp = df_disp[df_disp["Stock"] == stock_filter]

                # Add live price columns
                df_disp["Price"] = df_disp["Stock"].apply(lambda s: tickers.get(s)["price"] if tickers.get(s) else None)
                df_disp["Change%"] = df_disp["Stock"].apply(lambda s: tickers.get(s)["change_pct"] if tickers.get(s) else None)

                # Format published for display
                df_disp["PublishedStr"] = df_disp["Published"].dt.strftime("%Y-%m-%d %H:%M")

                # Show as table with links (clickable link via markdown)
                def make_row_md(row):
                    link_md = f"[Open article]({row['Link']})"
                    price_text = f"{row['Price']} ({row['Change%']}%)" if pd.notna(row['Price']) else "-"
                    return f"**{row['Stock']}** • {row['PublishedStr']}  \n**{row['Title']}**  \nSource: {row['Source']} • Price: {price_text}  \n{link_md}"

                # Show each article as expandable card
                for idx, r in df_disp.iterrows():
                    with st.expander(f"{r['Stock']} — {r['Published'].strftime('%Y-%m-%d %H:%M')} — {r['SentimentLabel']}"):
                        st.write(r["Title"])
                        st.markdown(f"**Source:** {r['Source']}  \n**Sentiment:** {r['SentimentLabel']} (compound={r['SentimentCompound']})")
                        if pd.notna(r.get("Price")):
                            st.markdown(f"**Live price:** {r.get('Price')} ({r.get('Change%')}%)")
                        st.markdown(f"[Read full article]({r['Link']})")

                # Download CSV
                csv = df_news.copy()
                csv["Published"] = csv["Published"].dt.strftime("%Y-%m-%d %H:%M")
                csv_bytes = csv.to_csv(index=False).encode("utf-8")
                st.download_button("💾 Download all news as CSV", data=csv_bytes, file_name="fo_news.csv", mime="text/csv")

# ---------------------------
# TAB 2: Trending
# ---------------------------
with trend_tab:
    st.header("📊 Trending (Most Mentioned Stocks)")
    if not selected:
        st.info("Select stocks in the sidebar.")
    else:
        # rely on df_news from earlier; if not present, fetch minimal
        df_news_local = build_news_df(selected, since_date, search_text)
        if df_news_local.empty:
            st.warning("No news to analyze.")
        else:
            counts = df_news_local["Stock"].value_counts().reset_index()
            counts.columns = ["Stock", "Mentions"]
            fig = px.bar(counts, x="Stock", y="Mentions", title="Top mentioned stocks", labels={"Mentions": "Number of articles"})
            st.plotly_chart(fig, use_container_width=True)

            # show top 5 sources for top stock
            top_stock = counts.iloc[0]["Stock"]
            st.write(f"Top stock: **{top_stock}**")
            top_sources = df_news_local[df_news_local["Stock"] == top_stock]["Source"].value_counts().reset_index()
            top_sources.columns = ["Source", "Count"]
            st.table(top_sources.head(10))

# ---------------------------
# TAB 3: Sentiment
# ---------------------------
with sentiment_tab:
    st.header("📈 Sentiment Overview")
    df_for_sent = build_news_df(selected, since_date, search_text)
    if df_for_sent.empty:
        st.warning("No news to compute sentiment.")
    else:
        # Group by date and sentiment
        df_sent = df_for_sent.copy()
        df_sent["DateOnly"] = df_sent["Published"].dt.date
        daily = df_sent.groupby(["DateOnly", "SentimentLabel"]).size().unstack(fill_value=0).reset_index()
        # ensure columns exist
        for col in ["Positive","Neutral","Negative"]:
            if col not in daily.columns:
                daily[col] = 0
        daily = daily.sort_values("DateOnly")
        fig2 = px.line(daily, x="DateOnly", y=["Positive","Neutral","Negative"], title="Daily sentiment counts")
        st.plotly_chart(fig2, use_container_width=True)

        st.write("Latest sentiment distribution")
        dist = df_for_sent["SentimentLabel"].value_counts().reset_index()
        dist.columns = ["Sentiment","Count"]
        st.table(dist)

# ---------------------------
# Footer
# ---------------------------
st.markdown("---")
st.caption("Built with Streamlit • Live prices via yfinance • Sentiment (VADER) • Google News RSS")
