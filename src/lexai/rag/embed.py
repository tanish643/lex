"""Voyage AI embeddings wrapper.

voyage-law-2 is asymmetric: documents and queries must be embedded with
distinct input_type values. Getting this wrong silently degrades recall
by ~15-20% in our experience, so the parameter is required (no default).

The SDK accepts batches up to 128 texts per call; we enforce that to
avoid a silent truncation at the provider side.
"""

from __future__ import annotations

import os
from typing import Literal

import voyageai
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

MODEL = "voyage-law-2"
VOYAGE_DIM = 1024
MAX_BATCH = 128

InputType = Literal["document", "query"]
_VALID_INPUT_TYPES = ("document", "query")


@retry(
    retry=retry_if_exception_type(voyageai.error.RateLimitError),
    wait=wait_exponential(multiplier=10, min=20, max=120),
    stop=stop_after_attempt(6),
    reraise=True,
)
def _embed_batch(
    client: voyageai.Client, batch: list[str], input_type: InputType
) -> list[list[float]]:
    resp = client.embed(batch, model=MODEL, input_type=input_type)
    return resp.embeddings


def embed_texts(texts: list[str], *, input_type: InputType) -> list[list[float]]:
    if input_type not in _VALID_INPUT_TYPES:
        raise ValueError(
            f"input_type must be one of {_VALID_INPUT_TYPES}, got {input_type!r}"
        )
    if not texts:
        return []

    client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

    vectors: list[list[float]] = []
    for i in range(0, len(texts), MAX_BATCH):
        batch = texts[i : i + MAX_BATCH]
        vectors.extend(_embed_batch(client, batch, input_type))
    return vectors
