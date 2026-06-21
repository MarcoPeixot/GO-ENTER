from app.chunking import chunk_text


def _words(n):
    return " ".join(f"w{i}" for i in range(n))


def test_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_single_short_paragraph_is_one_chunk():
    text = _words(30)
    chunks = chunk_text(text, min_words=10, max_words=100, overlap=5)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_large_text_splits_with_overlap_and_respects_max():
    text = _words(100)
    chunks = chunk_text(text, min_words=10, max_words=20, overlap=5)
    assert len(chunks) > 1
    # No chunk exceeds max_words.
    for c in chunks:
        assert len(c.split()) <= 20
    # Consecutive chunks overlap by `overlap` words.
    first = chunks[0].split()
    second = chunks[1].split()
    assert first[-5:] == second[:5]


def test_prefers_paragraph_boundaries():
    text = _words(15) + "\n\n" + _words(15)
    chunks = chunk_text(text, min_words=10, max_words=40, overlap=0)
    # Both small paragraphs merge into one chunk (fits under max_words).
    assert len(chunks) == 1
    assert len(chunks[0].split()) == 30
