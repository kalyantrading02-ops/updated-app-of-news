# app.py
"""
Streamlit News App - Single-file, robust starter
Drop this into your project (replace your current app.py if needed).
Features:
- Sidebar with category, source, search, page-size & refresh
- Main area: paginated article cards, article detail view
- Caching of API calls, graceful fallback to sample data if API fails
- Session state bookmarks
- Good error messages (no silent except/pass)
- Keeps layout blocks properly closed and indented to avoid "only sidebar" issue
"""

import streamlit as st
from datetime import datetime
from typing import List, Dict, Optional
import requests
from functools import lru_cache

# --- SETTINGS ----
st.set_page_config(page_title="News Dashboard", layout="wide", page_icon="🗞️")
DEFAULT_PAGE_SIZE = 6

# ---------- SAMPLE FALLBACK DATA (used if API unavailable) ----------
SAMPLE_ARTICLES: List[Dict] = [
    {
        "source": {"id": None, "name": "Sample Source"},
        "author": "Jane Doe",
        "title": "Sample headline: Streamlit app loaded with fallback data",
        "description": "This is fallback content shown when your news API is not reachable.",
        "url": "https://example.com/sample-article",
        "urlToImage": None,
        "publishedAt": datetime.utcnow().isoformat() + "Z",
        "content": "Full sample content. Replace with your API key or real fetch function.",
    },
    # Add more small sample items if desired
]

# ---------- HELPERS ----------
def format_datetime(dt_str: Optional[str]) -> str:
    if not dt_str:
        return ""
    try:
        # try parsing common ISO format
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        return dt_str

@st.cache_data(ttl=300)
def fetch_news_from_newsapi(api_key: str, category: str = "general", q: str = "",
                           page_size: int = 10, page: int = 1, source: Optional[str] = None) -> Dict:
    """
    Fetch news from NewsAPI.org (v2/top-headlines). If you use a different API, adapt this.
    Returns a dict with keys: status, totalResults, articles (list).
    """
    if not api_key:
        raise ValueError("No API key provided for NewsAPI. Provide one in the sidebar or leave empty to use fallback data.")
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": api_key,
        "category": category if category and category != "all" else None,
        "q": q or None,
        "pageSize": page_size,
        "page": page,
        "country": "in"  # change or make configurable as needed
    }
    if source:
        params["sources"] = source

    # Remove None params
    params = {k: v for k, v in params.items() if v is not None}

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def safe_get_articles(api_key: str, **kwargs) -> List[Dict]:
    """
    Try to fetch from NewsAPI, but on failure return SAMPLE_ARTICLES.
    """
    try:
        data = fetch_news_from_newsapi(api_key, **kwargs)
        articles = data.get("articles", [])
        if not articles:
            st.warning("No articles returned by the API — showing fallback sample articles.")
            return SAMPLE_ARTICLES
        return articles
    except Exception as e:
        st.error(f"Could not fetch news from API: {e}")
        st.info("Using fallback sample articles so the app remains functional.")
        return SAMPLE_ARTICLES


def render_article_card(article: Dict, idx: int):
    title = article.get("title") or "Untitled"
    source_name = article.get("source", {}).get("name") or ""
    desc = article.get("description") or ""
    url = article.get("url") or ""
    image = article.get("urlToImage")
    published = format_datetime(article.get("publishedAt"))

    st.markdown("---")
    cols = st.columns([0.12, 0.88])
    with cols[0]:
        st.write(f"**{idx}**")
    with cols[1]:
        if image:
            # image may be broken; avoid raising
            try:
                st.image(image, width=300)
            except Exception:
                # ignore image errors
                pass

        st.markdown(f"### {title}")
        st.caption(f"{source_name} — {published}")
        st.write(desc)
        row_cols = st.columns([1, 1, 1])
        with row_cols[0]:
            if st.button("Open article", key=f"open_{idx}"):
                st.write(f"[Open original article]({url})")
        with row_cols[1]:
            if st.button("Read more", key=f"more_{idx}"):
                st.session_state["selected_article"] = article
        with row_cols[2]:
            if st.button("Bookmark", key=f"save_{idx}"):
                # save to session bookmarks
                bookmarks = st.session_state.get("bookmarks", [])
                if article not in bookmarks:
                    bookmarks.append(article)
                    st.session_state["bookmarks"] = bookmarks
                    st.success("Bookmarked ✅")
                else:
                    st.info("Already bookmarked")


