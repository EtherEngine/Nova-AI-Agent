"""OpenAI embeddings access."""

from __future__ import annotations

from collections.abc import Sequence

from openai import AsyncOpenAI


async def embed_texts(
    client: AsyncOpenAI, model: str, texts: Sequence[str]
) -> list[list[float]]:
    """Return one embedding vector per input text (order preserved)."""
    if not texts:
        return []
    response = await client.embeddings.create(model=model, input=list(texts))
    return [item.embedding for item in response.data]


async def embed_query(client: AsyncOpenAI, model: str, query: str) -> list[float]:
    vectors = await embed_texts(client, model, [query])
    return vectors[0]
