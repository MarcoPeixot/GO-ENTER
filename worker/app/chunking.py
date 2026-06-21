"""Split text into word-bounded chunks, preferring paragraph boundaries.

Strategy:
  * Paragraphs (split on blank lines) are the preferred unit.
  * A paragraph larger than max_words is split into overlapping word windows
    (step = max_words - overlap), so no single chunk exceeds max_words.
  * Smaller paragraphs are greedily merged up to max_words, targeting min_words,
    carrying an overlap tail across merge boundaries.

Every returned chunk is guaranteed to contain at most max_words words.
"""
from app import config


def chunk_text(text: str, *, min_words=None, max_words=None, overlap=None):
    min_words = config.CHUNK_MIN_WORDS if min_words is None else min_words
    max_words = config.CHUNK_MAX_WORDS if max_words is None else max_words
    overlap = config.CHUNK_OVERLAP_WORDS if overlap is None else overlap

    if not text or not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    # 1. Build "units" (word lists), each <= max_words.
    step = max(1, max_words - overlap)
    units = []
    for para in paragraphs:
        words = para.split()
        if len(words) <= max_words:
            units.append(words)
        else:
            for i in range(0, len(words), step):
                window = words[i:i + max_words]
                units.append(window)
                if i + max_words >= len(words):
                    break

    # 2. Greedily merge small units up to max_words, with overlap tails.
    chunks: list[list[str]] = []
    current: list[str] = []
    for unit in units:
        if not current:
            current = list(unit)
        elif len(current) + len(unit) <= max_words:
            current.extend(unit)
        else:
            chunks.append(current)
            tail = current[-overlap:] if overlap > 0 else []
            if len(tail) + len(unit) > max_words:
                tail = []
            current = tail + list(unit)
    if current:
        chunks.append(current)

    return [" ".join(words) for words in chunks if words]
