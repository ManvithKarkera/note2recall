"""note2recall — Streamlit frontend.  Run with:  streamlit run app.py"""

import random

import streamlit as st

from smartnotes.pipeline import build_deck, deck_to_dict

st.set_page_config(page_title="note2recall", page_icon="🗂️", layout="wide")

ss = st.session_state
ss.setdefault("deck", None)
ss.setdefault("idx", 0)
ss.setdefault("flipped", False)
ss.setdefault("results", {})      # card index -> "known" | "again"


@st.cache_data(show_spinner=False)
def cached_deck(data: bytes, name: str, n_cards: int, threshold: float):
    return deck_to_dict(build_deck(data, n_cards=n_cards, dup_threshold=threshold))


# ------------------------------------------------------------------- upload
st.title("🗂️ note2recall")
st.caption("From notes to active recall: upload study notes and get flashcards grounded in them.")

with st.container(border=True):
    up_col, opt_col = st.columns([3, 2])
    with up_col:
        upload = st.file_uploader("Upload study notes (PDF or TXT)", type=["pdf", "txt"])
    with opt_col:
        n_cards = st.slider("Number of cards", 5, 40, 15)
        threshold = st.slider("Duplicate similarity threshold", 0.5, 0.95, 0.80, 0.05,
                              help="Cards whose source sentences are more similar than this are merged.")
    if st.button("Generate deck", type="primary", disabled=upload is None, width="stretch"):
        with st.spinner("Running NLP pipeline… (the first run loads the models and takes up to a minute)"):
            try:
                ss.deck = cached_deck(upload.getvalue(), upload.name, n_cards, threshold)
                ss.idx, ss.flipped, ss.results = 0, False, {}
            except ValueError as e:
                st.error(str(e))

deck = ss.deck
if deck is None:
    st.info("note2recall extracts key concepts, ranks the most informative sentences, turns them into "
            "flashcards, removes duplicates, and shows which concepts the deck misses.")
    st.stop()

cards = deck["cards"]
stats = deck["stats"]
cov = deck["coverage"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Cards", stats["cards"])
c2.metric("Sentences analysed", stats["sentences"])
c3.metric("Duplicates removed", len(deck["duplicates"]))
c4.metric("Concept coverage", f"{cov['ratio']:.0%}")

review, browse, quiz, analysis = st.tabs(["Review", "All cards", "Quiz", "Coverage & analysis"])

# ------------------------------------------------------------------- review
with review:
    if not cards:
        st.warning("No cards could be generated from this document.")
    else:
        card = cards[ss.idx]
        st.progress((ss.idx + 1) / len(cards), text=f"Card {ss.idx + 1} of {len(cards)}")
        with st.container(border=True):
            st.caption(f"{card['kind'].upper()} · page {card['page']}")
            st.markdown(f"### {card['question']}")
            if ss.flipped:
                st.success(f"**{card['answer']}**")
                st.caption(f"📄 Source (p. {card['page']}): _{card['source']}_")

        b1, b2, b3, b4 = st.columns(4)
        if b1.button("⬅ Previous", disabled=ss.idx == 0, width="stretch"):
            ss.idx -= 1; ss.flipped = False; st.rerun()
        if b2.button("Show answer" if not ss.flipped else "Hide answer", width="stretch"):
            ss.flipped = not ss.flipped; st.rerun()
        for col, label, val in [(b3, "✅ Knew it", "known"), (b4, "🔁 Again", "again")]:
            if col.button(label, width="stretch", disabled=not ss.flipped):
                ss.results[ss.idx] = val
                ss.idx = min(ss.idx + 1, len(cards) - 1); ss.flipped = False; st.rerun()

        known = sum(v == "known" for v in ss.results.values())
        again = [i for i, v in ss.results.items() if v == "again"]
        st.write(f"Reviewed **{len(ss.results)}/{len(cards)}** · knew **{known}** · to repeat **{len(again)}**")
        if again and st.button("Review the 'Again' cards"):
            ss.idx = min(again); ss.flipped = False; st.rerun()

# ------------------------------------------------------------------- browse
with browse:
    for i, c in enumerate(cards, 1):
        with st.expander(f"{i}. {c['question']}"):
            st.markdown(f"**Answer:** {c['answer']}")
            st.caption(f"Type: {c['kind']} · keyword: `{c['keyword']}` · score {c['score']:.2f} · page {c['page']}")
            st.caption(f"Source: _{c['source']}_")

# --------------------------------------------------------------------- quiz
with quiz:
    cloze = [c for c in cards if c["kind"] == "cloze"]
    if len(cloze) < 4:
        st.info("Need at least 4 fill-in-the-blank cards to build a multiple-choice quiz.")
    else:
        st.caption("Multiple choice built from cloze cards; distractors are answers of other cards.")
        rng = random.Random(42)
        all_answers = list({c["answer"].lower(): c["answer"] for c in cloze}.values())
        score = 0
        for i, c in enumerate(cloze):
            pool = [a for a in all_answers if a.lower() != c["answer"].lower()]
            options = rng.sample(pool, min(3, len(pool))) + [c["answer"]]
            rng.shuffle(options)
            choice = st.radio(f"**Q{i + 1}.** {c['question'].replace('Fill in the blank: ', '')}",
                              options, index=None, key=f"quiz{i}")
            if choice is not None:
                if choice == c["answer"]:
                    score += 1
                    st.success("Correct")
                else:
                    st.error(f"Answer: {c['answer']} (p. {c['page']})")
        st.subheader(f"Score: {score}/{len(cloze)}")

# ----------------------------------------------------------------- analysis
with analysis:
    left, right = st.columns(2)
    with left:
        st.subheader("Key concepts")
        st.caption("Noun phrases ranked by TF-IDF weight")
        covered = set(cov["covered"])
        for k in deck["keywords"]:
            kw, score = k["keyword"], k["score"]
            mark = "✅" if kw in covered else "⚠️"
            st.write(f"{mark} `{kw}` — {score:.2f}")
    with right:
        st.subheader("Not covered by the deck")
        if cov["missing"]:
            st.write(", ".join(f"`{k}`" for k in cov["missing"]))
            st.caption("Consider adding cards for these, or increasing the number of cards.")
        else:
            st.success("Every key concept is tested by at least one card.")

        st.subheader("Duplicates removed")
        st.caption(f"Similarity method: {stats['similarity_method']}")
        if not deck["duplicates"]:
            st.write("None found.")
        for d in deck["duplicates"]:
            with st.expander(f"similarity {d['similarity']:.2f}: {d['dropped']['question'][:70]}…"):
                st.write("**Dropped:**", d["dropped"]["source"])
                st.write("**Kept:**", d["kept"]["source"])

    st.subheader("Top-ranked sentences")
    st.dataframe(deck["top_sentences"], width="stretch", hide_index=True)
