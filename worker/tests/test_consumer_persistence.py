from app import consumer, similarity
from app.similarity import CandidateScore


def test_save_candidate_decision_persists_different(monkeypatch):
    inserted = []

    def fake_insert_match(
        conn,
        source_id,
        matched_id,
        relation_type,
        near_duplicate_score,
        semantic_score,
        reason,
        evidence,
    ):
        inserted.append(
            {
                "source_id": source_id,
                "matched_id": matched_id,
                "relation_type": relation_type,
                "near_duplicate_score": near_duplicate_score,
                "semantic_score": semantic_score,
                "reason": reason,
                "evidence": evidence,
            }
        )

    monkeypatch.setattr(consumer.db, "insert_match", fake_insert_match)

    candidate = CandidateScore("matched-document")
    candidate.minhash_score = 0.0
    candidate.best_per_source_chunk[0] = (
        0.45,
        "Texto do documento enviado.",
        "Texto do documento comparado.",
    )

    relation = consumer._save_candidate_decision(
        "conn", "source-document", candidate, total_source_chunks=1
    )

    assert relation == similarity.DIFFERENT
    assert inserted == [
        {
            "source_id": "source-document",
            "matched_id": "matched-document",
            "relation_type": similarity.DIFFERENT,
            "near_duplicate_score": 0.0,
            "semantic_score": 0.45,
            "reason": "Sem candidato relevante (MinHash=0.00, semântica=0.45, trechos fortes=0%).",
            "evidence": [
                {
                    "source_chunk": "Texto do documento enviado.",
                    "matched_chunk": "Texto do documento comparado.",
                    "similarity": 0.45,
                }
            ],
        }
    ]
