# app.py
import streamlit as st
from datetime import datetime
import requests

# --- SETTINGS ----
st.set_page_config(page_title="News Dashboard", layout="wide", page_icon="🗞️")
DEFAULT_PAGE_SIZE = 6

# ---------- SAMPLE FALLBACK DATA ----------
SAMPLE_ARTICLES = [
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

# ---------- HELPERS ----------
def format_datetime(dt_str):
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        return dt_str


@st.cache_data(ttl=300)
def fetch_news(api_key, category="general", q="", page_size=10, page=1, source=None):
    """Fetch news from NewsAPI.org"""
    if not api_key:
        raise ValueError("No API key provided.")
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": api_key,
        "category": category if category and category != "all" else None,
        "q": q or None,
        "pageSize": page_size,
        "page": page,
        "country": "in",
    }
    if source:
        params["sources"] = source
    params = {k: v for k, v in params.items() if v is not None}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def safe_get_articles(api_key, **kwargs):
    """Fetch news or fallback"""
    try:
        data = fetch_news(api_key, **kwargs)
        articles = data.get("articles", [])
        if not articles:
            st.warning("No articles found — showing sample data.")
            return SAMPLE_ARTICLES
        return articles
    except Exception as e:
        st.error(f"Error fetching news: {e}")
        st.info("Showing fallback data.")
        return SAMPLE_ARTICLES


def render_article_card(article, idx):
    """Render a single article card"""
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
                pass
        st.markdown(f"### {title}")
        st.caption(f"{source_name} — {published}")
        st.write(desc)
        col3 = st.columns([1, 1, 1])
        with col3[0]:
            if st.button("Open article", key=f"open_{idx}"):
                st.write(f"[Read original]({url})")
        with col3[1]:
            if st.button("Read more", key=f"read_{idx}"):
                st.session_state["selected_article"] = article
        with col3[2]:
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
    if "bookmarks" not in st.session_state:
        st.session_state["bookmarks"] = []
    if "selected_article" not in st.session_state:
        st.session_state["selected_article"] = None
    if "last_refresh" not in st.session_state:
        st.session_state["last_refresh"] = None

    # --- SIDEBAR ---
    with st.sidebar:
        st.title("🗞️ Controls")
        api_key = st.text_input("API Key (optional)", value="", help="Leave empty for sample news.")
        category = st.selectbox(
            "Category", ["all", "business", "entertainment", "general", "health", "science", "sports", "technology"], index=3
        )
        source = st.text_input("Source (optional)", value="", help="Example: bbc-news")
        query = st.text_input("Search query", value="")
        page_size = st.number_input("Articles per page", min_value=1, max_value=20, value=DEFAULT_PAGE_SIZE)
        page = st.number_input("Page", min_value=1, value=1)

        if st.button("Refresh"):
            st.cache_data.clear()
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

    # --- MAIN CONTENT ---
    st.title("📰 News Dashboard")
    st.write("Browse the latest news and headlines below.")

    articles = safe_get_articles(api_key, category=category, q=query, page_size=page_size, page=page, source=(source or None))

    if st.session_state["selected_article"]:
        article = st.session_state["selected_article"]
        st.subheader(article.get("title"))
        if article.get("urlToImage"):
            st.image(article["urlToImage"], width=700)
        st.caption(f"{article['source']['name']} — {format_datetime(article['publishedAt'])}")
        st.write(article.get("content") or article.get("description"))
        st.markdown(f"[Read more here]({article['url']})")
        if st.button("Back to list"):
            st.session_state["selected_article"] = None
    else:
        st.subheader(f"Showing {len(articles)} articles (page {page})")
        for idx, art in enumerate(articles, start=1):
            render_article_card(art, idx)

    st.markdown("---")
    st.write("Debug Info:")
    st.write(f"Category: {category}, Query: {query or '-'}, Page Size: {page_size}, Page: {page}")


if __name__ == "__main__":
    main()
