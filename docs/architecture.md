# note2recall architecture

## System overview

The React app runs in the browser and sends the uploaded file to the FastAPI backend. The backend runs the NLP pipeline and returns the whole deck as JSON. There is no database: the browser keeps the last deck and review progress in `localStorage`.

![note2recall system architecture](architecture.png)

## NLP pipeline (`build_deck`)

Everything runs locally with traditional NLP: no LLM or external API calls.

```mermaid
flowchart TD
    src[/"PDF or TXT bytes"/]

    subgraph pre["1 · Preprocessing"]
        ext["extract_pages<br/>pypdf text layer"]
        ocr["OCR for empty pages<br/>pypdfium2 at 300 dpi → Tesseract"]
        clean["clean_text<br/>slide-aware line joining<br/>split glued words (wordfreq)"]
        sent["split_sentences<br/>spaCy, 6–60 words, keeps page number"]
        ext -->|"page has < 20 chars"| ocr --> clean
        ext --> clean --> sent
    end

    subgraph kw["2 · Key concepts"]
        tfidf["extract_keywords<br/>TF-IDF over spaCy noun phrases<br/>× domain specificity (wordfreq)"]
    end

    subgraph rank["3 · Sentence ranking"]
        rs["rank_sentences<br/>mean TF-IDF + bonus per key concept"]
    end

    subgraph gen["4 · Question generation"]
        defn["Definition templates<br/>'X is a Y' → 'What is X?'"]
        cloze["Cloze deletion<br/>of key terms"]
    end

    subgraph dup["5 · Duplicate removal"]
        emb{"Embedder available?"}
        st["all-MiniLM-L6-v2<br/>cosine similarity"]
        tf["TF-IDF cosine<br/>(lite image)"]
        same["Acronym-aware<br/>same_concept check"]
        emb -->|"yes · EMBEDDINGS=1"| st --> same
        emb -->|"no · default"| tf --> same
    end

    cov["6 · coverage<br/>key concepts no card tests"]
    out[/"deck_to_dict → JSON<br/>cards · duplicates · keywords<br/>coverage · stats · top sentences"/]

    src --> ext
    sent --> tfidf --> rs --> defn & cloze
    defn & cloze --> emb
    same --> cov --> out
```

## Deployment and local development

| | Production | Local |
|---|---|---|
| Frontend | Vercel, `VITE_API_URL` points at the Render backend | Vite dev server on `:5173`, which proxies `/api` to `:8000` |
| Backend | Render web service built from `Dockerfile` (`render.yaml`), health check on `/api/health` | `uvicorn api:app --port 8000`, which also serves `frontend/dist` |
| Image | Lite by default: OCR plus TF-IDF duplicates, fits in 512 MB. `--build-arg EMBEDDINGS=1` adds torch and MiniLM (about 1.5 GB) | Full `requirements.txt` with embeddings |
| CORS | `ALLOWED_ORIGIN_REGEX` matches `note2recall*.vercel.app` | `localhost:5173` is allowed by default |

`app.py` is an alternative Streamlit frontend that calls `build_deck()` directly, without the API.
