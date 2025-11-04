# stock_news_sentiment_dashboard_marketimpact.py
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
# use checkbox (toggle may not exist on some Streamlit versions)
dark_mode = st.sidebar.checkbox("🌗 Dark Mode", value=True, help="Switch instantly between Dark & Light Mode")

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
.save-btn {{ float:right; }}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# APP TITLE
# -----------------------------
st.title("💹 Stock Market News & Sentiment Dashboard")

# -----------------------------
# AUTO REFRESH EVERY 10 MIN (robust)
# -----------------------------
refresh_interval = 600  # 10 minutes

if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = time.time()
else:
    if time.time() - st.session_state["last_refresh"] > refresh_interval:
        st.session_state["last_refresh"] = time.time()
        # Try rerun APIs safely
        try:
            # Preferred for many recent Streamlit builds
            st.experimental_rerun()
        except Exception:
            try:
                # Works on some older builds
                st.rerun()
            except Exception:
                # Graceful fallback
                st.warning(
                    "Auto-refresh isn’t available in this Streamlit version. "
                    "Please refresh the page manually to update data."
                )
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
# PERFORMANCE BOOSTERS: fetch functions (same as your app)
# -----------------------------
@st.cache_data(ttl=600, show_spinner=False)
def fetch_news(stock, start, end):
    try:
        gnews = GNews(language='en', country='IN', max_results=12)
        # best-effort: set date range where supported
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
                articles = future.result()
                results.append({"Stock": stock, "Articles": articles, "News Count": len(articles)})
            except Exception:
                results.append({"Stock": stock, "Articles": [], "News Count": 0})
    return results

analyzer = SentimentIntensityAnalyzer()

def analyze_sentiment(text):
    score = analyzer.polarity_scores(text)["compound"]
    if score > 0.2:
        return "Positive", "🟢", score
    elif score < -0.2:
        return "Negative", "🔴", score
    else:
        return "Neutral", "🟡", score

# -----------------------------
# Market-impact scoring engine (weights per your blueprint)
# -----------------------------
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
    "max_corroboration_bonus": 20  # applied after raw sum
}

TRUSTED_SOURCES = {"reuters", "bloomberg", "times of india", "economic times", "economictimes", "livemint", "mint", "business standard", "business-standard", "cnbc", "ft", "financial times", "thestreet", "press release", "nse", "bse"}

HIGH_PRIORITY_KEYWORDS = {
    "earnings": ["earnings", "quarter", "q1", "q2", "q3", "q4", "revenue", "profit", "loss", "guidance", "outlook", "beat", "miss", "results"],
    "MA": ["acquires", "acquisition", "merger", "demerger", "spin-off", "spin off", "joint venture", "joint-venture", "jv"],
    "management": ["appoint", "resign", "CEO", "CFO", "chairman", "board", "director", "promoter", "coo", "md"],
    "corp_action": ["buyback", "dividend", "split", "bonus issue", "bonus", "rights issue", "rights", "share pledge", "pledge"],
    "contract": ["contract", "order", "tender", "deal", "agreement", "licence", "license", "wins order"],
    "regulatory": ["sebi", "investigation", "fraud", "lawsuit", "penalty", "fine", "regulation", "ban", "policy", "pli", "subsidy", "tariff"],
    "analyst": ["upgrade", "downgrade", "target", "recommendation", "brokerage", "analyst"],
    "block": ["block deal", "bulk deal", "blocktrade", "block-trade", "insider", "promoter buy", "promoter selling", "promoter sell"]
}

SPECULATIVE_WORDS = ["may", "might", "could", "rumour", "rumor", "reportedly", "alleged", "possible", "speculat"]

NUMERIC_PATTERNS = re.compile(r'[%₹$£€]|(?:\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b\s*(?:crore|lakh|billion|bn|mn|m|₹|rs\.|rs|rs|rupee|ton|tons|mw|MW|GW))', re.IGNORECASE)

