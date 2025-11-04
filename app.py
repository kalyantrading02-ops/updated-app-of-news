with st.expander(f"🔹 {stock} ({len(visible)} Articles shown, scanned {len(scored_list)})", expanded=False):
    if visible:
        # iterate with index so we can build a unique key per article per-stock
        for idx, art in enumerate(visible[:10]):
            title = art["title"]
            url = art["url"]
            publisher = art["publisher"]
            published_date = art.get("raw", {}).get("published date") if isinstance(art.get("raw", {}), dict) else "N/A"
            score = art["score"]

            # priority icon (unchanged)
            if score >= 70:
                priority_label = "High"
                priority_icon = "🔺"
            elif score >= threshold:
                priority_label = "Medium"
                priority_icon = "🟨"
            else:
                priority_label = "Low"
                priority_icon = "🟩"

            reasons_txt = " • ".join(art["reasons"]) if art["reasons"] else "Signals detected"
            sentiment_label, sentiment_emoji, s_score = analyze_sentiment(title + " " + (art.get("desc") or ""))

            st.markdown(
                f"**[{title}]({url})**  {priority_icon} *{priority_label} ({score})*  🏢 *{publisher}* | 🗓️ *{published_date or 'N/A'}*"
            )
            st.markdown(f"*Reasons:* `{reasons_txt}`  •  *Sentiment:* {sentiment_emoji} {sentiment_label}")

            if show_snippet and art.get("desc"):
                snippet = art["desc"] if len(art["desc"]) < 220 else art["desc"][:217] + "..."
                st.markdown(f"> {snippet}")

            # ---- SAFE unique key for Save / Watch button ----
            # include stock (no spaces), index, and a short hash of url to guarantee uniqueness
            safe_stock = re.sub(r"\W+", "_", stock.lower())
            save_key = f"save_{safe_stock}_{idx}_{abs(hash(url))}"

            if st.button("💾 Save / Watch", key=save_key):
                found = next(
                    (x for x in st.session_state["saved_articles"] if x["url"] == url),
                    None,
                )
                if not found:
                    st.session_state["saved_articles"].append(
                        {
                            "title": title,
                            "url": url,
                            "stock": stock,
                            "date": published_date,
                            "score": score,
                        }
                    )
                    st.success("Saved to Watchlist")
                else:
                    st.info("Already in Watchlist")

            st.markdown("---")
    else:
        st.info("No market-impacting news found for this stock in the selected time period.")
