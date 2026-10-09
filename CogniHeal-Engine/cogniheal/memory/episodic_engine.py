"""Hybrid ChromaDB + SQLite episodic memory engine.

The ``EpisodicMemoryEngine`` class is the central persistence layer of
CogniHeal.  Every error episode — including its raw traceback, root-cause
analysis, fix record and hard-constraint rule — is persisted in **two**
complementary stores:

1. **ChromaDB** — a vector database that enables fast approximate
   nearest-neighbour (ANN) retrieval by semantic similarity.
2. **SQLite** — a relational store that provides exact filtering,
   aggregation and full audit-trail queries.

Both stores are kept in sync: an ``upsert`` writes to both atomically
(best-effort), and ``query`` fans out to ChromaDB for similarity search
then enriches the results with relational metadata from SQLite.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

import chromadb
from chromadb.config import Settings as ChromaSettings

from cogniheal.config import settings
from cogniheal.memory.embeddings import generate_embedding
from cogniheal.memory.models import (
    EpisodicRecord,
    FixRecord,
    HardConstraintRule,
    RootCauseAnalysis,
    StackFrame,
)

logger = logging.getLogger(__name__)


# ── SQLite schema ──────────────────────────────────────────────────────────
_CREATE_EPISODES_TABLE = """
CREATE TABLE IF NOT EXISTS episodes (
    episode_id        TEXT PRIMARY KEY,
    timestamp         TEXT NOT NULL,
    original_code     TEXT NOT NULL,
    task_prompt       TEXT NOT NULL DEFAULT '',
    raw_error         TEXT NOT NULL,
    stack_frames_json TEXT NOT NULL DEFAULT '[]',
    rca_json          TEXT NOT NULL,
    reflection        TEXT NOT NULL DEFAULT '',
    fix_json          TEXT NOT NULL,
    constraint_json   TEXT NOT NULL,
    tags_json         TEXT NOT NULL DEFAULT '[]',
    success           INTEGER NOT NULL DEFAULT 0,
    total_iterations  INTEGER NOT NULL DEFAULT 1
);
"""

_CREATE_CONSTRAINTS_TABLE = """
CREATE TABLE IF NOT EXISTS hard_constraints (
    rule_id      TEXT PRIMARY KEY,
    episode_id   TEXT NOT NULL,
    description  TEXT NOT NULL,
    code_pattern TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id)
);
"""

_CREATE_FTS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts
USING fts5(episode_id, raw_error, rca_summary, fix_description);
"""