LOW_QUALITY_SOURCES = {"blog", "medium", "wordpress", "forum", "reddit", "quora"}

# helper: normalize string
def norm(s):
    return (s or "").strip().lower()

def contains_any(text, keywords):
    t = norm(text)
    return any(k.lower() in t for k in keywords)

def is_trusted_source(pub):
    if not pub: return False
    p = norm(pub)
    for t in TRUSTED_SOURCES:
        if t in p:
            return True
    return False

def is_low_quality_source(pub):
    if not pub: return False
    p = norm(pub)
    return any(k in p for k in LOW_QUALITY_SOURCES)

def contains_numeric(text):
    if not text: return False
    return bool(NUMERIC_PATTERNS.search(text))

def parse_published_date(art):
    # try a few common fields and formats; if fails, return None
    candidates = [art.get("published date"), art.get("publishedDate"), art.get("published_date"), art.get("published"), art.get("publishedAt"), art.get("timestamp")]
    for c in candidates:
        if not c:
            continue
        # if already a datetime
        if isinstance(c, datetime):
            return c
        try:
            # try ISO parse
            return datetime.fromisoformat(c)
        except Exception:
            # try common formats
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(c, fmt)
                except Exception:
                    continue
    return None

def score_article(title, desc, publisher, matched_sources_with_times=None):
    """
    Returns (score:int, reasons:list[str], is_official:bool)
    matched_sources_with_times: an optional dict of {source_name: datetime} collected for corroboration step
    """
    raw = 0
    reasons = []
    text = f"{title} {desc}".lower()

    # Major keywords
    if contains_any(text, HIGH_PRIORITY_KEYWORDS["earnings"]):
        raw += WEIGHTS["earnings_guidance"]; reasons.append("Earnings/Guidance")
    if contains_any(text, HIGH_PRIORITY_KEYWORDS["MA"]):
        raw += WEIGHTS["M&A_JV"]; reasons.append("M&A/JV")
    if contains_any(text, HIGH_PRIORITY_KEYWORDS["management"]):
        raw += WEIGHTS["management_change"]; reasons.append("Management/Govt")
    if contains_any(text, HIGH_PRIORITY_KEYWORDS["corp_action"]):
        raw += WEIGHTS["buyback_dividend"]; reasons.append("Corporate Action")
    if contains_any(text, HIGH_PRIORITY_KEYWORDS["contract"]):
        raw += WEIGHTS["contract_deal"]; reasons.append("Contract/Order")
    if contains_any(text, HIGH_PRIORITY_KEYWORDS["regulatory"]):
        raw += WEIGHTS["policy_regulation"]; reasons.append("Regulatory/Policy")
    if contains_any(text, HIGH_PRIORITY_KEYWORDS["analyst"]):
        raw += WEIGHTS["analyst_move"]; reasons.append("Broker/Analyst Move")
    if contains_any(text, HIGH_PRIORITY_KEYWORDS["block"]):
        raw += WEIGHTS["block_insider"]; reasons.append("Block/Insider Deal")

    # Numeric
    if contains_numeric(text):
        raw += WEIGHTS["numeric_mentioned"]; reasons.append("Numeric Mention")

    # Source trustworthiness
    is_trusted = is_trusted_source(publisher)
    if is_trusted:
        raw += WEIGHTS["trusted_source"]; reasons.append("Trusted Source")

    # Low-quality source penalty
    if is_low_quality_source(publisher):
        raw += WEIGHTS["low_quality_penalty"]; reasons.append("Low-quality Source (penalized)")

    # Speculative penalty
    if contains_any(text, SPECULATIVE_WORDS):
        raw += WEIGHTS["speculative_penalty"]; reasons.append("Speculative Language (penalized)")

    # Corroboration: if matched_sources_with_times is provided, count additional trusted sources within 60 minutes
    corroboration_bonus = 0
    if matched_sources_with_times:
        # matched_sources_with_times is dict source->datetime
        t0 = None
        # pick earliest time in dict if any
        times = [ts for ts in matched_sources_with_times.values() if ts]
        if times:
            t0 = min(times)
        # count unique additional trusted sources (exclude current publisher if present)
        trusted_count = 0
        for src, ts in matched_sources_with_times.items():
            if src and is_trusted_source(src):
                # consider within +/- 60 minutes of t0
                if t0 and ts and abs((ts - t0).total_seconds()) <= 3600:
                    trusted_count += 1
        # bonus = min(max, 5 * (trusted_count-1))
        if trusted_count > 1:
            corroboration_bonus = min(WEIGHTS["max_corroboration_bonus"], 5 * (trusted_count - 1))

    score = int(max(0, min(100, raw + corroboration_bonus)))
    # if article looks like an official press release or exchange filing
    is_official = False
    if publisher and ("press" in publisher.lower() or "press release" in publisher.lower() or "nse" in publisher.lower() or "bse" in publisher.lower() or "company" in publisher.lower()):
        is_official = True

    return score, reasons, is_official

