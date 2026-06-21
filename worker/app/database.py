"""PostgreSQL access for the worker (psycopg2).

Owns all SQL. Embeddings are written/queried using the pgvector textual
representation ('[v1,v2,...]') cast to ::vector.
"""
import json
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from app import config


def connect():
    conn = psycopg2.connect(config.DATABASE_URL)
    conn.autocommit = False
    return conn


@contextmanager
def cursor(conn):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield cur
    finally:
        cur.close()


def _vector_literal(vec) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


# --- document lifecycle ----------------------------------------------------

def get_document(conn, document_id):
    with cursor(conn) as cur:
        cur.execute(
            "SELECT id, case_id, filename, storage_path, status FROM documents WHERE id = %s",
            (document_id,),
        )
        return cur.fetchone()


def update_document(conn, document_id, **fields):
    """Update arbitrary document columns. minhash_signature is JSON-encoded."""
    if not fields:
        return
    if "minhash_signature" in fields and fields["minhash_signature"] is not None:
        fields["minhash_signature"] = json.dumps(fields["minhash_signature"])
    sets = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [document_id]
    with cursor(conn) as cur:
        cur.execute(
            f"UPDATE documents SET {sets}, updated_at = now() WHERE id = %s",
            values,
        )
    conn.commit()


def set_status(conn, document_id, status, error_message=None):
    update_document(conn, document_id, status=status, error_message=error_message)


# --- chunks ----------------------------------------------------------------

def replace_chunks(conn, document_id, chunks, embeddings):
    """Delete any existing chunks for the document and insert the new set."""
    with cursor(conn) as cur:
        cur.execute("DELETE FROM document_chunks WHERE document_id = %s", (document_id,))
        for idx, (content, emb) in enumerate(zip(chunks, embeddings)):
            cur.execute(
                """INSERT INTO document_chunks (document_id, chunk_index, content, embedding)
                   VALUES (%s, %s, %s, %s::vector)""",
                (document_id, idx, content, _vector_literal(emb)),
            )
    conn.commit()


def get_chunks(conn, document_id):
    with cursor(conn) as cur:
        cur.execute(
            "SELECT chunk_index, content FROM document_chunks WHERE document_id = %s ORDER BY chunk_index",
            (document_id,),
        )
        return cur.fetchall()


# --- candidate lookup ------------------------------------------------------

def find_by_hash(conn, case_id, column, value, exclude_id):
    """Return the most recent other document in the case with matching hash."""
    if not value:
        return None
    with cursor(conn) as cur:
        cur.execute(
            f"""SELECT id FROM documents
                WHERE case_id = %s AND {column} = %s AND id <> %s AND status = 'PROCESSED'
                ORDER BY created_at DESC LIMIT 1""",
            (case_id, value, exclude_id),
        )
        row = cur.fetchone()
        return row["id"] if row else None


def get_case_documents(conn, case_id, exclude_id):
    """Other processed documents in the case, with their MinHash signatures."""
    with cursor(conn) as cur:
        cur.execute(
            """SELECT id, minhash_signature FROM documents
               WHERE case_id = %s AND id <> %s AND status = 'PROCESSED'""",
            (case_id, exclude_id),
        )
        return cur.fetchall()


def vector_search(conn, case_id, embedding, exclude_id, limit):
    """Return nearest chunks (cosine) across other docs in the same case.

    similarity = 1 - cosine_distance.
    """
    with cursor(conn) as cur:
        cur.execute(
            """SELECT c.document_id, c.chunk_index, c.content,
                      1 - (c.embedding <=> %s::vector) AS similarity
               FROM document_chunks c
               JOIN documents d ON d.id = c.document_id
               WHERE d.case_id = %s AND c.document_id <> %s AND d.status = 'PROCESSED'
               ORDER BY c.embedding <=> %s::vector
               LIMIT %s""",
            (_vector_literal(embedding), case_id, exclude_id, _vector_literal(embedding), limit),
        )
        return cur.fetchall()


# --- matches ---------------------------------------------------------------

def insert_match(conn, source_id, matched_id, relation_type,
                 near_duplicate_score, semantic_score, reason, evidence):
    with cursor(conn) as cur:
        cur.execute(
            """INSERT INTO document_matches
                   (source_document_id, matched_document_id, relation_type,
                    near_duplicate_score, semantic_score, reason, evidence)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (source_document_id, matched_document_id)
               DO UPDATE SET relation_type = EXCLUDED.relation_type,
                             near_duplicate_score = EXCLUDED.near_duplicate_score,
                             semantic_score = EXCLUDED.semantic_score,
                             reason = EXCLUDED.reason,
                             evidence = EXCLUDED.evidence""",
            (source_id, matched_id, relation_type, near_duplicate_score,
             semantic_score, reason, json.dumps(evidence)),
        )
    conn.commit()
