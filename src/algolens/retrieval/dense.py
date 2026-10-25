from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

from algolens.retrieval.bm25 import is_answer_eligible

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class DenseIndex:
    """Dense cosine-similarity retrieval over provenance-preserving chunks."""

    def __init__(
        self,
        chunks: Sequence[Mapping[str, Any]],
        *,
        include_unreviewed: bool = False,
        model_name: str = DEFAULT_MODEL,
        device: str | None = None,
        encoder: Any | None = None,
        batch_size: int = 16,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1.")

        self.chunks: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for original in chunks:
            chunk = dict(original)
            chunk_id = str(chunk.get("chunk_id", "")).strip()

            if not chunk_id:
                raise ValueError("Every chunk must have a nonempty chunk_id.")
            if chunk_id in seen_ids:
                raise ValueError(f"Duplicate chunk ID: {chunk_id}")
            seen_ids.add(chunk_id)

            if not include_unreviewed and not is_answer_eligible(chunk):
                continue

            text = chunk.get("retrieval_text") or chunk.get("text") or ""
            if not isinstance(text, str):
                raise ValueError(f"Chunk {chunk_id} has invalid text.")
            if text.strip():
                self.chunks.append(chunk)

        self.encoder = encoder
        self.embeddings: NDArray[np.float32] | None = None
        self.device = "not-loaded"
        self.model_name = model_name

        # Keep the safe default cheap: an empty approved corpus should not
        # download a model just to return zero results.
        if not self.chunks:
            return

        if self.encoder is None:
            from sentence_transformers import SentenceTransformer

            kwargs: dict[str, Any] = {}
            if device is not None:
                kwargs["device"] = device
            self.encoder = SentenceTransformer(model_name, **kwargs)

        self.device = str(getattr(self.encoder, "device", "unknown"))

        texts = [
            str(chunk.get("retrieval_text") or chunk.get("text") or "") for chunk in self.chunks
        ]

        if hasattr(self.encoder, "encode_document"):
            raw_embeddings = self.encoder.encode_document(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        else:
            raw_embeddings = self.encoder.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )

        self.embeddings = self._normalize_rows(raw_embeddings)

        if self.embeddings.shape[0] != len(self.chunks):
            raise ValueError("Embedding count does not match the number of indexed chunks.")

    @staticmethod
    def _normalize_rows(values: Any) -> NDArray[np.float32]:
        matrix = np.asarray(values, dtype=np.float32)

        if matrix.ndim != 2:
            raise ValueError("Embeddings must be a two-dimensional matrix.")
        if matrix.shape[0] == 0 or matrix.shape[1] == 0:
            raise ValueError("Embeddings cannot have an empty dimension.")
        if not np.isfinite(matrix).all():
            raise ValueError("Embeddings contain non-finite values.")

        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        if np.any(norms <= 0):
            raise ValueError("Embedding vectors must have nonzero norms.")

        return np.asarray(matrix / norms, dtype=np.float32)

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search by cosine similarity; retain original provenance fields."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")
        if not query.strip() or self.embeddings is None or self.encoder is None:
            return []

        if hasattr(self.encoder, "encode_query"):
            raw_query = self.encoder.encode_query(
                [query],
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        else:
            raw_query = self.encoder.encode(
                [query],
                show_progress_bar=False,
                convert_to_numpy=True,
            )

        query_matrix = np.asarray(raw_query, dtype=np.float32)
        if query_matrix.ndim != 2 or query_matrix.shape[0] != 1 or query_matrix.shape[1] == 0:
            raise ValueError("The encoder must return one nonempty query embedding.")
        if not np.isfinite(query_matrix).all():
            raise ValueError("Query embedding contains non-finite values.")
        if np.linalg.norm(query_matrix[0]) <= 0:
            return []

        query_vector = self._normalize_rows(query_matrix)
        if query_vector.shape[1] != self.embeddings.shape[1]:
            raise ValueError("Query and document embedding dimensions differ.")

        scores = self.embeddings @ query_vector[0]
        order = np.argsort(-scores, kind="stable")[:top_k]

        results: list[dict[str, Any]] = []
        for index in order:
            result = dict(self.chunks[int(index)])
            result["score"] = float(scores[int(index)])
            result["eligible_for_answer"] = is_answer_eligible(result)
            result["retrieval_method"] = "dense"
            results.append(result)

        return results