# -----------------------------
# STORE saved/watchlist in session state
# -----------------------------
if "saved_articles" not in st.session_state:
    st.session_state["saved_articles"] = []  # list of dicts {title,url,stock,date,score}

# -----------------------------
# MAIN TABS (Compare removed earlier)
# -----------------------------
news_tab, trending_tab, sentiment_tab = st.tabs([
    "📰 News", "🔥 Trending Stocks", "💬 Sentiment"
])

# -----------------------------
# NEW — TAB 1: NEWS (market-impacting filter + UI)
# -----------------------------
with news_tab:
    st.header("🗞️ Market-Impacting News — Filtered & Ranked")

    # Controls: toggle to show only market-impacting news, threshold slider
    colA, colB, colC = st.columns([2, 1, 1])
    with colA:
        only_impact = st.checkbox("🔎 Show only market-impacting news (score ≥ threshold)", value=True)
    with colB:
        threshold = st.slider("Minimum score to show", 0, 100, 40)
    with colC:
        show_snippet = st.checkbox("Show snippet", value=True)

    # fetch the top N stocks' news (same behavior as before)
    with st.spinner("Fetching latest financial news..."):
        news_results = fetch_all_news(fo_stocks[:12], start_date, today)

    # Flatten articles & collect source/time map for corroboration grouping
    flat = []
    # Build a mapping key -> {source: time} for corroboration: use normalized headline (short)
    corroboration_map = {}  # key: normalized headline -> dict(source->time)
    for r in news_results:
        stock = r.get("Stock", "Unknown")
        for art in r.get("Articles", []):
            title = art.get("title") or ""
            desc = art.get("description") or art.get("snippet") or ""
            publisher = ""
            pub_field = art.get("publisher")
            if isinstance(pub_field, dict):
                publisher = pub_field.get("title") or ""
            elif isinstance(pub_field, str):
                publisher = pub_field
            else:
                publisher = art.get("source") or ""
            url = art.get("url") or art.get("link") or "#"
            date = parse_published_date(art) or art.get("time") or art.get("published")
            # normalize heading for grouping (short)
            norm_head = re.sub(r'\W+', ' ', (title or "").lower()).strip()
            key = norm_head[:120] if norm_head else (stock.lower() + "_" + title[:40])
            # update corroboration_map
            corroboration_map.setdefault(key, {})
            try:
                if isinstance(date, datetime):
                    corroboration_map[key][publisher or "unknown"] = date
                else:
                    corroboration_map[key][publisher or "unknown"] = datetime.now()
            except Exception:
                corroboration_map[key][publisher or "unknown"] = datetime.now()
            flat.append({
                "stock": stock,
                "title": title,
                "desc": desc,
                "publisher": publisher,
                "url": url,
                "date": date,
                "key": key,
                "raw_article": art
            })

    # Score each article using corroboration map
    scored = []
    for art in flat:
        key = art["key"]
        publisher = art["publisher"]
        score, reasons, is_official = score_article(art["title"], art["desc"], publisher, matched_sources_with_times=corroboration_map.get(key))
        # sentiment (for extra info)
        sentiment_label, sentiment_emoji, sentiment_score = analyze_sentiment(f"{art['title']}. {art['desc']}")
        # Determine priority label
        if score >= 70:
            priority = ("High", "priority-high")
        elif score >= threshold:
            priority = ("Medium", "priority-med")
        else:
            priority = ("Low", "priority-low")
        # market timing flag: Pre-market / In-market / After-market
        market_flag = "N/A"
        try:
            if isinstance(art["date"], datetime):
                # Market hours approx (India): 09:15 - 15:30
                hr = art["date"].hour
                if 9 <= hr < 15:  # rough
                    market_flag = "In-market"
                else:
                    market_flag = "Pre/After-market"
            else:
                market_flag = "N/A"
        except Exception:
            market_flag = "N/A"
        scored.append({
            **art,
            "score": score,
            "reasons": reasons,
            "is_official": is_official,
            "sentiment": sentiment_label,
            "sentiment_emoji": sentiment_emoji,
            "sentiment_score": sentiment_score,
            "priority": priority,
            "market_flag": market_flag
        })

    # Optionally filter to show only impact >= threshold
    displayed = []
    filtered_out_count = 0
    for a in scored:
        if only_impact:
            if a["score"] >= threshold:
                displayed.append(a)
            else:
                filtered_out_count += 1
        else:
            displayed.append(a)

    # Sort displayed by score desc
    displayed = sorted(displayed, key=lambda x: x["score"], reverse=True)

    # Aggregate counts
    high_ct = sum(1 for a in displayed if a["score"] >= 70)
    med_ct = sum(1 for a in displayed if threshold <= a["score"] < 70)
    low_ct = sum(1 for a in displayed if a["score"] < threshold)
    total_possible = len(scored)

    st.markdown(f"**Aggregates:** High: **{high_ct}** | Medium (≥ {threshold}): **{med_ct}** | Filtered out: **{filtered_out_count}** | Total scanned: **{total_possible}**")

    # Render results in a 3-column card grid (responsive-ish)
    cols_per_row = 3
    rows = [displayed[i:i+cols_per_row] for i in range(0, len(displayed), cols_per_row)]

    if not displayed:
        st.info("No market-impacting news found for the selected timeframe and threshold.")
    else:
        for row in rows:
            cols = st.columns(len(row))
            for c, art in zip(cols, row):
                with c:
                    # Card container
                    st.markdown('<div class="news-card">', unsafe_allow_html=True)
                    # priority badge top-right with score
                    priority_label, priority_class = art["priority"]
                    st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                                f'<div style="font-size:12px;color:#9aa0a6">{art["stock"]} • {art["market_flag"]}</div>'
                                f'<div class="{priority_class}">{priority_label} • {art["score"]}</div>'
                                f'</div>', unsafe_allow_html=True)
                    # headline
                    st.markdown(f'<div class="headline"><a href="{art["url"]}" target="_blank" style="color:inherit;text-decoration:none">{art["title"]}</a></div>', unsafe_allow_html=True)
                    # meta: publisher, sentiment chip, date
                    pub = art["publisher"] or "Unknown"
                    date_str = art["date"].isoformat() if isinstance(art["date"], datetime) else str(art["date"])
                    # reason chips
                    chips = ""
                    for r in art["reasons"][:4]:
                        chips += f'<span class="reason-chip">{r}</span>'
                    # official badge
                    official_html = ""
                    if art["is_official"]:
                        official_html = '<span class="badge badge-source">Official / Filing</span>'
                    sentiment_badge_cls = "badge-neu"
                    if art["sentiment"] == "Positive":
                        sentiment_badge_cls = "badge-pos"
                    elif art["sentiment"] == "Negative":
                        sentiment_badge_cls = "badge-neg"
                    st.markdown(f'<div class="meta">{official_html} <span class="badge badge-source">{pub}</span> <span class="{sentiment_badge_cls}">{art["sentiment_emoji"]} {art["sentiment"]}</span> <span style="float:right;color:#9aa0a6">{date_str}</span></div>', unsafe_allow_html=True)
                    # reason chips
                    st.markdown(chips, unsafe_allow_html=True)
                    # snippet
                    if show_snippet and art.get("desc"):
                        trimmed = art["desc"] if len(art["desc"]) < 220 else art["desc"][:217] + "..."
                        st.markdown(f'<div class="snip">{trimmed}</div>', unsafe_allow_html=True)
                    # Why this matters tooltip / short explanation (join reasons)
                    why = "This article is flagged because: " + (", ".join(art["reasons"]) if art["reasons"] else "multiple signals detected")
                    st.markdown(f'<div style="margin-top:8px;"><small title="{why}">ℹ️ Why this matters</small></div>', unsafe_allow_html=True)
                    
                    # --- Save / Watch button (fixed) ---
