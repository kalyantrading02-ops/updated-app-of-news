# app.py
"""
Streamlit News App — full-featured version with 4 tabs.
Tabs:
  1) News (unchanged old features)
  2) Trending Stocks (placeholder area — keep your logic here)
  3) Sentiment (placeholder area)
  4) Upcoming Market-Moving Events (moved to LAST tab)
All original features are preserved: sidebar filters, API key, refresh, bookmarks,
article cards, read-more/detail view, caching + fallback, debug info.
"""

import streamlit as st
from datetime import datetime
import requests
from typing import List, Dict, Optional

# --- SETTINGS ---
st.set_page_config(page_title="News Dashboard", layout="wide", page_icon="🗞️")
DEFAULT_PAGE_SIZE = 6

# ---------- SAMPLE FALLBACK DATA ----------
SAMPLE_ARTICLES: List[Dict] = [
    {
        "source": {"id": None, "name": "Sample Source"},
        "author": "Jane Doe",
        "title": "Streamlit News App Loaded Successfully",
        "description": "This is fallback content shown when your news API is not reachable.",
        "url": "https://example.com/sample-article",
        "urlToImage": None,
        "publishedAt": datetime.utcnow().isoformat() + "Z",
        "content": "Full sample content. Replace with your API key or real fetch function.",
    },
]

# Sample placeholders for other tabs (you can replace with your real data)
SAMPLE_TRENDING = [
    {"symbol": "RELIANCE", "name": "Reliance Industries", "change": "+0.8%", "price": "2,550"},
    {"symbol": "TCS", "name": "Tata Consultancy Services", "change": "-0.2%", "price": "3,200"},
]
SAMPLE_SENTIMENT = {"overall": "Neutral", "score": 0.02, "breakdown": {"positive": 0.35, "neutral": 0.5, "negative": 0.15}}
SAMPLE_EVENTS = [
    {"date": "2025-11-07", "event": "RBI Policy Meeting", "importance": "High"},
    {"date": "2025-11-10", "event": "US Nonfarm Payrolls", "importance": "High"},
    {"date": "2025-11-12", "event": "Company XYZ Q3 Results", "importance": "Medium"},
]

# ---------- HELPERS ----------
def format_datetime(dt_str: Optional[str]) -> str:
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        return dt_str


@st.cache_data(ttl=300)
def fetch_news(api_key: str, category: str = "general", q: str = "", page_size: int = 10, page: int = 1, source: Optional[str] = None) -> Dict:
    """
    Fetch news from NewsAPI.org (v2/top-headlines).
    If you use a different provider, replace this function accordingly.
    """
    if not api_key:
        raise ValueError("No API key provided.")
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": api_key,
        "category": category if category and category != "all" else None,
        "q": q or None,
        "pageSize": page_size,
        "page": page,
        "country": "in",  # change as needed
    }
    if source:
        params["sources"] = source
    params = {k: v for k, v in params.items() if v is not None}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def safe_get_articles(api_key: str, **kwargs) -> List[Dict]:
    """
    Try to fetch articles using fetch_news; on error, return SAMPLE_ARTICLES.
    """
    try:
        data = fetch_news(api_key, **kwargs)
        articles = data.get("articles", [])
        if not articles:
            st.warning("No articles returned by the API — showing fallback sample articles.")
            return SAMPLE_ARTICLES
        return articles
    except Exception as e:
        st.error(f"Error fetching news: {e}")
        st.info("Showing fallback sample articles.")
        return SAMPLE_ARTICLES


def render_article_card(article: Dict, idx: int):
    """
    Render a single article card exactly like original app.
    """
    title = article.get("title") or "Untitled"
    desc = article.get("description") or ""
    url = article.get("url") or ""
    image = article.get("urlToImage")
    source_name = article.get("source", {}).get("name") or ""
    published = format_datetime(article.get("publishedAt"))

    st.markdown("---")
    cols = st.columns([0.12, 0.88])
    with cols[0]:
        st.write(f"**{idx}**")
    with cols[1]:
        if image:
            try:
                st.image(image, width=300)
            except Exception:
                # ignore image errors to avoid blanking out main view
                pass
        st.markdown(f"### {title}")
        st.caption(f"{source_name} — {published}")
        st.write(desc)
        action_cols = st.columns([1, 1, 1])
        with action_cols[0]:
            if st.button("Open article", key=f"open_{idx}"):
                st.write(f"[Open original article]({url})")
        with action_cols[1]:
            if st.button("Read more", key=f"readmore_{idx}"):
                st.session_state["selected_article"] = article
        with action_cols[2]:
            if st.button("Bookmark", key=f"bookmark_{idx}"):
                bookmarks = st.session_state.get("bookmarks", [])
                if article not in bookmarks:
                    bookmarks.append(article)
                    st.session_state["bookmarks"] = bookmarks
                    st.success("Bookmarked ✅")
                else:
                    st.info("Already bookmarked")


