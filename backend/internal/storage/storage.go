package storage

import (
	"fmt"
	"io"
	"mime/multipart"
	"os"
	"path/filepath"
	"time"

	"github.com/google/uuid"
)

// Storage abstracts where uploaded files live. The MVP ships a local-volume
// implementation; swapping to S3 later only requires another implementation.
type Storage interface {
	// Save persists the uploaded file and returns its storage path/key.
	Save(documentID uuid.UUID, fileHeader *multipart.FileHeader) (string, error)
}

// LocalStorage writes files to a directory on a shared Docker volume.
type LocalStorage struct {
	baseDir string
}

func NewLocalStorage(baseDir string) (*LocalStorage, error) {
	if err := os.MkdirAll(baseDir, 0o755); err != nil {
		return nil, fmt.Errorf("create upload dir: %w", err)
	}
	return &LocalStorage{baseDir: baseDir}, nil
}

func (s *LocalStorage) Save(documentID uuid.UUID, fileHeader *multipart.FileHeader) (string, error) {
	src, err := fileHeader.Open()
	if err != nil {
		return "", fmt.Errorf("open upload: %w", err)
	}
	defer src.Close()

	// Partition by date to keep directories small and human-navigable.
	subDir := filepath.Join(s.baseDir, time.Now().UTC().Format("2006/01/02"))
	if err := os.MkdirAll(subDir, 0o755); err != nil {
		return "", fmt.Errorf("create sub dir: %w", err)
	}

	ext := filepath.Ext(fileHeader.Filename)
	destPath := filepath.Join(subDir, documentID.String()+ext)

	dst, err := os.Create(destPath)
	if err != nil {
		return "", fmt.Errorf("create dest file: %w", err)
	}
	defer dst.Close()

	if _, err := io.Copy(dst, src); err != nil {
		return "", fmt.Errorf("write dest file: %w", err)
	}
	return destPath, nil
}