save_key = f"save_{abs(hash(art['title'] + art['url']))}"

# Directly create the button; don't pre-assign this key in session_state
if st.button("💾 Save / Watch", key=save_key):
    found = next((x for x in st.session_state["saved_articles"] if x["url"] == art["url"]), None)
    if not found:
        st.session_state["saved_articles"].append({
            "title": art["title"],
            "url": art["url"],
            "stock": art["stock"],
            "date": art["date"],
            "score": art["score"]
        })
        st.success("Saved to Watchlist")
    else:
        st.info("Already in Watchlist")
                    # End card
                    st.markdown('</div>', unsafe_allow_html=True)

    # Small Watchlist preview at bottom of News tab
    st.markdown("---")
    st.subheader("👀 Watchlist (Saved Articles)")
    if st.session_state["saved_articles"]:
        df_watch = pd.DataFrame(st.session_state["saved_articles"])[["stock", "title", "score", "date", "url"]]
        # show as table with clickable links (simple)
        def make_clickable(val):
            return f'<a href="{val}" target="_blank">Open</a>'
        df_watch = df_watch.rename(columns={"title": "headline", "score": "score (out of 100)"})
        st.dataframe(df_watch, use_container_width=True)
    else:
        st.info("No saved articles yet — click 💾 Save / Watch on any article card.")