# ---------- MAIN ----------
def main():
    # Initialize session state for bookmarks and selected article
    if "bookmarks" not in st.session_state:
        st.session_state["bookmarks"] = []
    if "selected_article" not in st.session_state:
        st.session_state["selected_article"] = None
    if "last_refresh" not in st.session_state:
        st.session_state["last_refresh"] = None

    # --- SIDEBAR (unchanged features) ---
    with st.sidebar:
        st.title("🗞️ Controls")
        api_key = st.text_input("API Key (optional)", value="", help="Leave empty to use sample fallback articles.")
        st.markdown("### Filters")
        category = st.selectbox("Category", ["all", "business", "entertainment", "general", "health", "science", "sports", "technology"], index=3)
        source = st.text_input("Source (optional)", value="", help="Optional source id (e.g., bbc-news)")
        query = st.text_input("Search query (optional)", value="", placeholder="Type keywords to search")
        page_size = st.number_input("Articles per page", min_value=1, max_value=20, value=DEFAULT_PAGE_SIZE)
        page = st.number_input("Page", min_value=1, value=1)

        st.markdown("---")
        if st.button("Refresh"):
            # clear cache and force rerun (keeps old refresh behavior)
            try:
                st.cache_data.clear()
            except Exception:
                pass
            st.session_state["last_refresh"] = datetime.utcnow().isoformat() + "Z"
            st.experimental_rerun()

        if st.session_state["last_refresh"]:
            st.caption(f"Refreshed: {format_datetime(st.session_state['last_refresh'])}")

        st.markdown("---")
        st.subheader("Bookmarks")
        if st.session_state["bookmarks"]:
            for i, bm in enumerate(st.session_state["bookmarks"], start=1):
                st.write(f"{i}. {bm.get('title')}")
        else:
            st.write("_No bookmarks yet_")

        st.markdown("---")
        st.write("App info")
        st.caption("Single-file Streamlit app. Replace API key to fetch live news.")
        st.markdown("Made with ❤️")

    # --- TABS (only UI re-layout; old features preserved inside News tab) ---
    st.title("📰 Market Dashboard")
    st.write("Tabs: 1) News  2) Trending Stocks  3) Sentiment  4) Upcoming Events (last tab)")

    tab1, tab2, tab3, tab4 = st.tabs(["News", "Trending Stocks", "Sentiment", "Upcoming Events"])

    # ----- TAB 1: NEWS (exactly original main view & behavior) -----
    with tab1:
        st.header("Top Headlines")
        st.write("Browse top headlines. Use the sidebar to filter, search, and change page size.")

        # Fetch articles - exact original logic
        articles = safe_get_articles(api_key=api_key, category=category, q=query, page_size=page_size, page=page, source=(source or None))

        # If a selected article exists (from Read more), show detail view (same as original)
        if st.session_state.get("selected_article"):
            article = st.session_state["selected_article"]
            st.markdown("## Article detail")
            detail_cols = st.columns([0.6, 0.4])
            with detail_cols[0]:
                st.markdown(f"### {article.get('title')}")
                st.caption(f"{article.get('source', {}).get('name')} — {format_datetime(article.get('publishedAt'))}")
                if article.get("urlToImage"):
                    try:
                        st.image(article.get("urlToImage"), width=700)
                    except Exception:
                        pass
                st.write(article.get("content") or article.get("description") or "No content available.")
                st.markdown(f"[Open original article]({article.get('url')})")
                if st.button("Close", key="close_detail"):
                    st.session_state["selected_article"] = None
            with detail_cols[1]:
                st.write("Quick actions")
                if st.button("Bookmark this article", key="bm_detail"):
                    bookmarks = st.session_state.get("bookmarks", [])
                    if article not in bookmarks:
                        bookmarks.append(article)
                        st.session_state["bookmarks"] = bookmarks
                        st.success("Bookmarked ✅")
                    else:
                        st.info("Already bookmarked")
                st.write("---")
                st.write("Article metadata")
                st.write(f"Author: {article.get('author')}")
                st.write(f"Source: {article.get('source', {}).get('name')}")
                st.write(f"Published: {format_datetime(article.get('publishedAt'))}")

            st.markdown("---")
            st.write("Back to list")
            if st.button("Back to list", key="back_list"):
                st.session_state["selected_article"] = None

        # Otherwise list the articles (same render loop)
        else:
            st.subheader(f"Showing {len(articles)} articles (page {page})")
            if not articles:
                st.warning("No articles to display.")
            # Render each article using the same render_article_card (keeps buttons, bookmarks, etc.)
            for idx, art in enumerate(articles, start=1 + (page - 1) * page_size):
                try:
                    render_article_card(art, idx)
                except Exception as e:
                    st.error(f"Error displaying article: {e}")

    # ----- TAB 2: TRENDING STOCKS (placeholder; keep your logic here) -----
    with tab2:
        st.header("Trending Stocks")
        st.write("This section lists currently trending stocks. Replace sample data with your real trending logic if available.")
        for s in SAMPLE_TRENDING:
            cols = st.columns([0.2, 0.6, 0.2])
            with cols[0]:
                st.subheader(s["symbol"])
            with cols[1]:
                st.write(s["name"])
            with cols[2]:
                st.write(f"{s['price']} ({s['change']})")

    # ----- TAB 3: SENTIMENT (placeholder) -----
    with tab3:
        st.header("Market Sentiment")
        st.write("Overall market sentiment based on news & social signals (sample data).")
        st.metric(label="Overall Sentiment", value=SAMPLE_SENTIMENT["overall"], delta=f"{SAMPLE_SENTIMENT['score']}")
        st.write("Breakdown:")
        st.write(SAMPLE_SENTIMENT["breakdown"])

    # ----- TAB 4: UPCOMING EVENTS (moved to LAST tab) -----
    with tab4:
        st.header("Upcoming Market-Moving Events")
        st.write("This tab contains upcoming events that may move the market. It's intentionally the LAST tab.")
        st.write("If you have a calendar or API for events, plug it in here. For now, sample events are shown.")
        for ev in SAMPLE_EVENTS:
            st.markdown("---")
            st.subheader(ev["event"])
            st.write(f"Date: {ev['date']} | Importance: {ev['importance']}")

    # Footer / debug: unchanged
    st.markdown("---")
    st.write("Debug / meta")
    st.write(f"Category: **{category}** | Query: **{query or '—'}** | Page size: **{page_size}** | Page: **{page}**")
    st.caption("If the main area is blank: check console logs, and ensure code outside `with st.sidebar:` blocks is not indented into the sidebar.")

if __name__ == "__main__":
    main()
