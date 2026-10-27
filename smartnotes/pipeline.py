"""note2recall NLP pipeline: study notes -> grounded flashcards.

Steps
1. Ingestion + preprocessing   (pypdf, regex cleanup, spaCy sentence split)
2. Keyword extraction          (TF-IDF over sentences, restricted to noun phrases)
3. Sentence ranking            (TF-IDF weight + keyword density)
4. Question generation         (definition templates, cloze deletion fallback)
5. Duplicate detection         (sentence embeddings, TF-IDF fallback)
6. Coverage analysis           (important keywords not tested by any card)
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field, asdict

import numpy as np
import spacy
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_nlp = None
_embedder = None


def get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def get_embedder():
    """Load the sentence-transformer once; return None if unavailable (offline etc.)."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _embedder = False
    return _embedder or None


# ---------------------------------------------------------------- data types

@dataclass
class Sentence:
    text: str
    page: int
    score: float = 0.0
    keywords: list[str] = field(default_factory=list)


@dataclass
class Card:
    question: str
    answer: str
    source: str
    page: int
    kind: str          # "definition" | "cloze"
    keyword: str
    score: float

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------- 1. preprocessing

def extract_pages(file) -> list[tuple[int, str]]:
    """Return [(page_number, raw_text)] from a PDF/TXT path, bytes, or file-like object."""
    name = getattr(file, "name", file if isinstance(file, str) else "")
    if isinstance(file, (bytes, bytearray)):
        data = bytes(file)
    elif isinstance(file, str):
        with open(file, "rb") as f:
            data = f.read()
    else:
        data = file.read()

    if str(name).lower().endswith(".txt") or not data.startswith(b"%PDF"):
        return [(1, data.decode("utf-8", errors="ignore"))]

    reader = PdfReader(io.BytesIO(data))
    pages = [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    empty = [i for i, (_, t) in enumerate(pages) if len(t.strip()) < 20]
    if empty and ocr_available():          # scanned pages have no text layer
        for i, text in zip(empty, _ocr_pages(data, empty)):
            pages[i] = (i + 1, text)
    return pages


def ocr_available() -> bool:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_pages(pdf_bytes: bytes, indices: list[int]) -> list[str]:
    """Render the given pages at 300 dpi and run Tesseract OCR (printed text only)."""
    import pypdfium2 as pdfium
    import pytesseract
    pdf = pdfium.PdfDocument(pdf_bytes)
    return [pytesseract.image_to_string(pdf[i].render(scale=300 / 72).to_pil()) for i in indices]


_BULLET = re.compile(r"^([•▪●◦○■□➢➤▶►✓✔\-\*–]|\d{1,2}[.)])\s*")
_PAGE_NO = re.compile(r"(page\s*)?\d+(\s*(/|of)\s*\d+)?", re.I)


def split_merged_word(word: str) -> str:
    """Repair words glued together by PDF extraction: "handlesaddressing" -> "handles addressing".

    Only applied to unknown lowercase words; every piece must be a common English word
    (Zipf >= 3), so real technical terms like "supernetting" or "lemmatization" are untouched.
    """
    from wordfreq import zipf_frequency
    if len(word) < 6 or not word.islower() or zipf_frequency(word, "en") > 0:
        return word
    if word.startswith(_PREFIXES):       # "subwords", "supernetting" are real compounds
        return word

    def ok(part):
        return (len(part) >= 3 or part in _GLUE) and zipf_frequency(part, "en") >= 3

    def best_split(w, parts):
        """Best split into `parts` valid words, scored by the rarest piece."""
        if parts == 1:
            return (zipf_frequency(w, "en"), w) if ok(w) else None
        best = None
        for i in range(1, len(w)):
            head, tail = w[:i], best_split(w[i:], parts - 1)
            if ok(head) and tail:
                cand = (min(zipf_frequency(head, "en"), tail[0]), f"{head} {tail[1]}")
                best = max(best, cand) if best else cand
        return best

    two = best_split(word, 2)
    if two:
        return two[1]
    three = best_split(word, 3)          # "thetopologyof": only with a glue word in it
    if three and _GLUE & set(three[1].split()):
        return three[1]
    return word


_PREFIXES = ("sub", "super", "inter", "intra", "multi", "pre", "re", "non", "un", "over", "under",
             "micro", "macro", "hyper", "bi", "tri", "uni", "co", "de", "dis", "mis", "out", "self")
_GLUE = {"a", "an", "the", "of", "to", "in", "on", "is", "and", "or", "for", "by", "as", "at"}


def clean_text(text: str, doc_counts: dict | None = None) -> str:
    """Normalise one page of extracted text into running sentences.

    Works line by line so it handles both prose PDFs and lecture slides: on slides
    (short lines) every capitalised line or bullet starts a new sentence, in prose a
    wrapped line is joined onto the previous one.
    """
    text = text.replace("­", "")                              # soft hyphens
    text = re.sub(r"https?://\S+", "", text)
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l and not _PAGE_NO.fullmatch(l)]
    if not lines:
        return ""
    slide_like = np.mean([len(l) for l in lines]) < 60

    out = ""
    for line in lines:
        bullet = bool(_BULLET.match(line))
        line = _BULLET.sub("", line).strip()
        if not line:
            continue
        if not out:
            out = line
            continue
        if out.endswith("-") and line[:1].islower():               # hyphenated line wrap
            out = out[:-1] + line
            continue
        last_line = out.rsplit(". ", 1)[-1]
        last_word = last_line.split()[-1]
        prev_is_heading = len(last_line.split()) <= 5 and not re.search(r"[,;:\-]$", out)
        # a line ending in "the", "and", "," or a capitalised word ("File" + "Transfer Protocol")
        # is a wrapped line, not the end of a bullet
        continues = (last_word.lower() in _GLUE or out.endswith(",")
                     or (last_word[:1].isupper() and not prev_is_heading))
        if bullet or (line[:1].isupper() and not continues and (slide_like or prev_is_heading)):
            if not re.search(r"[.!?:;]$", out):
                out += "."
        out += " " + line

    if doc_counts is not None:   # only repair words that occur once in the whole document
        out = re.sub(r"\b[a-z]{6,}\b",
                     lambda m: split_merged_word(m.group(0)) if doc_counts.get(m.group(0), 0) <= 1 else m.group(0),
                     out)
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"\.(\s*\.)+", ".", out)
    return out.strip()