# -----------------------------
# TAB 2 — TRENDING STOCKS (unchanged)
# -----------------------------
with trending_tab:
    st.header("🔥 Trending F&O Stocks by News Mentions")
    with st.spinner("Analyzing trends..."):
        all_results = fetch_all_news(fo_stocks, start_date, today)
        counts = [{"Stock": r["Stock"], "News Count": r.get("News Count", len(r["Articles"]))} for r in all_results]
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
                title = art.get("title") or ""
                desc = art.get("description") or ""
                combined = f"{title}. {desc}"
                sentiment_label, emoji, s_score = analyze_sentiment(combined)
                sentiment_data.append(
                    {"Stock": stock, "Headline": title, "Sentiment": sentiment_label, "Emoji": emoji, "Score": s_score}
                )
        if sentiment_data:
            sentiment_df = pd.DataFrame(sentiment_data).sort_values(by=["Stock", "Score"], ascending=[True, False])
            st.dataframe(sentiment_df, use_container_width=True)
            csv_bytes = sentiment_df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download Sentiment Data", csv_bytes, "sentiment_data.csv", "text/csv")
        else:
            st.warning("No sentiment data found for the selected timeframe.")

# -----------------------------
# FOOTER
# -----------------------------
st.markdown("---")
st.caption(f"📊 Data Source: Google News | Mode: {'Dark' if dark_mode else 'Light'} | Auto-refresh every 10 min | Built with ❤️ using Streamlit & Plotly")
