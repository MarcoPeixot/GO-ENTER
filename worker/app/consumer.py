"""RabbitMQ consumer and end-to-end processing pipeline.

Consumes document jobs, runs the extraction -> fingerprint -> embed -> classify
pipeline, and writes results back to Postgres. Includes simple retries for
transient failures; terminal failures mark the document FAILED / NEEDS_OCR.
"""
import json
import logging
import time

import pika

from app import config, database as db
from app import embeddings, extraction, fingerprinting, llm, similarity
from app.chunking import chunk_text
from app.normalization import mask_variable_data, normalize_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("worker")


class TerminalError(Exception):
    """Non-retryable failure (bad input). Document should be marked FAILED."""


# --- pipeline --------------------------------------------------------------

def process_document(conn, job):
    document_id = job["document_id"]
    log.info("processing document %s (case=%s)", document_id, job.get("case_id"))

    doc = db.get_document(conn, document_id)
    if not doc:
        raise TerminalError(f"document {document_id} not found")
    case_id = doc["case_id"]
    storage_path = doc["storage_path"]

    # 1-2. read + extract
    try:
        raw_text = extraction.extract_text(storage_path)
    except extraction.NeedsOCRError as exc:
        log.warning("document %s needs OCR: %s", document_id, exc)
        db.set_status(conn, document_id, "NEEDS_OCR", error_message=str(exc))
        return
    except extraction.UnsupportedFileError as exc:
        raise TerminalError(str(exc))

    # 3-4. normalize + mask
    normalized = normalize_text(raw_text)
    masked = mask_variable_data(normalized)
    if not normalized.strip():
        raise TerminalError("no extractable text content")

    # 5. hashes
    file_hash = fingerprinting.file_sha256(storage_path)
    text_hash = fingerprinting.text_sha256(normalized)
    db.update_document(
        conn, document_id,
        normalized_text=normalized, masked_text=masked,
        file_hash=file_hash, text_hash=text_hash,
    )

    # 5b. exact-duplicate short circuit (same case_id only)
    exact_file = db.find_by_hash(conn, case_id, "file_hash", file_hash, document_id)
    if exact_file:
        _save_exact_match(conn, document_id, exact_file,
                          similarity.EXACT_FILE_DUPLICATE,
                          "Arquivo idêntico (mesmo SHA-256).")
        log.info("document %s is EXACT_FILE_DUPLICATE of %s", document_id, exact_file)
        return

    exact_text = db.find_by_hash(conn, case_id, "text_hash", text_hash, document_id)
    if exact_text:
        _save_exact_match(conn, document_id, exact_text,
                          similarity.EXACT_TEXT_DUPLICATE,
                          "Texto normalizado idêntico (arquivo possivelmente diferente).")
        log.info("document %s is EXACT_TEXT_DUPLICATE of %s", document_id, exact_text)
        return

    # 6. MinHash
    new_minhash = fingerprinting.build_minhash(masked)
    db.update_document(
        conn, document_id,
        minhash_signature=fingerprinting.minhash_to_list(new_minhash),
    )

    # 7-8. chunk + embed + store
    chunks = chunk_text(normalized)
    if not chunks:
        chunks = [normalized]
    vectors = embeddings.embed_chunks(chunks)
    db.replace_chunks(conn, document_id, chunks, vectors)
    log.info("document %s: %d chunks embedded", document_id, len(chunks))

    # 9. gather candidates (vector search per chunk, restricted to the case)
    candidates = _gather_candidates(conn, case_id, document_id, chunks, vectors)

    # MinHash similarity against stored signatures of case documents.
    for cand in db.get_case_documents(conn, case_id, document_id):
        sig = cand["minhash_signature"]
        if not sig:
            continue
        other = fingerprinting.minhash_from_list(sig)
        score = fingerprinting.jaccard(new_minhash, other)
        cs = candidates.setdefault(cand["id"], similarity.CandidateScore(cand["id"]))
        cs.minhash_score = score

    # 10. keep the best 5 candidates by semantic score
    ranked = sorted(candidates.values(), key=lambda c: c.semantic_score, reverse=True)
    top = ranked[: config.TOP_CANDIDATES]

    # 11-12. classify + optional LLM + persist
    saved = 0
    for cand in top:
        relation, reason = similarity.classify(cand, len(chunks))
        if relation == similarity.DIFFERENT:
            continue
        evidence = cand.top_evidence()
        if relation in (similarity.NEAR_DUPLICATE, similarity.SEMANTICALLY_RELATED):
            llm_result = llm.justify(relation, cand.minhash_score, cand.semantic_score, evidence)
            if llm_result and llm_result.get("reason"):
                reason = llm_result["reason"]
                if llm_result.get("changed_elements"):
                    for e in evidence:
                        e["changed_elements"] = llm_result["changed_elements"]
        db.insert_match(
            conn, document_id, cand.candidate_id, relation,
            round(cand.minhash_score, 4), round(cand.semantic_score, 4),
            reason, evidence,
        )
        saved += 1

    db.set_status(conn, document_id, "PROCESSED")
    log.info("document %s PROCESSED with %d relevant match(es)", document_id, saved)


