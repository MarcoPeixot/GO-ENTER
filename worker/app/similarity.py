"""Deterministic similarity scoring and rule-based classification.

Scores are NOT multiplied together. Each relation type is decided by explicit,
configurable rules (see app/config.py for thresholds).
"""
from app import config

# Relation types (must match what the API/consumers expect).
EXACT_FILE_DUPLICATE = "EXACT_FILE_DUPLICATE"
EXACT_TEXT_DUPLICATE = "EXACT_TEXT_DUPLICATE"
NEAR_DUPLICATE = "NEAR_DUPLICATE"
SEMANTICALLY_RELATED = "SEMANTICALLY_RELATED"
DIFFERENT = "DIFFERENT"


class CandidateScore:
    """Aggregated similarity of the new document against one candidate."""

    def __init__(self, candidate_id):
        self.candidate_id = candidate_id
        self.minhash_score = 0.0
        # best_per_source_chunk: src_idx -> (similarity, source_text, matched_text)
        self.best_per_source_chunk: dict = {}

    @property
    def semantic_score(self) -> float:
        if not self.best_per_source_chunk:
            return 0.0
        sims = [v[0] for v in self.best_per_source_chunk.values()]
        return sum(sims) / len(sims)

    def chunk_fraction(self, total_source_chunks: int) -> float:
        """Fraction of source chunks with a strong (>= threshold) match."""
        if total_source_chunks <= 0:
            return 0.0
        strong = sum(
            1 for sim, _, _ in self.best_per_source_chunk.values()
            if sim >= config.CHUNK_SIM_THRESHOLD
        )
        return strong / total_source_chunks

    def top_evidence(self, limit=3):
        items = sorted(
            self.best_per_source_chunk.values(), key=lambda v: v[0], reverse=True
        )[:limit]
        return [
            {
                "source_chunk": src[:500],
                "matched_chunk": matched[:500],
                "similarity": round(float(sim), 4),
            }
            for sim, src, matched in items
        ]


def classify(candidate: CandidateScore, total_source_chunks: int):
    """Apply the rule set. Returns (relation_type, reason).

    Exact-hash duplicates are handled earlier in the pipeline; this covers the
    embedding/MinHash-based decisions only.
    """
    minhash = candidate.minhash_score
    semantic = candidate.semantic_score
    fraction = candidate.chunk_fraction(total_source_chunks)

    if minhash >= config.MINHASH_NEAR_DUP and fraction >= config.CHUNK_SIM_FRACTION:
        return (
            NEAR_DUPLICATE,
            f"Alta sobreposição textual (MinHash={minhash:.2f}) e "
            f"{fraction*100:.0f}% dos trechos com similaridade alta.",
        )

    if semantic >= config.SEMANTIC_RELATED and minhash < config.MINHASH_SEMANTIC_MAX:
        return (
            SEMANTICALLY_RELATED,
            f"Assunto semelhante (similaridade semântica média={semantic:.2f}) "
            f"sem forte sobreposição literal (MinHash={minhash:.2f}).",
        )

    return (
        DIFFERENT,
        f"Sem candidato relevante (MinHash={minhash:.2f}, "
        f"semântica={semantic:.2f}, trechos fortes={fraction*100:.0f}%).",
    )