def split_sentences(pages: list[tuple[int, str]], min_words=6, max_words=60) -> list[Sentence]:
    from collections import Counter
    nlp = get_nlp()
    doc_counts = Counter(re.findall(r"\b[a-z]{6,}\b", " ".join(t for _, t in pages)))
    out = []
    for page_no, raw in pages:
        for sent in nlp(clean_text(raw, doc_counts)).sents:
            s = sent.text.strip()
            n = len(s.split())
            has_verb = any(t.pos_ in ("VERB", "AUX") for t in sent)   # headings/titles have none
            if min_words <= n <= max_words and has_verb and re.search(r"[a-zA-Z]{3}", s):
                out.append(Sentence(text=s, page=page_no))
    return out


# ------------------------------------------------------ 2. keyword extraction

def _candidate_phrases(text: str) -> set[str]:
    """Noun chunks and named entities, normalized (lowercase, no leading determiners)."""
    from wordfreq import zipf_frequency
    doc = get_nlp()(text)
    phrases = set()
    for span in list(doc.noun_chunks) + list(doc.ents):
        toks = [t for t in span if not (t.is_stop or t.is_punct or t.like_num or t.pos_ == "PRON")]
        # strip common leading modifiers: "modern NER systems" -> "NER systems"
        while len(toks) > 1 and toks[0].pos_ in ("ADJ", "ADV") and zipf_frequency(toks[0].text, "en") > 4:
            toks = toks[1:]
        # the chunk must end in a noun ("lemmatization maps" is a verb mis-parse)
        if toks and toks[-1].pos_ not in ("NOUN", "PROPN"):
            continue
        if not toks:
            continue
        phrase = " ".join(t.text.lower() for t in toks)
        if 3 <= len(phrase) <= 40 and len(toks) <= 4:
            phrases.add(phrase)
    return phrases


