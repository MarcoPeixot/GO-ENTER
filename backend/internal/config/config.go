package config

import (
	"os"
	"strconv"
	"strings"
)

// Config holds all runtime configuration, loaded from environment variables.
type Config struct {
	Port             string
	DatabaseURL      string
	RabbitMQURL      string
	QueueName        string
	UploadDir        string
	MaxUploadBytes   int64
	AllowedExtensions map[string]bool
}

// Load reads configuration from the environment, applying sensible defaults
// so the service can boot in a local Docker Compose setup without extra wiring.
func Load() Config {
	cfg := Config{
		Port:           getEnv("PORT", "8080"),
		DatabaseURL:    getEnv("DATABASE_URL", "postgres://postgres:postgres@postgres:5432/juridicflow?sslmode=disable"),
		RabbitMQURL:    getEnv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/"),
		QueueName:      getEnv("QUEUE_NAME", "document_jobs"),
		UploadDir:      getEnv("UPLOAD_DIR", "/data/uploads"),
		MaxUploadBytes: getEnvInt64("MAX_UPLOAD_BYTES", 25*1024*1024), // 25 MiB
	}

	allowed := getEnv("ALLOWED_EXTENSIONS", ".txt,.pdf,.docx")
	cfg.AllowedExtensions = map[string]bool{}
	for _, ext := range strings.Split(allowed, ",") {
		ext = strings.TrimSpace(strings.ToLower(ext))
		if ext != "" {
			cfg.AllowedExtensions[ext] = true
		}
	}
	return cfg
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvInt64(key string, fallback int64) int64 {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil {
			return n
		}
	}
	return fallback
}
