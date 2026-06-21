package api

import (
	"context"
	"errors"
	"log"
	"net/http"
	"path/filepath"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"juridicflow/internal/config"
	"juridicflow/internal/documents"
	"juridicflow/internal/queue"
	"juridicflow/internal/repository"
	"juridicflow/internal/storage"
)

// Handler bundles the dependencies needed to serve the document API.
type Handler struct {
	cfg     config.Config
	repo    *repository.Repository
	store   storage.Storage
	pub     *queue.Publisher
}

func NewHandler(cfg config.Config, repo *repository.Repository, store storage.Storage, pub *queue.Publisher) *Handler {
	return &Handler{cfg: cfg, repo: repo, store: store, pub: pub}
}

// Register wires the routes onto the given gin engine.
func (h *Handler) Register(r *gin.Engine) {
	r.GET("/health", func(c *gin.Context) { c.JSON(http.StatusOK, gin.H{"status": "ok"}) })
	r.POST("/documents", h.createDocument)
	r.GET("/documents/:id", h.getDocument)
	r.GET("/documents/:id/matches", h.getMatches)
}

// createDocument handles multipart upload, persists the file + row and enqueues a job.
func (h *Handler) createDocument(c *gin.Context) {
	caseID := strings.TrimSpace(c.PostForm("case_id"))
	if caseID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "case_id is required"})
		return
	}

	fileHeader, err := c.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "file is required"})
		return
	}

	// Validate size.
	if fileHeader.Size <= 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "file is empty"})
		return
	}
	if fileHeader.Size > h.cfg.MaxUploadBytes {
		c.JSON(http.StatusRequestEntityTooLarge, gin.H{"error": "file exceeds maximum allowed size"})
		return
	}

	// Validate extension.
	ext := strings.ToLower(filepath.Ext(fileHeader.Filename))
	if !h.cfg.AllowedExtensions[ext] {
		c.JSON(http.StatusUnsupportedMediaType, gin.H{
			"error": "unsupported file type", "extension": ext,
		})
		return
	}

	ctx := c.Request.Context()

	doc, err := h.repo.CreateDocument(ctx, caseID, fileHeader.Filename, "")
	if err != nil {
		log.Printf("create document row: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not create document"})
		return
	}

	storagePath, err := h.store.Save(doc.ID, fileHeader)
	if err != nil {
		log.Printf("save file: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not store file"})
		return
	}

	// Persist the storage path now that the file is on disk.
	if err := h.repo.SetStoragePath(ctx, doc.ID, storagePath); err != nil {
		log.Printf("set storage path: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not update document"})
		return
	}
	doc.StoragePath = storagePath

	job := documents.Job{
		DocumentID:  doc.ID,
		CaseID:      caseID,
		StoragePath: storagePath,
		Filename:    fileHeader.Filename,
	}
	if err := h.pub.Publish(ctx, job); err != nil {
		// The file is saved but the job could not be queued; mark FAILED so it is visible.
		log.Printf("publish job: %v", err)
		_ = h.repo.UpdateStatus(context.Background(), doc.ID, documents.StatusFailed)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not enqueue processing job"})
		return
	}

	c.JSON(http.StatusAccepted, gin.H{
		"document_id": doc.ID,
		"status":      documents.StatusProcessing,
	})
}

func (h *Handler) getDocument(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid document id"})
		return
	}
	doc, err := h.repo.GetDocument(c.Request.Context(), id)
	if errors.Is(err, repository.ErrNotFound) {
		c.JSON(http.StatusNotFound, gin.H{"error": "document not found"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not fetch document"})
		return
	}
	c.JSON(http.StatusOK, doc)
}

func (h *Handler) getMatches(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid document id"})
		return
	}
	doc, err := h.repo.GetDocument(c.Request.Context(), id)
	if errors.Is(err, repository.ErrNotFound) {
		c.JSON(http.StatusNotFound, gin.H{"error": "document not found"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not fetch document"})
		return
	}

	matches, err := h.repo.GetMatches(c.Request.Context(), id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not fetch matches"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"document_id": doc.ID,
		"status":      doc.Status,
		"matches":     matches,
	})
}