def specificity(phrase: str) -> float:
    """How domain-specific a phrase is, in [0, 1], from general-English word frequency.

    Uses the Zipf scale (log10 occurrences per billion words, ~1 = very rare, ~7 = "the").
    A phrase is as specific as its rarest word: "word embeddings" is specific, "words" is not.
    """
    from wordfreq import zipf_frequency
    rarest = min(zipf_frequency(w, "en") for w in re.split(r"[\s\-]+", phrase) if w)
    return max(0.0, min(1.0, (6.5 - rarest) / 4.5))


def extract_keywords(sentences: list[Sentence], top_k=25):
    """Rank noun phrases by TF-IDF weight, adjusted for domain specificity.

    score = (summed TF-IDF over sentences) * IDF * specificity^2 * multi-word boost
    IDF pushes down terms that occur in many sentences of these notes; specificity pushes
    down words that are common in English in general ("model", "count", "text").
    Returns (keywords [(phrase, score)], fitted vectorizer, sentence-term matrix).
    """
    texts = [s.text for s in sentences]
    vec = TfidfVectorizer(ngram_range=(1, 3), stop_words="english", lowercase=True,
                          token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9\-]+\b")
    X = vec.fit_transform(texts)
    terms = vec.get_feature_names_out()
    weights = dict(zip(terms, np.asarray(X.sum(axis=0)).ravel() * vec.idf_))

    candidates = _candidate_phrases(" ".join(texts))
    scored = {}
    for phrase in candidates:
        if phrase in weights:
            scored[phrase] = (weights[phrase] * specificity(phrase) ** 2
                              * (1 + 0.5 * (len(phrase.split()) - 1)))

    ranked = sorted(scored.items(), key=lambda kv: -kv[1])
    kept = []
    for phrase, score in ranked:
        # drop overlaps with a higher-ranked keyword (either direction) and plural variants
        stem = phrase.rstrip("s")
        if any(_contains(k, phrase) or _contains(phrase, k) or k.rstrip("s") == stem for k, _ in kept):
            continue
        kept.append((phrase, round(float(score), 3)))
        if len(kept) == top_k:
            break
    return kept, vec, X


def _term_regex(term: str) -> str:
    """Whole-term match that does not fire inside hyphenated words (bag-of-*words*)."""
    return rf"(?<![\w-]){re.escape(term)}s?(?![\w-])"


def _contains(text: str, term: str) -> bool:
    return re.search(_term_regex(term), text, flags=re.I) is not None


# -------------------------------------------------------- 3. sentence ranking

def rank_sentences(sentences: list[Sentence], keywords, X) -> list[Sentence]:
    """Score = mean TF-IDF weight of the sentence + bonus for each keyword it contains."""
    kw_score = dict(keywords)
    max_kw = max(kw_score.values()) if kw_score else 1.0
    tfidf_mean = np.asarray(X.sum(axis=1)).ravel() / np.maximum(X.getnnz(axis=1), 1)

    for s, base in zip(sentences, tfidf_mean):
        s.keywords = [k for k in kw_score if _contains(s.text, k)]
        s.score = float(base + sum(kw_score[k] / max_kw for k in s.keywords) * 0.5)
    return sorted(sentences, key=lambda s: -s.score)


# ----------------------------------------------------- 4. question generation

_DEF_PATTERNS = [
    # "X is a/an/the Y" / "X are Y"
    re.compile(r"^(?P<term>[A-Z][\w\s\-\(\)/]{1,60}?)\s+(?:is|are)\s+(?:(?:a|an|the|defined as|known as|called)\b)?\s*(?P<def>.{10,})$"),
    # "X refers to Y" / "X means Y" / "X is used to Y"
    re.compile(r"^(?P<term>[A-Z][\w\s\-\(\)/]{1,60}?)\s+(?:refers to|means|describes|is used to|are used to)\s+(?P<def>.{10,})$"),
]
_BAD_TERMS = {"it", "this", "that", "these", "those", "they", "there", "which", "he", "she", "we", "one",
              "each", "why", "what", "how", "here", "value", "example", "first", "second", "following", "most",
              "when", "if", "because", "since", "where", "once", "then", "after", "before", "whether"}