def _gather_candidates(conn, case_id, document_id, chunks, vectors):
    """Build CandidateScore objects keyed by candidate document id."""
    candidates: dict = {}
    for idx, vec in enumerate(vectors):
        rows = db.vector_search(conn, case_id, vec, document_id, config.VECTOR_SEARCH_LIMIT)
        for row in rows:
            cand_id = row["document_id"]
            sim = float(row["similarity"])
            cs = candidates.setdefault(cand_id, similarity.CandidateScore(cand_id))
            prev = cs.best_per_source_chunk.get(idx)
            if prev is None or sim > prev[0]:
                cs.best_per_source_chunk[idx] = (sim, chunks[idx], row["content"])
    return candidates


def _save_exact_match(conn, source_id, matched_id, relation, reason):
    db.insert_match(conn, source_id, matched_id, relation, 1.0, 1.0, reason, [])
    db.set_status(conn, source_id, "PROCESSED")


# --- transport -------------------------------------------------------------

def _handle_with_retries(conn, job):
    """Run the pipeline with simple backoff retries for transient errors."""
    attempt = 0
    while True:
        try:
            process_document(conn, job)
            return
        except TerminalError as exc:
            log.error("terminal failure for %s: %s", job.get("document_id"), exc)
            _safe_fail(conn, job, str(exc))
            return
        except Exception as exc:  # transient (DB blip, model load, etc.)
            attempt += 1
            if attempt > config.MAX_RETRIES:
                log.exception("giving up on %s after %d attempts", job.get("document_id"), attempt - 1)
                _safe_fail(conn, job, f"failed after retries: {exc}")
                return
            wait = config.RETRY_BACKOFF_SECONDS * attempt
            log.warning("transient error on %s (attempt %d): %s; retrying in %.1fs",
                        job.get("document_id"), attempt, exc, wait)
            time.sleep(wait)


def _safe_fail(conn, job, message):
    try:
        db.set_status(conn, job["document_id"], "FAILED", error_message=message[:1000])
    except Exception:
        log.exception("could not mark document FAILED")


def main():
    conn = db.connect()
    params = pika.URLParameters(config.RABBITMQ_URL)

    # Retry the initial broker connection (Compose start-up ordering).
    connection = None
    for i in range(30):
        try:
            connection = pika.BlockingConnection(params)
            break
        except Exception as exc:
            log.warning("waiting for rabbitmq (%d/30): %s", i + 1, exc)
            time.sleep(2)
    if connection is None:
        raise SystemExit("could not connect to rabbitmq")

    channel = connection.channel()
    channel.queue_declare(queue=config.QUEUE_NAME, durable=True)
    channel.basic_qos(prefetch_count=1)

    def on_message(ch, method, _properties, body):
        try:
            job = json.loads(body)
        except json.JSONDecodeError:
            log.error("dropping malformed message: %r", body[:200])
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        _handle_with_retries(conn, job)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=config.QUEUE_NAME, on_message_callback=on_message)
    log.info("worker ready, consuming from %s", config.QUEUE_NAME)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    finally:
        connection.close()
        conn.close()


if __name__ == "__main__":
    main()
