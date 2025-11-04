import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from gnews import GNews
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from concurrent.futures import ThreadPoolExecutor, as_completed
import nltk
import time
import re

# -----------------------------
# INITIAL SETUP
# -----------------------------
nltk.download('vader_lexicon', quiet=True)
st.set_page_config(page_title="Stock News & Sentiment Dashboard", layout="wide")

# -----------------------------
# SIDEBAR — DARK MODE TOGGLE
# -----------------------------
st.sidebar.header("⚙️ Settings")
# keeping your original toggle
dark_mode = st.sidebar.toggle("🌗 Dark Mode", value=True, help="Switch instantly between Dark & Light Mode")

# -----------------------------
# APPLY THEMES
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

st.markdown(f"""
<style>
body {{
  background: {bg_gradient};
  color: {text_color};
}}
.stApp {{
  background: {bg_gradient} !important;
  color: {text_color} !important;
}}
h1, h2, h3, h4, h5 {{
  color: {accent_color} !important;
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
.news-card {{
  border-radius: 10px;
  padding: 12px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.12);
  transition: transform .12s ease, box-shadow .12s ease;
  background: rgba(255,255,255,0.02);
  margin-bottom: 12px;
}}
.news-card:hover {{ transform: translateY(-4px); box-shadow: 0 10px 30px rgba(0,0,0,0.16); }}
.headline {{ font-weight:600; font-size:16px; margin-bottom:6px; }}
.meta {{ font-size:12px; color: #9aa0a6; margin-bottom:8px; }}
.snip {{ font-size:13px; color: #dfe6ea; }}
.badge {{ display:inline-block; padding:4px 8px; border-radius:999px; font-size:12px; margin-right:6px; }}
.badge-source {{ background: rgba(255,255,255,0.04); color:inherit; }}
.badge-pos {{ background: rgba(0,200,83,0.12); color:#00C853; }}
.badge-neu {{ background: rgba(255,193,7,0.08); color:#FFC107; }}
.badge-neg {{ background: rgba(239,83,80,0.08); color:#EF5350; }}
.priority-high {{ background: rgba(239,83,80,0.12); color:#EF5350; padding:6px 10px; border-radius:8px; font-weight:600; }}
.priority-med {{ background: rgba(255,193,7,0.08); color:#FFC107; padding:6px 10px; border-radius:8px; font-weight:600; }}
.priority-low {{ background: rgba(128,128,128,0.06); color:#9aa0a6; padding:6px 10px; border-radius:8px; font-weight:600; }}
.reason-chip {{ display:inline-block; margin:3px 4px; padding:4px 8px; border-radius:999px; font-size:12px; background: rgba(255,255,255,0.03); }}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# APP TITLE
# -----------------------------
st.title("💹 Stock Market News & Sentiment Dashboard")

# -----------------------------
# AUTO REFRESH EVERY 10 MIN
# -----------------------------
refresh_interval = 600
if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = time.time()
elif time.time() - st.session_state["last_refresh"] > refresh_interval:
    st.session_state["last_refresh"] = time.time()
    # using st.rerun as in your running code
    try:
        st.rerun()
    except Exception:
        # fallback: try experimental_rerun silently
        try:
            st.experimental_rerun()
        except Exception:
            st.warning("Auto-refresh not supported in this Streamlit build; please refresh the page manually.")
            st.stop()

# -----------------------------
# SIDEBAR FILTERS
# -----------------------------
st.sidebar.header("📅 Filter Options")
time_period = st.sidebar.selectbox(
    "Select Time Period",
    ["Last Week", "Last Month", "Last 3 Months", "Last 6 Months"]
)

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
    "Reliance Industries", "TCS", "Infosys", "HDFC Bank", "ICICI Bank", "State Bank of India",
    "HCL Technologies", "Wipro", "Larsen & Toubro", "Tata Motors", "Bajaj Finance", "Axis Bank",
    "NTPC", "ITC", "Adani Enterprises", "Coal India", "Power Grid", "Maruti Suzuki",
    "Tech Mahindra", "Sun Pharma"
]

# -----------------------------
# PERFORMANCE BOOSTERS: fetch functions
# -----------------------------
@st.cache_data(ttl=600, show_spinner=False)
def fetch_news(stock, start, end):
    try:
        gnews = GNews(language='en', country='IN', max_results=10)
        try:
            gnews.start_date, gnews.end_date = start, end
        except Exception:
            pass
        return gnews.get_news(stock) or []
    except Exception:
        return []

@st.cache_data(ttl=600, show_spinner=False)
def fetch_all_news(stocks, start, end):
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_news, s, start, end): s for s in stocks}
        for future in as_completed(futures):
            stock = futures[future]
            try:
                articles = future.result() or []
                results.append({"Stock": stock, "Articles": articles, "News Count": len(articles)})
            except Exception:
                results.append({"Stock": stock, "Articles": [], "News Count": 0})
    return results

# sentiment analyzer (existing)
analyzer = SentimentIntensityAnalyzer()
def analyze_sentiment(text):
    if not text:
        text = ""
    score = analyzer.polarity_scores(text)["compound"]
    if score > 0.2:
        return "Positive", "🟢"
    elif score < -0.2:
        return "Negative", "🔴"
    else:
        return "Neutral", "🟡"

# -----------------------------
# MAIN TABS — ensure these are created BEFORE using them
# -----------------------------
news_tab, trending_tab, sentiment_tab = st.tabs([
    "📰 News", "🔥 Trending Stocks", "💬 Sentiment"
])

# -----------------------------
# TAB 1 — NEWS (market-impacting filter + UI)
# -----------------------------
with news_tab:
    st.header("🗞️ Latest Market News for F&O Stocks (Market-impacting only)")

    # Controls: show only market-impacting toggle + threshold slider + snippet toggle
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        only_impact = st.checkbox("🔎 Show only market-impacting news (score ≥ threshold)", value=True)
    with col2:
        threshold = st.slider("Minimum score to show", 0, 100, 40)
    with col3:
        show_snippet = st.checkbox("Show snippet", value=True)

    # --- scoring config (implements the 11 categories you gave) ---
    WEIGHTS = {
        "earnings_guidance": 30,
        "M&A_JV": 25,
        "management_change": 20,
        "buyback_dividend": 20,
        "contract_deal": 25,
        "block_insider": 25,
        "policy_regulation": 20,
        "analyst_move": 15,
        "numeric_mentioned": 10,
        "trusted_source": 15,
        "speculative_penalty": -15,
        "low_quality_penalty": -10,
        "max_corroboration_bonus": 20,
    }

    HIGH_PRIORITY_KEYWORDS = {
        "earnings": ["earnings", "quarter", "q1", "q2", "q3", "q4", "revenue", "profit", "loss", "guidance", "outlook", "beat", "miss", "results"],
        "MA": ["acquires", "acquisition", "merger", "demerger", "spin-off", "spin off", "joint venture", "jv"],
        "management": ["appoint", "resign", "ceo", "cfo", "chairman", "board", "director", "promoter", "coo", "md"],
        "corp_action": ["buyback", "dividend", "split", "bonus issue", "bonus", "rights issue", "rights", "share pledge", "pledge"],
        "contract": ["contract", "order", "tender", "deal", "agreement", "licence", "license", "wins order"],
        "regulatory": ["sebi", "investigation", "fraud", "lawsuit", "penalty", "fine", "regulation", "ban", "policy", "pli", "subsidy", "tariff"],
        "analyst": ["upgrade", "downgrade", "target", "recommendation", "brokerage", "analyst"],
        "block": ["block deal", "bulk deal", "blocktrade", "block-trade", "insider", "promoter buy", "promoter selling", "promoter sell"],
    }

    TRUSTED_SOURCES = {"reuters", "bloomberg", "economic times", "economictimes", "livemint", "mint", "business standard", "business-standard", "cnbc", "ft", "financial times", "press release", "nse", "bse"}
    LOW_QUALITY_SOURCES = {"blog", "medium", "wordpress", "forum", "reddit", "quora"}
    SPECULATIVE_WORDS = ["may", "might", "could", "rumour", "rumor", "reportedly", "alleged", "possible", "speculat"]
    NUMERIC_PATTERN = r'[%₹$£€]|(?:\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b\s*(?:crore|lakh|billion|bn|mn|m|₹|rs\.|rs|rupee|ton|tons|mw|MW|GW))'

    def norm_text(s):
        return (s or "").strip().lower()

    def contains_any(text, keywords):
        t = norm_text(text)
        return any(k in t for k in keywords)

    def is_trusted(publisher):
        if not publisher: return False
        p = norm_text(publisher)
        return any(ts in p for ts in TRUSTED_SOURCES)

    def is_low_quality(publisher):
        if not publisher: return False
        p = norm_text(publisher)
        return any(lq in p for lq in LOW_QUALITY_SOURCES)

    numeric_re = re.compile(NUMERIC_PATTERN, re.IGNORECASE)
    def has_numeric(text):
        return bool(numeric_re.search(text or ""))

    def score_article(title, desc, publisher, corroboration_sources=None):
        raw = 0
        reasons = []
        txt = f"{title} {desc}".lower()

        if contains_any(txt, HIGH_PRIORITY_KEYWORDS["earnings"]):
            raw += WEIGHTS["earnings_guidance"]; reasons.append("Earnings/Guidance")
        if contains_any(txt, HIGH_PRIORITY_KEYWORDS["MA"]):
            raw += WEIGHTS["M&A_JV"]; reasons.append("M&A/JV")
        if contains_any(txt, HIGH_PRIORITY_KEYWORDS["management"]):
            raw += WEIGHTS["management_change"]; reasons.append("Management/Govt")
        if contains_any(txt, HIGH_PRIORITY_KEYWORDS["corp_action"]):
            raw += WEIGHTS["buyback_dividend"]; reasons.append("Corporate Action")
        if contains_any(txt, HIGH_PRIORITY_KEYWORDS["contract"]):
            raw += WEIGHTS["contract_deal"]; reasons.append("Contract/Order")
        if contains_any(txt, HIGH_PRIORITY_KEYWORDS["regulatory"]):
            raw += WEIGHTS["policy_regulation"]; reasons.append("Regulatory/Policy")
        if contains_any(txt, HIGH_PRIORITY_KEYWORDS["analyst"]):
            raw += WEIGHTS["analyst_move"]; reasons.append("Broker/Analyst Move")
        if contains_any(txt, HIGH_PRIORITY_KEYWORDS["block"]):
            raw += WEIGHTS["block_insider"]; reasons.append("Block/Insider Deal")

        if has_numeric(txt):
            raw += WEIGHTS["numeric_mentioned"]; reasons.append("Numeric Mention")

        if is_trusted(publisher):
            raw += WEIGHTS["trusted_source"]; reasons.append("Trusted Source")

        if is_low_quality(publisher):
            raw += WEIGHTS["low_quality_penalty"]; reasons.append("Low-quality Source (penalized)")

        if contains_any(txt, SPECULATIVE_WORDS):
            raw += WEIGHTS["speculative_penalty"]; reasons.append("Speculative Language (penalized)")

        corroboration_bonus = 0
        if corroboration_sources:
            trusted_count = sum(1 for s in set(corroboration_sources) if s and is_trusted(s))
            if trusted_count > 1:
                corroboration_bonus = min(WEIGHTS["max_corroboration_bonus"], 5 * (trusted_count - 1))
                if corroboration_bonus:
                    reasons.append("Corroboration")

        score = max(0, min(100, raw + corroboration_bonus))
        return int(score), reasons

    # Fetch news for top 10 F&O stocks
    with st.spinner("Fetching the latest financial news..."):
        news_results = fetch_all_news(fo_stocks[:10], start_date, today)

    # Build map headline->publishers for corroboration
    headline_map = {}
    flat_articles = []
    for res in news_results:
        stock = res["Stock"]
        for art in res.get("Articles", []):
            title = art.get("title") or ""
            desc = art.get("description") or art.get("snippet") or ""
            pub_field = art.get("publisher")
            if isinstance(pub_field, dict):
                publisher = pub_field.get("title") or ""
            elif isinstance(pub_field, str):
                publisher = pub_field
            else:
                publisher = art.get("source") or ""
            url = art.get("url") or art.get("link") or "#"
            norm_head = re.sub(r'\W+', ' ', title.lower()).strip()
            key = norm_head[:120] if norm_head else stock.lower() + "_" + title[:40]
            headline_map.setdefault(key, []).append(publisher or "unknown")
            flat_articles.append({
                "stock": stock,
                "title": title,
                "desc": desc,
                "publisher": publisher,
                "url": url,
                "key": key,
                "raw": art
            })

    # Score and display — keep your expander style per stock
    displayed_count = 0
    filtered_out_count = 0

    for res in news_results:
        stock = res["Stock"]
        articles = res.get("Articles", []) or []
        scored_list = []
        for art in articles:
            title = art.get("title") or ""
            desc = art.get("description") or art.get("snippet") or ""
            pub_field = art.get("publisher")
            if isinstance(pub_field, dict):
                publisher = pub_field.get("title") or ""
            elif isinstance(pub_field, str):
                publisher = pub_field
            else:
                publisher = art.get("source") or ""
            url = art.get("url") or art.get("link") or "#"
            norm_head = re.sub(r'\W+', ' ', title.lower()).strip()
            key = norm_head[:120] if norm_head else stock.lower() + "_" + title[:40]
            publishers_for_head = headline_map.get(key, [])
            score, reasons = score_article(title, desc, publisher, corroboration_sources=publishers_for_head)
            scored_list.append({
                "title": title,
                "desc": desc,
                "publisher": publisher or "Unknown Source",
                "url": url,
                "score": score,
                "reasons": reasons,
                "raw": art
            })

        if only_impact:
            visible_articles = [s for s in scored_list if s["score"] >= threshold]
        else:
            visible_articles = scored_list

        filtered_out_count += (len(scored_list) - len(visible_articles))
        displayed_count += len(visible_articles)

        with st.expander(f"🔹 {stock} ({len(visible_articles)} Articles shown, scanned {len(scored_list)})", expanded=False):
            if visible_articles:
                for art in visible_articles[:10]:
                    title = art["title"]
                    url = art["url"]
                    publisher = art["publisher"]
                    pub_raw = art.get("raw", {})
                    published_date = pub_raw.get("published date") if isinstance(pub_raw, dict) else "N/A"
                    score = art["score"]
                    if score >= 70:
                        priority = "High"
                        priority_color = "🔴"
                    elif score >= threshold:
                        priority = "Medium"
                        priority_color = "🟠"
                    else:
                        priority = "Low"
                        priority_color = "⚪"
                    reasons_txt = " • ".join(art["reasons"]) if art["reasons"] else "Signals detected"
                    sentiment_label, emot = analyze_sentiment(title + " " + (art["desc"] or ""))
                    st.markdown(f"**[{title}]({url})**  {priority_color} *{priority} ({score})*  🏢 *{publisher}* | 🗓️ *{published_date or 'N/A'}*")
                    st.markdown(f"*Reasons:* `{reasons_txt}`  •  *Sentiment:* {emot} {sentiment_label}")
                    if show_snippet and art.get("desc"):
                        snippet = art["desc"] if len(art["desc"]) < 220 else art["desc"][:217] + "..."
                        st.markdown(f"> {snippet}")
                    st.markdown("---")
            else:
                st.info("No market-impacting news found for this stock in the selected time period.")

    total_scanned = sum(len(res.get("Articles", [])) for res in news_results)
    st.markdown(f"**Summary:** Displayed **{displayed_count}** articles • Filtered out **{filtered_out_count}** • Scanned **{total_scanned}**")

# -----------------------------
# TAB 2 — TRENDING STOCKS (unchanged)
# -----------------------------
with trending_tab:
    st.header("🔥 Trending F&O Stocks by News Mentions")
    with st.spinner("Analyzing trends..."):
        all_results = fetch_all_news(fo_stocks, start_date, today)
        counts = [{"Stock": r["Stock"], "News Count": r.get("News Count", len(r.get("Articles", [])))} for r in all_results]
        df_counts = pd.DataFrame(counts).sort_values("News Count", ascending=False)
        fig = px.bar(df_counts, x="Stock", y="News Count", color="News Count",
                     color_continuous_scale="Turbo", title=f"Trending F&O Stocks ({time_period})",
                     template=plot_theme)
        st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# TAB 3 — SENTIMENT (unchanged)
# -----------------------------
with sentiment_tab:
    st.header("💬 Sentiment Analysis")
    with st.spinner("Analyzing sentiment..."):
        sentiment_data = []
        all_results = fetch_all_news(fo_stocks[:10], start_date, today)
        for res in all_results:
            stock = res["Stock"]
            for art in res["Articles"][:3]:
                sentiment, emoji = analyze_sentiment(art.get("title") or "")
                sentiment_data.append({
                    "Stock": stock,
                    "Headline": art.get("title") or "",
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
# FOOTER
# -----------------------------
st.markdown("---")
st.caption(f"📊 Data Source: Google News | Mode: {'Dark' if dark_mode else 'Light'} | Auto-refresh every 10 min | Built with ❤️ using Streamlit & Plotly")
