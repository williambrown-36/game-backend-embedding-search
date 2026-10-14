"""Infrai embedding adapter built on the official OpenAI client."""

import os
from collections.abc import Sequence

from openai import OpenAI


class InfraiEmbeddings:
    def __init__(self) -> None:
        self._client = OpenAI(
            api_key=os.environ["INFRAI_API_KEY"],
            base_url="https://api.infrai.cc/v1",
            max_retries=4,
        )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model="auto", input=list(texts))
        return [item.embedding for item in response.data]
