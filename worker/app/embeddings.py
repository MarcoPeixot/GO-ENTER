"""Sentence embedding generation using sentence-transformers.

The model is loaded lazily and cached as a module-level singleton so the
(relatively heavy) load happens once per worker process.
"""
from app import config

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(config.EMBEDDING_MODEL)
    return _model


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Return one embedding vector per chunk (normalized for cosine similarity)."""
    if not chunks:
        return []
    model = _get_model()
    vectors = model.encode(
        chunks,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return [vec.tolist() for vec in vectors]
