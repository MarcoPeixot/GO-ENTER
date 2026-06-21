"""Hashes and MinHash fingerprints for fast duplicate / near-duplicate checks."""
import hashlib

import numpy as np
from datasketch import MinHash

from app import config


def file_sha256(path: str) -> str:
    """SHA-256 of the raw file bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def text_sha256(normalized_text: str) -> str:
    """SHA-256 of the normalized text."""
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def _shingles(text: str, size: int):
    """Word-level shingles (groups of `size` consecutive words)."""
    words = text.split()
    if len(words) < size:
        # Short docs: use the whole thing as a single shingle.
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + size]) for i in range(len(words) - size + 1)}


def build_minhash(masked_text: str) -> MinHash:
    """Build a MinHash from word shingles of the masked text."""
    m = MinHash(num_perm=config.MINHASH_PERM)
    for sh in _shingles(masked_text, config.SHINGLE_SIZE):
        m.update(sh.encode("utf-8"))
    return m


def minhash_to_list(m: MinHash) -> list[int]:
    """Serialize a MinHash signature to a JSON-friendly list of ints."""
    return [int(x) for x in m.hashvalues]


def minhash_from_list(values: list[int]) -> MinHash:
    """Rebuild a MinHash from a stored signature list.

    Uses the same default seed as build_minhash so jaccard() is comparable.
    """
    m = MinHash(num_perm=len(values))
    m.hashvalues = np.array(values, dtype=np.uint64)
    return m


def jaccard(a, b) -> float:
    """Estimated Jaccard similarity between two MinHash objects."""
    try:
        return float(a.jaccard(b))
    except Exception:
        return 0.0
