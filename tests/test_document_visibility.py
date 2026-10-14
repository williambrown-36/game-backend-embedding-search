from datetime import datetime, timedelta, timezone

from game_backend_search.document_index import (
    DocumentKind,
    GameDocument,
    GameDocumentIndex,
    ModerationState,
    SearchAudience,
)


class FixedEmbedder:
    vectors = {
        "dragon skin": [1.0, 0.0],
        "player_asset: Approved dragon\nred dragon skin": [0.9, 0.1],
        "player_asset: Pending dragon\nrare dragon skin": [1.0, 0.0],
        "live_event: Finished raid\ndragon raid": [0.95, 0.05],
        "moderation_item: Review dragon\nreported dragon decal": [0.99, 0.01],
    }

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.vectors[text] for text in texts]


def test_player_search_excludes_pending_finished_and_queue_documents() -> None:
    now = datetime(2026, 9, 5, tzinfo=timezone.utc)
    index = GameDocumentIndex(FixedEmbedder())
    index.upsert(
        [
            GameDocument("asset-approved", DocumentKind.PLAYER_ASSET, "Approved dragon", "red dragon skin"),
            GameDocument(
                "asset-pending",
                DocumentKind.PLAYER_ASSET,
                "Pending dragon",
                "rare dragon skin",
                ModerationState.PENDING,
            ),
            GameDocument(
                "event-finished",
                DocumentKind.LIVE_EVENT,
                "Finished raid",
                "dragon raid",
                ends_at=now - timedelta(minutes=1),
            ),
            GameDocument(
                "queue-review",
                DocumentKind.MODERATION_ITEM,
                "Review dragon",
                "reported dragon decal",
                ModerationState.PENDING,
            ),
        ]
    )

    player_hits = index.search("dragon skin", SearchAudience.PLAYER, limit=10, now=now)
    moderator_hits = index.search("dragon skin", SearchAudience.MODERATOR, limit=10, now=now)

    assert [hit.document_id for hit in player_hits] == ["asset-approved"]
    assert [hit.document_id for hit in moderator_hits] == [
        "asset-pending",
        "queue-review",
        "asset-approved",
    ]
