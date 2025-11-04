# app.py
articles = safe_get_articles(api_key=api_key, category=category, q=query, page_size=page_size, page=page, source=(source or None))


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


else:
st.subheader(f"Showing {len(articles)} articles (page {page})")
if not articles:
st.warning("No articles to display.")
for idx, art in enumerate(articles, start=1 + (page - 1) * page_size):
try:
render_article_card(art, idx)
except Exception as e:
st.error(f"Error displaying article: {e}")


# ----- TAB 1: TRENDING STOCKS -----
with tabs[1]:
st.header("Trending Stocks")
st.write("This section lists currently trending stocks. Replace SAMPLE_TRENDING with your real data source if available.")
for s in SAMPLE_TRENDING:
cols = st.columns([0.2, 0.6, 0.2])
with cols[0]:
st.subheader(s["symbol"])
with cols[1]:
st.write(s["name"])
with cols[2]:
st.write(f"{s['price']} ({s['change']})")


# ----- TAB 2: SENTIMENT -----
with tabs[2]:
st.header("Market Sentiment")
st.write("Overall market sentiment based on news & social signals (sample data).")
st.metric(label="Overall Sentiment", value=SAMPLE_SENTIMENT["overall"], delta=f"{SAMPLE_SENTIMENT['score']}")
st.write("Breakdown:")
st.write(SAMPLE_SENTIMENT["breakdown"])


# ----- TAB 3: UPCOMING EVENTS (moved to last tab) -----
with tabs[3]:
st.header("Upcoming Market-Moving Events")
st.write("This tab contains upcoming events that may move the market. It's intentionally placed as the LAST tab per your request.")
st.write("If you have a calendar or API for events, plug it in here. For now, sample events are shown.")
for ev in SAMPLE_EVENTS:
st.markdown("---")
st.subheader(ev["event"])
st.write(f"Date: {ev['date']} | Importance: {ev['importance']}")


# Footer / debug section (shown below tabs)
st.markdown("---")
st.write("Debug / meta")
st.write(f"Category: **{category}** | Query: **{query or '—'}** | Page size: **{page_size}** | Page: **{page}**")
st.caption("If the main area is blank: check console logs, and ensure code outside `with st.sidebar:` blocks is not indented into the sidebar.")




if __name__ == "__main__":
main()
