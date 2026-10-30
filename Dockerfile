# note2recall API.
# Lite by default (TF-IDF duplicate detection, fits in 512 MB RAM).
# Build with --build-arg EMBEDDINGS=1 for sentence-embedding duplicate detection.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app

COPY --chown=user requirements-api.txt requirements-embeddings.txt ./
RUN pip install --no-cache-dir --user -r requirements-api.txt

ARG EMBEDDINGS=0
# bake the embedding model into the image so startup doesn't download it
RUN if [ "$EMBEDDINGS" = "1" ]; then \
      pip install --no-cache-dir --user torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu \
      && pip install --no-cache-dir --user -r requirements-embeddings.txt \
      && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"; \
    fi
ENV HF_HUB_OFFLINE=1

COPY --chown=user smartnotes ./smartnotes
COPY --chown=user api.py .

# Render (and most hosts) pass the port in $PORT
ENV PORT=8000
EXPOSE 8000
CMD uvicorn api:app --host 0.0.0.0 --port $PORT
