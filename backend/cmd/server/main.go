package main

import (
	"context"
	"log"
	"time"

	"github.com/gin-gonic/gin"

	"juridicflow/internal/api"
	"juridicflow/internal/config"
	"juridicflow/internal/queue"
	"juridicflow/internal/repository"
	"juridicflow/internal/storage"
)

func main() {
	cfg := config.Load()

	ctx := context.Background()

	repo := mustRepo(ctx, cfg.DatabaseURL)
	defer repo.Close()

	pub := mustPublisher(cfg.RabbitMQURL, cfg.QueueName)
	defer pub.Close()

	store, err := storage.NewLocalStorage(cfg.UploadDir)
	if err != nil {
		log.Fatalf("init storage: %v", err)
	}

	r := gin.Default()
	r.MaxMultipartMemory = 8 << 20 // 8 MiB buffered in memory; rest streamed to temp file.
	api.NewHandler(cfg, repo, store, pub).Register(r)

	log.Printf("backend listening on :%s (uploads=%s, queue=%s)", cfg.Port, cfg.UploadDir, cfg.QueueName)
	if err := r.Run(":" + cfg.Port); err != nil {
		log.Fatalf("server stopped: %v", err)
	}
}

// mustRepo retries the DB connection so the backend can start alongside Postgres in Compose.
func mustRepo(ctx context.Context, url string) *repository.Repository {
	var lastErr error
	for i := 0; i < 30; i++ {
		repo, err := repository.New(ctx, url)
		if err == nil {
			return repo
		}
		lastErr = err
		log.Printf("waiting for postgres (%d/30): %v", i+1, err)
		time.Sleep(2 * time.Second)
	}
	log.Fatalf("could not connect to postgres: %v", lastErr)
	return nil
}

// mustPublisher retries the RabbitMQ connection for the same reason.
func mustPublisher(url, queueName string) *queue.Publisher {
	var lastErr error
	for i := 0; i < 30; i++ {
		pub, err := queue.NewPublisher(url, queueName)
		if err == nil {
			return pub
		}
		lastErr = err
		log.Printf("waiting for rabbitmq (%d/30): %v", i+1, err)
		time.Sleep(2 * time.Second)
	}
	log.Fatalf("could not connect to rabbitmq: %v", lastErr)
	return nil
}
