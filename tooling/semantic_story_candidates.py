#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from typing import Protocol
from urllib import error, request


class StoryLike(Protocol):
    url: str
    title: str
    lede: str
    summary: str
    body_preview: str
    named_entities: list[str]
    event_tags: set[str]


def normalize_embedding_text(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s-]", " ", text.lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def dedupe_segments(segments: list[str], *, limit: int) -> list[str]:
    kept: list[str] = []
    seen: set[str] = set()
    for segment in segments:
        normalized = normalize_embedding_text(segment)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        kept.append(segment.strip())
        if len(kept) >= limit:
            break
    return kept


def summarize_embedding_body(text: str) -> str:
    if not text:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    useful = [
        sentence
        for sentence in sentences
        if len(sentence.strip()) >= 50
        and "newsletter" not in sentence.lower()
        and "all rights reserved" not in sentence.lower()
    ]
    return " ".join(dedupe_segments(useful, limit=3))


def build_story_embedding_text(item: StoryLike) -> str:
    narrative_parts = dedupe_segments(
        [
            item.title,
            item.lede,
            item.summary,
            summarize_embedding_body(item.body_preview),
        ],
        limit=4,
    )
    parts = [
        " ".join(narrative_parts),
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


@dataclass
class SentenceTransformerEmbeddingProvider:
    model_name: str

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        try:
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Install it or use PRISM_EMBEDDING_PROVIDER=hashing."
            ) from exc

        model = SentenceTransformer(self.model_name)
        vectors = model.encode(texts, normalize_embeddings=True)
        return [list(vector) for vector in vectors]


@dataclass
class OpenAIEmbeddingProvider:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        payload = json.dumps({"input": texts, "model": self.model}).encode("utf-8")
        target = self.base_url.rstrip("/") + "/embeddings"
        http_request = request.Request(
            target,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=30) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:  # pragma: no cover - networked provider
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"embedding request failed with HTTP {exc.code}: {body}") from exc

        data = response_payload.get("data")
        if not isinstance(data, list):
            raise RuntimeError("embedding response missing data array")
        ordered = sorted(data, key=lambda row: row.get("index", 0))
        return [list(row.get("embedding", [])) for row in ordered]


def build_embedding_provider() -> EmbeddingProvider:
    provider = os.getenv("PRISM_EMBEDDING_PROVIDER", "hashing").strip().lower()
    if provider == "hashing":
        dimensions = int(os.getenv("PRISM_HASHING_EMBEDDING_DIMENSIONS", "384"))
        return HashingEmbeddingProvider(dimensions=dimensions)
    if provider in {"sentence-transformers", "sentence_transformers"}:
        model_name = os.getenv("PRISM_SENTENCE_TRANSFORMERS_MODEL", "all-MiniLM-L6-v2")
        return SentenceTransformerEmbeddingProvider(model_name=model_name)
    if provider == "openai":
        api_key = os.getenv("PRISM_OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("PRISM_OPENAI_API_KEY must be set when PRISM_EMBEDDING_PROVIDER=openai")
        model = os.getenv("PRISM_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
        base_url = os.getenv("PRISM_OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
        return OpenAIEmbeddingProvider(api_key=api_key, model=model, base_url=base_url)
    raise ValueError(
        f"Unsupported PRISM_EMBEDDING_PROVIDER '{provider}'. "
        "Use 'hashing', 'sentence-transformers', or 'openai'."
    )


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def build_similarity_lookup(
    items: list[StoryLike],
    *,
    top_k: int = 6,
    min_similarity: float | None = None,
) -> tuple[dict[str, list[str]], dict[tuple[str, str], float]]:
    if len(items) <= 1:
        return {}, {}

    if min_similarity is None:
        min_similarity = float(os.getenv("PRISM_SEMANTIC_MIN_SIMILARITY", "0.10"))

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
