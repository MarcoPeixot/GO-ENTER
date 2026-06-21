"""Centralised configuration loaded from environment variables.

All similarity thresholds live here so they can be calibrated without code
changes (override via environment / docker-compose).
"""
import os


def _env(key: str, default: str) -> str:
    val = os.getenv(key)
    return val if val not in (None, "") else default


def _envf(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default


def _envi(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


# --- infrastructure ---
DATABASE_URL = _env("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/juridicflow")
RABBITMQ_URL = _env("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
QUEUE_NAME = _env("QUEUE_NAME", "document_jobs")

# --- embeddings ---
EMBEDDING_MODEL = _env("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
EMBEDDING_DIM = _envi("EMBEDDING_DIM", 384)

# --- chunking ---
CHUNK_MIN_WORDS = _envi("CHUNK_MIN_WORDS", 500)
CHUNK_MAX_WORDS = _envi("CHUNK_MAX_WORDS", 800)
CHUNK_OVERLAP_WORDS = _envi("CHUNK_OVERLAP_WORDS", 50)

# --- fingerprinting ---
SHINGLE_SIZE = _envi("SHINGLE_SIZE", 5)
MINHASH_PERM = _envi("MINHASH_PERM", 128)

# --- candidate selection ---
TOP_CANDIDATES = _envi("TOP_CANDIDATES", 5)
VECTOR_SEARCH_LIMIT = _envi("VECTOR_SEARCH_LIMIT", 50)

# --- classification thresholds ---
MINHASH_NEAR_DUP = _envf("MINHASH_NEAR_DUP", 0.80)
CHUNK_SIM_THRESHOLD = _envf("CHUNK_SIM_THRESHOLD", 0.80)
CHUNK_SIM_FRACTION = _envf("CHUNK_SIM_FRACTION", 0.60)
SEMANTIC_RELATED = _envf("SEMANTIC_RELATED", 0.78)
MINHASH_SEMANTIC_MAX = _envf("MINHASH_SEMANTIC_MAX", 0.60)

# --- retries ---
MAX_RETRIES = _envi("MAX_RETRIES", 3)
RETRY_BACKOFF_SECONDS = _envf("RETRY_BACKOFF_SECONDS", 2.0)

# --- LLM (optional) ---
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = _env("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = _env("LLM_MODEL", "gpt-4o-mini")
LLM_ENABLED = bool(LLM_API_KEY)
