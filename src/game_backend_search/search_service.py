"""Typed HTTP boundary for indexing and searching game documents."""

from datetime import datetime

from fastapi import FastAPI, HTTPException
from openai import APIConnectionError, APIStatusError
from pydantic import BaseModel, Field

from .document_index import DocumentKind, GameDocument, GameDocumentIndex, ModerationState, SearchAudience
from .infrai_embeddings import InfraiEmbeddings


class DocumentInput(BaseModel):
    document_id: str = Field(min_length=1)
    kind: DocumentKind
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    moderation_state: ModerationState = ModerationState.APPROVED
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class IndexRequest(BaseModel):
    documents: list[DocumentInput] = Field(min_length=1, max_length=100)


class IndexResult(BaseModel):
    indexed: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    audience: SearchAudience = SearchAudience.PLAYER
    limit: int = Field(default=5, ge=1, le=20)


class SearchHitOutput(BaseModel):
    document_id: str
    kind: DocumentKind
    title: str
    score: float


def _upstream_error(error: APIStatusError) -> HTTPException:
    status = error.status_code if 400 <= error.status_code < 500 else 502
    return HTTPException(status_code=status, detail="embedding request was rejected")


def create_app(index: GameDocumentIndex | None = None) -> FastAPI:
    app = FastAPI(title="Game backend document search")
    document_index = index or GameDocumentIndex(InfraiEmbeddings())

    @app.post("/documents", response_model=IndexResult)
    def index_documents(request: IndexRequest) -> IndexResult:
        try:
            documents = [GameDocument(**item.model_dump()) for item in request.documents]
            return IndexResult(indexed=document_index.upsert(documents))
        except APIStatusError as error:
            raise _upstream_error(error) from error
        except APIConnectionError as error:
            raise HTTPException(status_code=502, detail="embedding request could not be completed") from error

    @app.post("/search", response_model=list[SearchHitOutput])
    def search_documents(request: SearchRequest) -> list[SearchHitOutput]:
        try:
            hits = document_index.search(request.query, request.audience, request.limit)
            return [SearchHitOutput(**hit.__dict__) for hit in hits]
        except APIStatusError as error:
            raise _upstream_error(error) from error
        except APIConnectionError as error:
            raise HTTPException(status_code=502, detail="embedding request could not be completed") from error

    return app


app = create_app()
