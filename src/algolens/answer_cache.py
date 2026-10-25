from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import time
from collections.abc import Mapping, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from algolens.answering import AnswerDraft, AnswerProvider
from algolens.contracts import APPROVED_REVIEW_STATUSES, Hit


class CachedAnswerProvider:
    """Cache structurally valid, evidence-bound answer drafts in SQLite.

    Cache keys include the question, partial-answer setting, model/corpus
    namespace, and the complete ordered evidence records. The raw question,
    evidence text, API keys, and other credentials are never written to disk.
    Only a SHA-256 key and validated answer draft are stored.

    The cache is an optimization, not an authority: every call must still
    supply explicitly answer-eligible evidence, and the outer AnswerService
    and grounding verifier continue to validate the resulting answer.
    """

    SCHEMA_VERSION = 1
    DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60
    DEFAULT_MAX_ENTRIES = 256

    def __init__(
        self,
        provider: AnswerProvider,
        *,
        corpus_version: str,
        model_id: str,
        cache_path: str | Path | None = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        if not corpus_version.strip():
            raise ValueError("corpus_version must not be empty.")
        if not model_id.strip():
            raise ValueError("model_id must not be empty.")
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds < 1:
            raise ValueError("ttl_seconds must be a positive integer.")
        if isinstance(max_entries, bool) or not isinstance(max_entries, int) or max_entries < 1:
            raise ValueError("max_entries must be a positive integer.")

        if cache_path is None:
            selected_path = Path(tempfile.gettempdir()) / "algolens" / "answers.sqlite3"
        else:
            if not str(cache_path).strip():
                raise ValueError("cache_path must not be blank.")
            selected_path = Path(cache_path).expanduser()

        self.provider = provider
        self.corpus_version = corpus_version.strip()
        self.model_id = model_id.strip()
        self.cache_path = selected_path
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries

    def _open_database(self) -> sqlite3.Connection:
        """Open the local cache with a short busy timeout and create its table."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.cache_path), timeout=2.0)
        try:
            connection.execute("PRAGMA busy_timeout = 2000")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS answer_cache (
                    cache_key TEXT PRIMARY KEY,
                    draft_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
        except Exception:
            connection.close()
            raise
        return connection

    def _cache_key(
        self,
        question: str,
        evidence: Sequence[Hit],
        *,
        allow_partial: bool,
    ) -> str:
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "corpus_version": self.corpus_version,
            "model_id": self.model_id,
            "question": question.strip(),
            "allow_partial": allow_partial,
            "evidence": [hit.model_dump(mode="json") for hit in evidence],
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _load(self, cache_key: str) -> AnswerDraft | None:
        """Load one unexpired, schema-valid response; cache faults fail open."""
        try:
            with closing(self._open_database()) as connection:
                with connection:
                    row = connection.execute(
                        "SELECT draft_json, created_at FROM answer_cache WHERE cache_key = ?",
                        (cache_key,),
                    ).fetchone()
                    if row is None:
                        return None

                    draft_json, created_at = row
                    if time.time() - float(created_at) > self.ttl_seconds:
                        connection.execute(
                            "DELETE FROM answer_cache WHERE cache_key = ?",
                            (cache_key,),
                        )
                        return None

                    try:
                        return AnswerDraft.model_validate_json(str(draft_json))
                    except (ValidationError, ValueError, TypeError):
                        connection.execute(
                            "DELETE FROM answer_cache WHERE cache_key = ?",
                            (cache_key,),
                        )
                        return None
        except (OSError, sqlite3.Error, TypeError, ValueError):
            # A cache outage must not prevent a fresh generation attempt.
            return None

    def _store(self, cache_key: str, draft: AnswerDraft) -> None:
        """Store a validated draft and prune expired/old entries best-effort."""
        now = time.time()
        try:
            with closing(self._open_database()) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO answer_cache (cache_key, draft_json, created_at)
                        VALUES (?, ?, ?)
                        """,
                        (cache_key, draft.model_dump_json(), now),
                    )
                    connection.execute(
                        "DELETE FROM answer_cache WHERE created_at < ?",
                        (now - self.ttl_seconds,),
                    )
                    connection.execute(
                        """
                        DELETE FROM answer_cache
                        WHERE cache_key IN (
                            SELECT cache_key FROM answer_cache
                            ORDER BY created_at DESC
                            LIMIT -1 OFFSET ?
                        )
                        """,
                        (self.max_entries,),
                    )
        except (OSError, sqlite3.Error, TypeError, ValueError):
            # Cache storage is optional; do not turn a successful model answer
            # into a failure just because the local cache is unavailable.
            return

    @staticmethod
    def _validate_evidence(evidence: Sequence[Hit]) -> set[str]:
        if not evidence:
            raise ValueError("At least one approved evidence passage is required.")

        ids: set[str] = set()
        for hit in evidence:
            passage = hit.passage
            if (
                passage.eligible_for_answer is not True
                or passage.review_status.strip().casefold() not in APPROVED_REVIEW_STATUSES
            ):
                raise ValueError("Cached generation requires explicitly approved evidence.")
            if passage.id in ids:
                raise ValueError("Evidence contains duplicate passage IDs.")
            ids.add(passage.id)
        return ids

    def generate(
        self,
        question: str,
        evidence: Sequence[Hit],
        *,
        allow_partial: bool,
    ) -> AnswerDraft:
        """Return a cache hit when its full evidence-bound key matches."""
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string.")
        if not isinstance(allow_partial, bool):
            raise ValueError("allow_partial must be a boolean.")

        evidence_ids = self._validate_evidence(evidence)
        cache_key = self._cache_key(question, evidence, allow_partial=allow_partial)
        cached = self._load(cache_key)
        if cached is not None:
            cited_ids = {passage_id for claim in cached.claims for passage_id in claim.cites}
            if cited_ids.issubset(evidence_ids):
                return cached

        raw_draft = self.provider.generate(
            question,
            evidence,
            allow_partial=allow_partial,
        )
        draft = AnswerDraft.model_validate(raw_draft)
        cited_ids = {passage_id for claim in draft.claims for passage_id in claim.cites}
        if not cited_ids.issubset(evidence_ids):
            raise ValueError("Provider draft cites passage IDs absent from supplied evidence.")

        self._store(cache_key, draft)
        return draft
