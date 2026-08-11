"""Lightweight hashed n-gram embeddings (no model download required)."""

from __future__ import annotations

import hashlib
import math
import re

_WS = re.compile(r"\s+")
DIM = 384


def embed(text: str, *, dim: int = DIM) -> list[float]:
    vec = [0.0] * dim
    normalized = _WS.sub(" ", (text or "").lower()).strip()
    if not normalized:
        return vec
    tokens = [normalized, *normalized.split()]
    for token in tokens:
        for n in (2, 3, 4):
            if len(token) < n:
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "little") % dim
                vec[idx] += 1.0
                continue
            for i in range(len(token) - n + 1):
                gram = token[i : i + n]
                digest = hashlib.sha256(gram.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "little") % dim
                vec[idx] += 1.0 / n
    return _l2(vec)


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _l2(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]
