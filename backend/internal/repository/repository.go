package repository

import (
	"context"
	"errors"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"juridicflow/internal/documents"
)

// ErrNotFound is returned when a document does not exist.
var ErrNotFound = errors.New("document not found")

// Repository wraps the Postgres connection pool and document queries.
type Repository struct {
	pool *pgxpool.Pool
}

func New(ctx context.Context, databaseURL string) (*Repository, error) {
	pool, err := pgxpool.New(ctx, databaseURL)
	if err != nil {
		return nil, fmt.Errorf("connect postgres: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("ping postgres: %w", err)
	}
	return &Repository{pool: pool}, nil
}

func (r *Repository) Close() { r.pool.Close() }

// CreateDocument inserts a new document row in PROCESSING status.
func (r *Repository) CreateDocument(ctx context.Context, caseID, filename, storagePath string) (documents.Document, error) {
	id := uuid.New()
	const q = `
		INSERT INTO documents (id, case_id, filename, storage_path, status)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, case_id, filename, storage_path, status, file_hash, text_hash, created_at, updated_at`
	return r.scanDocument(r.pool.QueryRow(ctx, q,
		id, caseID, filename, storagePath, documents.StatusProcessing))
}

// SetStoragePath updates the storage path after the file is written to disk.
func (r *Repository) SetStoragePath(ctx context.Context, id uuid.UUID, path string) error {
	const q = `UPDATE documents SET storage_path = $2, updated_at = now() WHERE id = $1`
	_, err := r.pool.Exec(ctx, q, id, path)
	return err
}

// UpdateStatus updates a document's processing status.
func (r *Repository) UpdateStatus(ctx context.Context, id uuid.UUID, status string) error {
	const q = `UPDATE documents SET status = $2, updated_at = now() WHERE id = $1`
	_, err := r.pool.Exec(ctx, q, id, status)
	return err
}

// GetDocument fetches a single document by id.
func (r *Repository) GetDocument(ctx context.Context, id uuid.UUID) (documents.Document, error) {
	const q = `
		SELECT id, case_id, filename, storage_path, status, file_hash, text_hash, created_at, updated_at
		FROM documents WHERE id = $1`
	doc, err := r.scanDocument(r.pool.QueryRow(ctx, q, id))
	if errors.Is(err, pgx.ErrNoRows) {
		return documents.Document{}, ErrNotFound
	}
	return doc, err
}

// GetMatches returns all matches where the given document is the source.
func (r *Repository) GetMatches(ctx context.Context, sourceID uuid.UUID) ([]documents.Match, error) {
	const q = `
		SELECT matched_document_id, relation_type,
		       COALESCE(near_duplicate_score, 0), COALESCE(semantic_score, 0),
		       COALESCE(reason, ''), COALESCE(evidence, '[]'::jsonb), created_at
		FROM document_matches
		WHERE source_document_id = $1
		ORDER BY near_duplicate_score DESC NULLS LAST, semantic_score DESC NULLS LAST`
	rows, err := r.pool.Query(ctx, q, sourceID)
	if err != nil {
		return nil, fmt.Errorf("query matches: %w", err)
	}
	defer rows.Close()

	matches := []documents.Match{}
	for rows.Next() {
		var m documents.Match
		if err := rows.Scan(&m.MatchedDocumentID, &m.RelationType, &m.NearDuplicateScore,
			&m.SemanticScore, &m.Reason, &m.Evidence, &m.CreatedAt); err != nil {
			return nil, fmt.Errorf("scan match: %w", err)
		}
		matches = append(matches, m)
	}
	return matches, rows.Err()
}

func (r *Repository) scanDocument(row pgx.Row) (documents.Document, error) {
	var d documents.Document
	err := row.Scan(&d.ID, &d.CaseID, &d.Filename, &d.StoragePath, &d.Status,
		&d.FileHash, &d.TextHash, &d.CreatedAt, &d.UpdatedAt)
	return d, err
}
