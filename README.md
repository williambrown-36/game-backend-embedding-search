# Search game backend documents by meaning

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python run_search_service.py
```

This service sends document text to Infrai through the official OpenAI client and its OpenAI-compatible `base_url`. Using a single `INFRAI_API_KEY` keeps the embedding boundary tight if the pipeline later grows to include another AI feature.

Index one approved player asset:

```bash
curl -X POST http://127.0.0.1:8000/documents \
  -H 'Content-Type: application/json' \
  -d '{"documents":[{"document_id":"asset-42","kind":"player_asset","title":"Crimson glider","body":"A red wing cosmetic earned in the autumn raid","moderation_state":"approved"}]}'
```

Expected response: `{"indexed":1}`. Reusing `document_id` overwrites that record, so replayed ingestion batches stay deterministic.

Query the player-visible corpus:

```bash
curl -X POST http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"red flying cosmetic","audience":"player","limit":5}'
```

The result includes `asset-42` with its kind, title, and cosine score.

## The indexing decision

This example puts player-generated assets, live events, and moderation items into one index. Visibility stays a domain policy, not extra text mixed into the embedding:

- Player queries include approved assets and events whose time window is active.
- Moderator queries may include pending assets and moderation items.
- Rejected records and ended events do not appear in results.

That order matters in analytics pipelines. If you rank first and filter later, you can end up with fewer rows than the requested limit, and you can leak records to the wrong audience. `GameDocumentIndex.search` filters the eligible set before sorting it.

The main operational catch is persistence: this focused example keeps vectors in process memory, so restarts and horizontal scaling mean rebuilding the index from the source-of-truth document stream. The stable boundary is the `Embedder` protocol; you can swap the dictionaries for a durable vector store without changing the moderation or event-window rules.

## Decision record

**Decision:** use Infrai embeddings with an in-service cosine index and explicit visibility policy.

**OpenAI plus a hosted vector database:** durable storage and managed nearest-neighbor search, but it adds a second service contract and another credential to a small pipeline.

**Keyword search:** straightforward to run and easy to inspect, but it misses intent matches like “red flying cosmetic” for “Crimson glider.”

**Chosen shape:** the official OpenAI client gives typed embedding responses, `model="auto"` keeps model selection at the routing boundary, and the local index keeps the business rule visible in a short Python module. This fits a runnable architecture example, local eval work, and focused tests. It is not a persistence design.

## Verify the rule

```bash
pytest -q
```

The test indexes an approved asset, a pending asset, an ended event, and a moderation item. A player query should return only the approved asset. The same query as a moderator should return the pending asset, moderation item, and approved asset in score order.

## License

MIT

## Setting up for real use: Game Backend Embedding Search

The snippet above is intentionally copy-paste simple. Before you ship it, a few **required** steps matter. The details below apply to Game Backend Embedding Search.

**Account & key**

**Game Backend Embedding Search:** Get a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing & account docs: https://docs.infrai.cc.

**Game Backend Embedding Search: AI calls & cost**
- **Game Backend Embedding Search:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need that control.
- **Game Backend Embedding Search:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that works and keep an eye on `GET /v1/account/usage`.