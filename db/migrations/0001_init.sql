-- JuridicFlow MVP schema.
-- Idempotent so it can run via docker-entrypoint-initdb.d or a migration runner.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- documents -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id           TEXT NOT NULL,
    filename          TEXT NOT NULL,
    storage_path      TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'PROCESSING',
    file_hash         TEXT,
    text_hash         TEXT,
    normalized_text   TEXT,
    masked_text       TEXT,
    minhash_signature JSONB,
    error_message     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_case_id   ON documents (case_id);
CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents (case_id, file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_text_hash ON documents (case_id, text_hash);

-- document_chunks -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_chunks (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content     TEXT NOT NULL,
    embedding   VECTOR(384),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks (document_id);

-- Approximate-nearest-neighbour index for cosine distance on embeddings.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- document_matches ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_matches (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    matched_document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    relation_type       TEXT NOT NULL,
    near_duplicate_score FLOAT,
    semantic_score      FLOAT,
    reason              TEXT,
    evidence            JSONB DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_document_id, matched_document_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_source ON document_matches (source_document_id);
