#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass
from typing import Protocol


class StoryLike(Protocol):
    url: str
    title: str
    lede: str
    summary: str
    named_entities: list[str]
    event_tags: set[str]


def normalize_embedding_text(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s-]", " ", text.lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def build_story_embedding_text(item: StoryLike) -> str:
    parts = [
        item.title,
        item.lede,
        item.summary,
        " ".join(item.named_entities[:6]),
        " ".join(sorted(item.event_tags)),
    ]
    return normalize_embedding_text(" ".join(part for part in parts if part))


def embedding_tokens(text: str) -> list[str]:
    words = [word for word in text.split() if len(word) >= 3]
    if not words:
        return []

    bigrams = [f"{left} {right}" for left, right in zip(words, words[1:])]
    return words + bigrams


class EmbeddingProvider(Protocol):
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        ...


@dataclass
class HashingEmbeddingProvider:
    dimensions: int = 384

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in embedding_tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.75 if " " in token else 1.0
            vector[index] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]


def build_embedding_provider() -> EmbeddingProvider:
    provider = os.getenv("PRISM_EMBEDDING_PROVIDER", "hashing").strip().lower()
    if provider == "hashing":
        dimensions = int(os.getenv("PRISM_HASHING_EMBEDDING_DIMENSIONS", "384"))
        return HashingEmbeddingProvider(dimensions=dimensions)
    raise ValueError(
        f"Unsupported PRISM_EMBEDDING_PROVIDER '{provider}'. "
        "Use 'hashing' for local development."
    )


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def build_similarity_lookup(
    items: list[StoryLike],
    *,
    top_k: int = 6,
    min_similarity: float = 0.14,
) -> tuple[dict[str, list[str]], dict[tuple[str, str], float]]:
    if len(items) <= 1:
        return {}, {}

    provider = build_embedding_provider()
    texts = [build_story_embedding_text(item) for item in items]
    vectors = provider.embed_many(texts)
    neighbor_lookup: dict[str, list[str]] = {}
    similarity_lookup: dict[tuple[str, str], float] = {}

    for index, item in enumerate(items):
        scored: list[tuple[str, float]] = []
        for other_index, other in enumerate(items):
            if index == other_index:
                continue
            similarity = cosine_similarity(vectors[index], vectors[other_index])
            if similarity < min_similarity:
                continue
            scored.append((other.url, similarity))
            similarity_lookup[(item.url, other.url)] = similarity
        scored.sort(key=lambda pair: pair[1], reverse=True)
        neighbor_lookup[item.url] = [url for url, _score in scored[:top_k]]

    return neighbor_lookup, similarity_lookup
