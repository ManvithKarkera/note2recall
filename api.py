"""note2recall — REST API for the React frontend.

Run with:  .venv/bin/uvicorn api:app --port 8000
Then open http://localhost:8000 (serves the built React app from frontend/dist).
"""

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from smartnotes.pipeline import build_deck, deck_to_dict, get_embedder, get_nlp, ocr_available

MAX_BYTES = 50 * 1024 * 1024

app = FastAPI(title="note2recall")
# Vite dev server runs on :5173 and calls the API on :8000
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def warm_up():
    """Load spaCy and the embedding model once, so the first upload isn't slow."""
    get_nlp()
    get_embedder()


@app.get("/api/health")
def health():
    return {"status": "ok", "ocr": ocr_available()}


@app.post("/api/deck")
async def make_deck(file: UploadFile = File(...), n_cards: int = Form(15), threshold: float = Form(0.80)):
    name = (file.filename or "").lower()
    if not name.endswith((".pdf", ".txt")):
        raise HTTPException(400, "Please upload a PDF or a .txt file.")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 50 MB.")
    if not 3 <= n_cards <= 60 or not 0.3 <= threshold <= 0.99:
        raise HTTPException(400, "n_cards must be 3–60 and threshold 0.3–0.99.")
    try:
        # the pipeline is CPU-bound; keep the server responsive while it runs
        deck = await run_in_threadpool(build_deck, data, n_cards=n_cards, dup_threshold=threshold)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"filename": file.filename, **deck_to_dict(deck)}


dist = Path(__file__).parent / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
