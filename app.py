# -----------------------------
# TAB 1 — NEWS (market-impacting filter + UI)  <-- REPLACE YOUR OLD NEWS BLOCK WITH THIS
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

    import re
    numeric_re = re.compile(NUMERIC_PATTERN, re.IGNORECASE)

    def has_numeric(text):
        return bool(numeric_re.search(text or ""))

    # scoring function (simple weighted sum + corroboration)
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

        # corroboration bonus: count distinct trusted publishers in corroboration_sources (if provided)
        corroboration_bonus = 0
        if corroboration_sources:
            trusted_count = sum(1 for s in set(corroboration_sources) if s and is_trusted(s))
            if trusted_count > 1:
                corroboration_bonus = min(WEIGHTS["max_corroboration_bonus"], 5 * (trusted_count - 1))
                if corroboration_bonus:
                    reasons.append("Corroboration")

        score = max(0, min(100, raw + corroboration_bonus))
        return int(score), reasons

    # Fetch news (same as before)
    with st.spinner("Fetching the latest financial news..."):
        news_results = fetch_all_news(fo_stocks[:10], start_date, today)

    # Build quick map of headline -> publisher list for corroboration
    headline_map = {}
    flat_articles = []  # keep flat list for display & scoring
    for res in news_results:
        stock = res["Stock"]
        for art in res.get("Articles", []):
            title = art.get("title") or ""
            desc = art.get("description") or art.get("snippet") or ""
            pub_field = art.get("publisher")
            publisher = ""
            if isinstance(pub_field, dict):
                publisher = pub_field.get("title") or ""
            elif isinstance(pub_field, str):
                publisher = pub_field
            else:
                publisher = art.get("source") or ""
            url = art.get("url") or art.get("link") or "#"
            # normalized headline key (short)
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

    # Score each article and decide display
    displayed_count = 0
    filtered_out_count = 0

    # We'll keep your original expander-per-stock UI, but filter articles inside each expander by score if only_impact is on
    for res in news_results:
        stock = res["Stock"]
        articles = res.get("Articles", []) or []
        # compute scored articles for this stock
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
                "reasons": reasons
            })

        # If only_impact is true, filter out low-score articles
        if only_impact:
            visible_articles = [s for s in scored_list if s["score"] >= threshold]
        else:
            visible_articles = scored_list

        # count filtered
        filtered_out_count += (len(scored_list) - len(visible_articles))
        displayed_count += len(visible_articles)

        # display same expander as before but only with visible articles inside
        with st.expander(f"🔹 {stock} ({len(visible_articles)} Articles shown, scanned {len(scored_list)})", expanded=False):
            if visible_articles:
                for art in visible_articles[:10]:
                    title = art["title"]
                    url = art["url"]
                    publisher = art["publisher"]
                    published_date = art.get("raw", {}).get("published date", "N/A") if isinstance(art.get("raw", {}), dict) else "N/A"
                    # But we don't want to change your existing simple markdown for links; keep that but add badges
                    # Compose reason chips and priority badge
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
                    # reason chips text
                    reasons_txt = " • ".join(art["reasons"]) if art["reasons"] else "Signals detected"
                    # sentiment from your existing analyzer function
                    sentiment, emot = analyze_sentiment(title + " " + (art["desc"] or ""))
                    # Render: headline link + publisher + date + priority + reasons + snippet
                    st.markdown(f"**[{title}]({url})**  {priority_color} *{priority} ({score})*  🏢 *{publisher}* | 🗓️ *{published_date}*")
                    st.markdown(f"*Reasons:* `{reasons_txt}`  •  *Sentiment:* {emot} {sentiment}")
                    if show_snippet and art.get("desc"):
                        snippet = art["desc"] if len(art["desc"]) < 220 else art["desc"][:217] + "..."
                        st.markdown(f"> {snippet}")
                    st.markdown("---")
            else:
                st.info("No market-impacting news found for this stock in the selected time period.")
    # end for stocks

    # Show aggregate summary (keeps UI consistent)
    total_scanned = sum(len(res.get("Articles", [])) for res in news_results)
    st.markdown(f"**Summary:** Displayed **{displayed_count}** articles • Filtered out **{filtered_out_count}** • Scanned **{total_scanned}**")
