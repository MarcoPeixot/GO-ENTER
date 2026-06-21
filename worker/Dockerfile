FROM python:3.11-slim

# Avoid interactive prompts; keep Python output unbuffered for live logs.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models

WORKDIR /app

# System libs needed by PyMuPDF / numpy wheels are already bundled; only need build basics.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Pre-download the embedding model into the image so the first job is fast and
# the worker can run without internet at runtime.
ARG EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

COPY app ./app
COPY tests ./tests

CMD ["python", "-m", "app.consumer"]