# ---------- MAIN LAYOUT ----------
def main():
    # Initialize session state
    if "bookmarks" not in st.session_state:
        st.session_state["bookmarks"] = []
    if "selected_article" not in st.session_state:
        st.session_state["selected_article"] = None
    if "last_refresh" not in st.session_state:
        st.session_state["last_refresh"] = None

    # ---- SIDEBAR ----
    with st.sidebar:
        st.title("🗞️ News Controls")
        api_key = st.text_input("NewsAPI API Key (optional)", value="", help="If empty, app uses fallback sample articles.")
        st.markdown("### Filters")
        category = st.selectbox("Category", ["all", "business", "entertainment", "general", "health", "science", "sports", "technology"], index=3)
        source = st.text_input("Source (optional)", value="", help="Optional: specific source id from NewsAPI (e.g. 'bbc-news').")
        query = st.text_input("Search query (optional)", value="", placeholder="Type keywords to search")
        page_size = st.number_input("Articles per page", min_value=1, max_value=20, value=DEFAULT_PAGE_SIZE)
        page = st.number_input("Page", min_value=1, value=1)
        st.markdown("---")
        if st.button("Refresh"):
            # simple way to force new fetch by clearing cache or changing a state
            st.cache_data.clear()
            st.session_state["last_refresh"] = datetime.utcnow().isoformat() + "Z"
            st.experimental_rerun()
        if st.session_state["last_refresh"]:
            st.caption(f"Refreshed: {format_datetime(st.session_state['last_refresh'])}")

        st.markdown("---")
        st.write("Bookmarks")
        if st.session_state["bookmarks"]:
            for i, bm in enumerate(st.session_state["bookmarks"], start=1):
                st.write(f"{i}. {bm.get('title')}")
        else:
            st.write("_No bookmarks yet_")

        st.markdown("---")
        st.write("App info")
        st.caption("Single-file Streamlit app. Replace API key to fetch live news.")
        st.markdown("Made with ❤️")

    # ---- MAIN PAGE ----
    st.title("📰 News Dashboard")
    st.write("Browse top headlines. Use the sidebar to filter, search, and change page size.")

    # Try to fetch articles (safe fallback included)
    articles = safe_get_articles(api_key=api_key, category=category, q=query, page_size=page_size, page=page, source=(source or None))

    # If user selected an article to read more, show detail
    selected = st.session_state.get("selected_article")
    if selected:
        st.markdown("## Article detail")
        detail_cols = st.columns([0.6, 0.4])
        with detail_cols[0]:
            st.markdown(f"### {selected.get('title')}")
            st.caption(f"{selected.get('source', {}).get('name')} — {format_datetime(selected.get('publishedAt'))}")
            if selected.get("urlToImage"):
                try:
                    st.image(selected.get("urlToImage"), width=700)
                except Exception:
                    pass
            st.write(selected.get("content") or selected.get("description") or "No content available.")
            st.markdown(f"[Open original article]({selected.get('url')})")
            if st.button("Close", key="close_detail"):
                st.session_state["selected_article"] = None
        with detail_cols[1]:
            st.write("Quick actions")
            if st.button("Bookmark this article", key="bm_detail"):
                bookmarks = st.session_state.get("bookmarks", [])
                if selected not in bookmarks:
                    bookmarks.append(selected)
                    st.session_state["bookmarks"] = bookmarks
                    st.success("Bookmarked ✅")
                else:
                    st.info("Already bookmarked")
            st.write("---")
            st.write("Article metadata")
            st.write(f"Author: {selected.get('author')}")
            st.write(f"Source: {selected.get('source', {}).get('name')}")
            st.write(f"Published: {format_datetime(selected.get('publishedAt'))}")

        st.markdown("---")
        st.write("Back to list")
        if st.button("Back to list", key="back_list"):
            st.session_state["selected_article"] = None

    # Show article list (only when not viewing detail)
    else:
        st.subheader(f"Showing {len(articles)} articles (page {page})")
        if not articles:
            st.warning("No articles to display.")
        # Pagination: display page_size articles per "page" (we already requested page_size but keep defensive)
        for idx, art in enumerate(articles, start=1 + (page - 1) * page_size):
            try:
                render_article_card(art, idx)
            except Exception as e:
                st.error(f"Error displaying article: {e}")

    # Footer / debug section
    st.markdown("---")
    st.write("Debug / meta")
    st.write(f"Category: **{category}** | Query: **{query or '—'}** | Page size: **{page_size}** | Page: **{page}**")
    st.caption("If the main area is blank: check console logs, and ensure code outside `with st.sidebar:` blocks is not indented into the sidebar.")

if __name__ == "__main__":
    main()