def _definition_card(s: Sentence) -> Card | None:
    text = s.text.rstrip(".")
    for pat in _DEF_PATTERNS:
        m = pat.match(text)
        if not m:
            continue
        raw_term = m.group("term").strip()
        article = re.match(r"^(a|an)\s+", raw_term, flags=re.I)
        term = re.sub(r"^(the|a|an)\s+", "", raw_term, flags=re.I)
        term = re.sub(r"\s+\w+ly$", "", term)          # "network topology specifically"
        term = re.sub(r"^(while|whereas|thus|hence|also|so|but|however)\s+", "", term, flags=re.I)
        if (len(term.split()) > 4 or re.search(r"\b(and|or)\b|\d", term)
                or _BAD_TERMS & set(term.lower().split()) or specificity(term.lower()) < 0.35):
            return None
        answer = m.group("def").strip().rstrip(".")
        if len(re.findall(r"[A-Za-z]{2,}", answer)) < 4:   # "Left most of all", "128+64 = 192"
            return None
        # "X are usually trained as..." is a description, not a definition
        first = next(t for t in get_nlp()(text) if t.idx >= m.start("def"))   # tag in context
        if first.pos_ in ("VERB", "AUX", "ADP", "PART") or (first.pos_ == "ADV" and first.head.pos_ in ("VERB", "AUX")):
            return None
        if term[1:] == term[1:].lower():          # keep acronyms, CamelCase, Proper Names
            term = term[0].lower() + term[1:]
        keyword = term.lower()
        if article:
            term = f"{article.group(1).lower()} {term}"
        after = text[len(raw_term):len(raw_term) + 25]
        verb = "are" if re.match(r"\s+are\b", after) else "is"
        if re.match(r"\s+(is|are) used to", after):
            q = f"What {verb} {term} used for?"
        else:
            q = f"What {verb} {term}?"
        q = q[0].upper() + q[1:]
        return Card(question=q, answer=answer[0].upper() + answer[1:] + ".",
                    source=s.text, page=s.page, kind="definition",
                    keyword=keyword, score=s.score)
    return None


def _cloze_card(s: Sentence, used: set[str]) -> Card | None:
    """Blank out the most important keyword that hasn't been tested yet.

    The blanked term must be worth recalling: a multi-word term, an acronym, or a word
    that is uncommon in general English (blanking "layer" or "bits" makes a trivial card).
    """
    for kw in s.keywords:
        if kw in used:
            continue
        m = re.search(_term_regex(kw), s.text, flags=re.I)
        if not m:
            continue
        # TCP, FDM are acronyms; "LAYER" in an all-caps slide heading is not
        is_acronym = m.group(0).isupper() and len(m.group(0)) >= 2 and specificity(kw) >= 0.5
        if " " not in kw and not is_acronym and specificity(kw) < 0.6:
            continue
        blanked = s.text[: m.start()] + "_____" + s.text[m.end():]
        if len(re.findall(r"[A-Za-z]{2,}", blanked)) < 7:
            continue
        # answer leaks if another form of it is still in the sentence (topology / topologies)
        stem = kw[: max(4, len(kw) - 3)]
        if re.search(rf"(?<![\w-]){re.escape(stem)}", blanked, flags=re.I):
            continue
        return Card(question=f"Fill in the blank: {blanked}", answer=m.group(0),
                    source=s.text, page=s.page, kind="cloze", keyword=kw, score=s.score)
    return None


# sentences that only make sense next to a slide image, or are course admin
_NOT_STANDALONE = re.compile(r"\b(figure|fig\.|diagram|shown (above|below)|above image|syllabus|module \d|"
                             r"chapter \d|lecture \d|course outcome)\b", re.I)


def generate_cards(ranked: list[Sentence], n_cards=15) -> list[Card]:
    cards, used = [], set()
    for s in ranked:
        if _NOT_STANDALONE.search(s.text):
            continue
        card = _definition_card(s) or _cloze_card(s, used)
        if card:
            cards.append(card)
            used.add(card.keyword)
        if len(cards) >= n_cards * 2:   # over-generate, duplicates are removed next
            break
    return cards


# ---------------------------------------------------- 5. duplicate detection

def embed(texts: list[str]):
    model = get_embedder()
    if model is not None:
        return model.encode(texts, normalize_embeddings=True), "sentence-transformer"
    vec = TfidfVectorizer(stop_words="english").fit(texts)
    return vec.transform(texts), "tfidf"