class EpisodicMemoryEngine:
    """Hybrid ChromaDB + SQLite episodic memory store.

    Usage::

        engine = EpisodicMemoryEngine()
        engine.initialise()
        engine.upsert(record)
        results = engine.query("TypeError in async handler", top_k=3)
        engine.close()
    """

    def __init__(
        self,
        data_dir: Path | None = None,
        sqlite_path: Path | None = None,
        chroma_persist_dir: Path | None = None,
        collection_name: str | None = None,
    ) -> None:
        """Initialize directory paths and connection placeholders.

        Args:
            data_dir: Base directory for storing memory files.
            sqlite_path: File path to SQLite database.
            chroma_persist_dir: Directory where ChromaDB indexes are kept.
            collection_name: Name of the Chroma collection.
        """
        self._data_dir = data_dir or settings.data_dir
        self._sqlite_path = sqlite_path or settings.sqlite_path
        self._chroma_dir = chroma_persist_dir or settings.chroma_persist_dir
        self._collection_name = collection_name or settings.chroma_collection_name

        self._conn: sqlite3.Connection | None = None
        self._chroma_client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    def __enter__(self) -> EpisodicMemoryEngine:
        """Enter context manager, ensuring connections are initialised."""
        self.initialise()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager, closing all connections cleanly."""
        self.close()

    # ── lifecycle ──────────────────────────────────────────────────────

    def initialise(self) -> None:
        """Create directories, open connections and ensure schemas exist."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._chroma_dir.mkdir(parents=True, exist_ok=True)

        # SQLite
        self._conn = sqlite3.connect(str(self._sqlite_path))
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.execute(_CREATE_EPISODES_TABLE)
        self._conn.execute(_CREATE_CONSTRAINTS_TABLE)
        try:
            self._conn.execute(_CREATE_FTS_TABLE)
        except sqlite3.OperationalError:
            pass  # FTS5 may not be available on every build
        self._conn.commit()

        # ChromaDB - Supports both modern ChromaDB (PersistentClient) and legacy (Client)
        try:
            self._chroma_client = chromadb.PersistentClient(
                path=str(self._chroma_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        except (AttributeError, ValueError, TypeError):
            self._chroma_client = chromadb.Client(
                ChromaSettings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=str(self._chroma_dir),
                    anonymized_telemetry=False,
                )
            )

        self._collection = self._chroma_client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "EpisodicMemoryEngine initialised  "
            "(sqlite=%s, chroma=%s, collection=%s)",
            self._sqlite_path,
            self._chroma_dir,
            self._collection_name,
        )

    def close(self) -> None:
        """Flush and close all connections."""
        if self._conn:
            self._conn.close()
            self._conn = None
        self._chroma_client = None
        self._collection = None
        logger.debug("EpisodicMemoryEngine closed.")

    # ── write ──────────────────────────────────────────────────────────

    def upsert(self, record: EpisodicRecord) -> None:
        """Persist an episodic record to both ChromaDB and SQLite.

        If the record's ``embedding_vector`` is empty, one is generated
        automatically from the semantic text.

        Args:
            record: A fully-populated ``EpisodicRecord``.
        """
        if not record.embedding_vector:
            record.embedding_vector = generate_embedding(record.to_semantic_text())

        self._upsert_sqlite(record)
        self._upsert_chroma(record)
        logger.info("Upserted episode %s", record.episode_id)

    def _upsert_sqlite(self, record: EpisodicRecord) -> None:
        """Write the record into the SQLite relational store."""
        assert self._conn is not None
        self._conn.execute(
            """
            INSERT OR REPLACE INTO episodes
                (episode_id, timestamp, original_code, task_prompt,
                 raw_error, stack_frames_json, rca_json, reflection,
                 fix_json, constraint_json, tags_json, success,
                 total_iterations)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.episode_id,
                record.timestamp.isoformat(),
                record.original_code,
                record.task_prompt,
                record.raw_error,
                json.dumps([sf.model_dump() for sf in record.stack_frames]),
                record.rca.model_dump_json(),
                record.reflection_reasoning,
                record.fix.model_dump_json(),
                record.hard_constraint.model_dump_json(),
                json.dumps(record.tags),
                int(record.success),
                record.total_iterations,
            ),
        )
        # hard constraint
        hc = record.hard_constraint
        self._conn.execute(
            """
            INSERT OR REPLACE INTO hard_constraints
                (rule_id, episode_id, description, code_pattern, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                hc.rule_id,
                record.episode_id,
                hc.description,
                hc.code_pattern,
                hc.created_at.isoformat(),
            ),
        )
        # FTS (best-effort)
        try:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO episodes_fts
                    (episode_id, raw_error, rca_summary, fix_description)
                VALUES (?, ?, ?, ?)
                """,
                (
                    record.episode_id,
                    record.raw_error[:2000],
                    record.rca.summary,
                    record.fix.description,
                ),
            )
        except sqlite3.OperationalError:
            pass
        self._conn.commit()

    def _upsert_chroma(self, record: EpisodicRecord) -> None:
        """Write the record into the ChromaDB vector store."""
        assert self._collection is not None
        self._collection.upsert(
            ids=[record.episode_id],
            embeddings=[record.embedding_vector],
            documents=[record.to_semantic_text()],
            metadatas=[
                {
                    "category": record.rca.category.value,
                    "severity": record.rca.severity.value,
                    "success": str(record.success),
                    "timestamp": record.timestamp.isoformat(),
                }
            ],
        )

    # ── read ───────────────────────────────────────────────────────────

    def query(
        self,
        query_text: str,
        top_k: int | None = None,
        min_similarity: float | None = None,
    ) -> list[EpisodicRecord]:
        """Retrieve the most relevant past episodes for *query_text*.

        Args:
            query_text: Natural-language description or raw error text.
            top_k: Number of results to return.
            min_similarity: Minimum cosine similarity threshold.

        Returns:
            A list of ``EpisodicRecord`` objects ordered by relevance.
        """
        top_k = top_k if top_k is not None else settings.top_k_memories
        min_similarity = (
            min_similarity
            if min_similarity is not None
            else settings.similarity_threshold
        )

        query_embedding = generate_embedding(query_text)
        return self.query_by_vector(query_embedding, top_k, min_similarity)

    def query_by_vector(
        self,
        embedding: list[float],
        top_k: int = 5,
        min_similarity: float = 0.0,
    ) -> list[EpisodicRecord]:
        """Retrieve episodes by raw embedding vector.

        Args:
            embedding: Pre-computed query embedding.
            top_k: Number of results.
            min_similarity: Cosine-similarity floor.

        Returns:
            Matching ``EpisodicRecord`` list.
        """
        assert self._collection is not None
        count = self._collection.count()
        if count == 0 or top_k <= 0:
            return []

        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, count),
        )
        if not results or not results["ids"] or not results["ids"][0]:
            return []

        ids = results["ids"][0]
        distances = results["distances"][0] if results.get("distances") else []

        records: list[EpisodicRecord] = []
        for idx, episode_id in enumerate(ids):
            similarity = 1.0 - distances[idx] if idx < len(distances) else 1.0
            if similarity < min_similarity:
                continue
            rec = self._load_from_sqlite(episode_id)
            if rec is not None:
                records.append(rec)
        return records

    def _load_from_sqlite(self, episode_id: str) -> EpisodicRecord | None:
        """Reconstruct a full ``EpisodicRecord`` from SQLite.

        Args:
            episode_id: Unique episode identifier to retrieve.

        Returns:
            The parsed ``EpisodicRecord`` or None if not found.
        """
        assert self._conn is not None
        cur = self._conn.execute(
            "SELECT * FROM episodes WHERE episode_id = ?", (episode_id,)
        )
        row = cur.fetchone()
        if row is None:
            return None

        columns = [desc[0] for desc in cur.description]
        data = dict(zip(columns, row))

        return EpisodicRecord(
            episode_id=data["episode_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            original_code=data["original_code"],
            task_prompt=data["task_prompt"],
            raw_error=data["raw_error"],
            stack_frames=[
                StackFrame(**sf) for sf in json.loads(data["stack_frames_json"])
            ],
            rca=RootCauseAnalysis.model_validate_json(data["rca_json"]),
            reflection_reasoning=data["reflection"],
            fix=FixRecord.model_validate_json(data["fix_json"]),
            hard_constraint=HardConstraintRule.model_validate_json(
                data["constraint_json"]
            ),
            tags=json.loads(data["tags_json"]),
            success=bool(data["success"]),
            total_iterations=data["total_iterations"],
        )

    # ── constraints ────────────────────────────────────────────────────

    def get_all_constraints(self) -> list[dict[str, Any]]:
        """Return every hard-constraint rule stored in SQLite.

        Returns:
            A list of dicts with keys ``rule_id``, ``description``,
            ``code_pattern`` and ``created_at``.
        """
        assert self._conn is not None
        cur = self._conn.execute(
            "SELECT rule_id, description, code_pattern, created_at "
            "FROM hard_constraints ORDER BY created_at DESC"
        )
        return [
            {
                "rule_id": r[0],
                "description": r[1],
                "code_pattern": r[2],
                "created_at": r[3],
            }
            for r in cur.fetchall()
        ]

    # ── search & delete ────────────────────────────────────────────────

    def search_fts(self, query_text: str, limit: int = 5) -> list[EpisodicRecord]:
        """Perform a full-text search across episodes using SQLite FTS5.

        Args:
            query_text: Search query string.
            limit: Maximum number of records to return.

        Returns:
            Matching ``EpisodicRecord`` objects.
        """
        assert self._conn is not None
        try:
            cur = self._conn.execute(
                """
                SELECT episode_id FROM episodes_fts
                WHERE episodes_fts MATCH ?
                LIMIT ?
                """,
                (query_text, limit),
            )
            records: list[EpisodicRecord] = []
            for (eid,) in cur.fetchall():
                rec = self._load_from_sqlite(eid)
                if rec:
                    records.append(rec)
            return records
        except sqlite3.OperationalError:
            return []

    def delete_episode(self, episode_id: str) -> bool:
        """Remove an episode by ID from both SQLite and ChromaDB stores.

        Args:
            episode_id: Unique episode identifier to delete.

        Returns:
            True if the episode was found and removed from SQLite, False otherwise.
        """
        assert self._conn is not None
        self._conn.execute(
            "DELETE FROM hard_constraints WHERE episode_id = ?", (episode_id,)
        )
        cur = self._conn.execute(
            "DELETE FROM episodes WHERE episode_id = ?", (episode_id,)
        )
        deleted = cur.rowcount > 0
        try:
            self._conn.execute(
                "DELETE FROM episodes_fts WHERE episode_id = ?", (episode_id,)
            )
        except sqlite3.OperationalError:
            pass
        self._conn.commit()

        if self._collection is not None:
            try:
                self._collection.delete(ids=[episode_id])
            except Exception:
                pass
        return deleted

    def clear(self) -> None:
        """Purge all records from both SQLite and ChromaDB stores."""
        if self._conn is not None:
            self._conn.execute("DELETE FROM hard_constraints")
            self._conn.execute("DELETE FROM episodes")
            try:
                self._conn.execute("DELETE FROM episodes_fts")
            except sqlite3.OperationalError:
                pass
            self._conn.commit()

        if self._chroma_client is not None and self._collection is not None:
            try:
                self._chroma_client.delete_collection(self._collection_name)
            except Exception:
                pass
            self._collection = self._chroma_client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        logger.info("EpisodicMemoryEngine cleared.")

    # ── stats ──────────────────────────────────────────────────────────

    def count_episodes(self) -> int:
        """Return the total number of stored episodes."""
        assert self._conn is not None
        cur = self._conn.execute("SELECT COUNT(*) FROM episodes")
        row = cur.fetchone()
        return row[0] if row else 0

    def count_constraints(self) -> int:
        """Return the total number of hard-constraint rules."""
        assert self._conn is not None
        cur = self._conn.execute("SELECT COUNT(*) FROM hard_constraints")
        row = cur.fetchone()
        return row[0] if row else 0

    def recent_episodes(self, limit: int = 10) -> list[EpisodicRecord]:
        """Return the *limit* most recent episodes.

        Args:
            limit: Maximum number of recent episodes to return.

        Returns:
            List of ``EpisodicRecord`` objects ordered newest first.
        """
        assert self._conn is not None
        cur = self._conn.execute(
            "SELECT episode_id FROM episodes ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        records: list[EpisodicRecord] = []
        for (eid,) in cur.fetchall():
            rec = self._load_from_sqlite(eid)
            if rec:
                records.append(rec)
        return records
