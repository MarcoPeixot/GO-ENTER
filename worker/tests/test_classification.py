from app import similarity
from app.similarity import CandidateScore


def _candidate(minhash, chunk_sims):
    """Build a candidate with given minhash score and per-source-chunk sims."""
    c = CandidateScore("cand-1")
    c.minhash_score = minhash
    for idx, sim in enumerate(chunk_sims):
        c.best_per_source_chunk[idx] = (sim, f"src{idx}", f"match{idx}")
    return c


def test_near_duplicate_high_minhash_and_chunk_overlap():
    # 4/5 chunks strong, minhash 0.90 -> NEAR_DUPLICATE.
    cand = _candidate(0.90, [0.95, 0.92, 0.88, 0.85, 0.40])
    relation, reason = similarity.classify(cand, total_source_chunks=5)
    assert relation == similarity.NEAR_DUPLICATE
    assert reason


def test_semantically_related_high_semantic_low_minhash():
    cand = _candidate(0.30, [0.80, 0.82])
    relation, _ = similarity.classify(cand, total_source_chunks=2)
    assert relation == similarity.SEMANTICALLY_RELATED


def test_different_when_everything_low():
    cand = _candidate(0.10, [0.40, 0.50])
    relation, _ = similarity.classify(cand, total_source_chunks=2)
    assert relation == similarity.DIFFERENT


def test_high_minhash_but_low_chunk_fraction_is_not_near_dup():
    # minhash high but only 1/5 chunks strong (20% < 60%) -> not NEAR_DUPLICATE.
    cand = _candidate(0.85, [0.95, 0.10, 0.10, 0.10, 0.10])
    relation, _ = similarity.classify(cand, total_source_chunks=5)
    assert relation != similarity.NEAR_DUPLICATE


def test_semantic_score_and_fraction_helpers():
    cand = _candidate(0.0, [1.0, 0.0])
    assert cand.semantic_score == 0.5
    assert cand.chunk_fraction(2) == 0.5  # 1 of 2 chunks >= 0.80