def _initials(phrase: str) -> str:
    return "".join(w[0] for w in re.split(r"[\s\-]+", phrase) if w)


def same_concept(a: str, b: str) -> bool:
    """Same keyword, or one is the acronym of the other ("rarp" / "reverse address resolution protocol")."""
    a, b = a.lower(), b.lower()
    a_base = re.sub(r"\s*\(.*\)$", "", a)   # "address resolution protocol (arp)"
    b_base = re.sub(r"\s*\(.*\)$", "", b)
    if a == b or a_base == b_base:
        return True
    for short, long in ((a_base, b_base), (b_base, a_base)):
        if " " not in short and len(short) >= 2 and short == _initials(long):
            return True
    return False


def remove_duplicates(cards: list[Card], threshold=0.80):
    """Greedy: keep cards in rank order, drop a card that duplicates an already-kept one.

    Two cards are duplicates if their source sentences are semantically similar
    (cosine >= threshold) or they test the same concept (same keyword). A definition
    card is preferred over a cloze card for the same concept.
    """
    if not cards:
        return [], [], "none"
    order = sorted(range(len(cards)), key=lambda i: (cards[i].kind != "definition", -cards[i].score))
    E, method = embed([c.source for c in cards])
    sim = cosine_similarity(E)
    kept_idx, dupes = [], []
    for i in order:
        match, reason = None, None
        for j in kept_idx:
            if sim[i, j] >= threshold:
                match, reason = j, "similar meaning"
                break
            if same_concept(cards[i].keyword, cards[j].keyword):
                match, reason = j, "same concept"
                break
        if match is None:
            kept_idx.append(i)
        else:
            dupes.append({"dropped": cards[i], "kept": cards[match], "reason": reason,
                          "similarity": round(float(sim[i, match]), 3)})
    kept_idx.sort(key=lambda i: -cards[i].score)
    return [cards[i] for i in kept_idx], dupes, method


# ------------------------------------------------------- 6. coverage analysis

def coverage(cards: list[Card], keywords) -> dict:
    tested = " ".join(f"{c.question} {c.answer}" for c in cards)
    covered = [k for k, _ in keywords if _contains(tested, k)]
    missing = [k for k, _ in keywords if k not in covered]
    return {"covered": covered, "missing": missing,
            "ratio": round(len(covered) / max(len(keywords), 1), 3)}


# ------------------------------------------------------------------- facade

def build_deck(file, n_cards=15, top_k=25, dup_threshold=0.80) -> dict:
    """Run the full pipeline. This is the only function the frontend needs."""
    pages = extract_pages(file)
    sentences = split_sentences(pages)
    if len(sentences) < 3:
        hint = "" if ocr_available() else " Scanned PDFs need OCR: install it with  sudo apt install tesseract-ocr"
        raise ValueError("Not enough readable text found (is the PDF scanned or handwritten?)." + hint)
    keywords, _, X = extract_keywords(sentences, top_k=top_k)
    ranked = rank_sentences(sentences, keywords, X)
    candidates = generate_cards(ranked, n_cards=n_cards)
    cards, dupes, sim_method = remove_duplicates(candidates, threshold=dup_threshold)
    cards = cards[:n_cards]
    return {
        "cards": cards,
        "duplicates": dupes,
        "keywords": keywords,
        "coverage": coverage(cards, keywords),
        "stats": {"pages": len(pages), "sentences": len(sentences),
                  "candidates": len(candidates), "cards": len(cards),
                  "similarity_method": sim_method},
        "top_sentences": ranked[:10],
    }


def deck_to_dict(deck: dict) -> dict:
    """Plain JSON-serialisable version of a build_deck() result (for the API and caching)."""
    return {
        **deck,
        "cards": [c.to_dict() for c in deck["cards"]],
        "duplicates": [{**d, "dropped": d["dropped"].to_dict(), "kept": d["kept"].to_dict()}
                       for d in deck["duplicates"]],
        "keywords": [{"keyword": k, "score": s} for k, s in deck["keywords"]],
        "top_sentences": [{"text": s.text, "page": s.page, "score": round(s.score, 3)}
                          for s in deck["top_sentences"]],
    }
