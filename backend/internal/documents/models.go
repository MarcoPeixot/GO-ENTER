package documents

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// Document status values shared with the worker.
const (
	StatusProcessing = "PROCESSING"
	StatusProcessed  = "PROCESSED"
	StatusFailed     = "FAILED"
	StatusNeedsOCR   = "NEEDS_OCR"
)

// Document is the API/DB representation of an uploaded legal document.
type Document struct {
	ID             uuid.UUID  `json:"document_id"`
	CaseID         string     `json:"case_id"`
	Filename       string     `json:"filename"`
	StoragePath    string     `json:"storage_path"`
	Status         string     `json:"status"`
	FileHash       *string    `json:"file_hash"`
	TextHash       *string    `json:"text_hash"`
	CreatedAt      time.Time  `json:"created_at"`
	UpdatedAt      time.Time  `json:"updated_at"`
}

// Match represents one similar document found for a source document.
type Match struct {
	MatchedDocumentID uuid.UUID       `json:"matched_document_id"`
	RelationType      string          `json:"relation_type"`
	NearDuplicateScore float64        `json:"near_duplicate_score"`
	SemanticScore     float64         `json:"semantic_score"`
	Reason            string          `json:"reason"`
	Evidence          json.RawMessage `json:"evidence"`
	CreatedAt         time.Time       `json:"created_at"`
}

// Job is the message published to RabbitMQ for the worker to process.
type Job struct {
	DocumentID  uuid.UUID `json:"document_id"`
	CaseID      string    `json:"case_id"`
	StoragePath string    `json:"storage_path"`
	Filename    string    `json:"filename"`
}
