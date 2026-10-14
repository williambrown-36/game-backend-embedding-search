"""Domain rules and an in-memory cosine index for game backend records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from math import sqrt
from typing import Protocol


class DocumentKind(str, Enum):
    PLAYER_ASSET = "player_asset"
    LIVE_EVENT = "live_event"
    MODERATION_ITEM = "moderation_item"


class ModerationState(str, Enum):
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"


class SearchAudience(str, Enum):
    PLAYER = "player"
    MODERATOR = "moderator"


@dataclass(frozen=True)
class GameDocument:
    document_id: str
    kind: DocumentKind
    title: str
    body: str
    moderation_state: ModerationState = ModerationState.APPROVED
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    def embedding_text(self) -> str:
        return f"{self.kind.value}: {self.title}\n{self.body}"


@dataclass(frozen=True)
class SearchHit:
    document_id: str
    kind: DocumentKind
    title: str
    score: float


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class GameDocumentIndex:
    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._documents: dict[str, GameDocument] = {}
        self._vectors: dict[str, list[float]] = {}

    def upsert(self, documents: list[GameDocument]) -> int:
        vectors = self._embedder.embed([document.embedding_text() for document in documents])
        if len(vectors) != len(documents):
            raise ValueError("embedding count does not match document count")
        for document, embedding in zip(documents, vectors, strict=True):
            self._documents[document.document_id] = document
            self._vectors[document.document_id] = embedding
        return len(documents)

    def search(
        self,
        query: str,
        audience: SearchAudience,
        limit: int,
        now: datetime | None = None,
    ) -> list[SearchHit]:
        query_vector = self._embedder.embed([query])[0]
        observed_at = now or datetime.now(timezone.utc)
        ranked = (
            SearchHit(document.document_id, document.kind, document.title, _cosine(query_vector, vector))
            for document_id, document in self._documents.items()
            if self._visible(document, audience, observed_at)
            for vector in [self._vectors[document_id]]
        )
        return sorted(ranked, key=lambda hit: (-hit.score, hit.document_id))[:limit]

    @staticmethod
    def _visible(document: GameDocument, audience: SearchAudience, now: datetime) -> bool:
        if audience is SearchAudience.PLAYER and document.moderation_state is not ModerationState.APPROVED:
            return False
        if document.kind is DocumentKind.MODERATION_ITEM:
            return audience is SearchAudience.MODERATOR
        if document.kind is DocumentKind.LIVE_EVENT:
            return (document.starts_at is None or document.starts_at <= now) and (
                document.ends_at is None or now < document.ends_at
            )
        return document.moderation_state is not ModerationState.REJECTED


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    denominator = sqrt(sum(value * value for value in left)) * sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator if denominator else 0.0
