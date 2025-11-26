"""FastMCP service that provides hybrid memory search over historical messages."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import create_engine, text

try:
    import faiss  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Missing dependency 'faiss-cpu'. Install it with 'pip install faiss-cpu'.") from exc

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Missing dependency 'sentence-transformers'. Install it with 'pip install sentence-transformers'."
    ) from exc

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv(override=False)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_WORKDIR = Path(os.getenv("PERSONAL_AGENT_WORKDIR", BASE_DIR.parent)).resolve()

def _build_db_url() -> str:
    if url := os.getenv("MEMORY_DB_URL"):
        return url
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "mymeta")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


DEFAULT_DB_URL = _build_db_url()
DEFAULT_INDEX_DIR = Path(os.getenv("MEMORY_INDEX_DIR", DEFAULT_WORKDIR / "memory_index")).resolve()
DEFAULT_LOOKBACK_DAYS = int(os.getenv("MEMORY_LOOKBACK_DAYS", "30"))
DEFAULT_MAX_MESSAGES = int(os.getenv("MEMORY_MAX_MESSAGES", "5000"))
DEFAULT_EMBED_MODEL = os.getenv("MEMORY_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DEFAULT_REFRESH_INTERVAL_HOURS = float(os.getenv("MEMORY_REFRESH_INTERVAL_HOURS", "6"))

app = FastMCP("memory-service")


@dataclass
class MCPResponse:
    ok: bool
    data: Optional[Dict[str, object]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {"ok": self.ok}
        if self.data is not None:
            payload["data"] = self.data
        if self.error:
            payload["error"] = self.error
        return payload


class MemorySearchSchema(BaseModel):
    query: str = Field(..., description="Search query describing the memory to retrieve.")
    top_k: int = Field(5, ge=1, le=20, description="Maximum number of results to return.")
    min_score: float = Field(0.25, ge=0.0, le=1.0, description="Minimum cosine similarity score to keep.")


class MemoryIndex:
    def __init__(
        self,
        *,
        db_url: str,
        index_dir: Path,
        lookback_days: int,
        max_messages: int,
        embed_model_name: str,
        refresh_interval_hours: float,
    ) -> None:
        self.db_url = db_url
        self._engine = create_engine(
            self.db_url,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.index_dir = index_dir
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.lookback_days = lookback_days
        self.max_messages = max_messages
        self.embed_model_name = embed_model_name
        self.refresh_interval = timedelta(hours=refresh_interval_hours)

        self.index_file = self.index_dir / "memory.faiss"
        self.metadata_file = self.index_dir / "memory_metadata.json"

        self._lock = threading.Lock()
        self._model = SentenceTransformer(self.embed_model_name)
        self._dim = self._model.get_sentence_embedding_dimension()
        self._index: Optional[faiss.IndexFlatIP] = None
        self._documents: List[Dict[str, object]] = []
        self._built_at: Optional[datetime] = None

        self._load_or_build()

    def search(self, query: str, top_k: int, min_score: float) -> List[Dict[str, object]]:
        with self._lock:
            self._ensure_fresh_index()
            if not self._documents or self._index is None:
                return []

            embedding = self._encode([query])[0]
            scores, indices = self._index.search(np.array([embedding]), top_k)
            scored_results: List[Dict[str, object]] = []
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1 or score < min_score:
                    continue
                doc = self._documents[idx]
                scored_results.append(
                    {
                        "score": float(score),
                        "text": doc["text"],
                        "message_id": doc["message_id"],
                        "session_id": doc["session_id"],
                        "role": doc["role"],
                        "created_at": doc["created_at"],
                        "snippet": doc["snippet"],
                    }
                )
            return scored_results

    def refresh(self, force: bool = False) -> Dict[str, object]:
        with self._lock:
            self._build_index(force=force)
            return {
                "documents": len(self._documents),
                "built_at": self._built_at.isoformat() if self._built_at else None,
            }

    def _load_or_build(self) -> None:
        with self._lock:
            if self.index_file.exists() and self.metadata_file.exists():
                try:
                    self._load_index()
                except Exception:  # noqa: BLE001
                    self._build_index(force=True)
            else:
                self._build_index(force=True)

    def _ensure_fresh_index(self) -> None:
        if self._built_at is None:
            self._build_index(force=True)
            return
        if datetime.now(timezone.utc) - self._built_at > self.refresh_interval:
            self._build_index(force=True)

    def _build_index(self, force: bool) -> None:
        docs = self._fetch_documents()
        embeddings = self._encode([doc["text"] for doc in docs]) if docs else np.zeros((0, self._dim), dtype="float32")
        index = faiss.IndexFlatIP(self._dim)
        if embeddings.shape[0]:
            index.add(embeddings)
        self._index = index
        self._documents = docs
        self._built_at = datetime.now(timezone.utc)
        self._persist_index()

    def _load_index(self) -> None:
        self._index = faiss.read_index(str(self.index_file))
        with self.metadata_file.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        self._documents = payload.get("documents", [])
        built_at = payload.get("built_at")
        self._built_at = datetime.fromisoformat(built_at) if built_at else None

    def _persist_index(self) -> None:
        if self._index is not None:
            faiss.write_index(self._index, str(self.index_file))
        with self.metadata_file.open("w", encoding="utf-8") as fh:
            json.dump(
                {"built_at": self._built_at.isoformat() if self._built_at else None, "documents": self._documents},
                fh,
                ensure_ascii=False,
                indent=2,
            )

    def _encode(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype="float32")
        embeddings = self._model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.astype("float32")

    def _fetch_documents(self) -> List[Dict[str, object]]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
        query = """
            SELECT id, session_id, role, content, created_at
            FROM messages
            WHERE created_at IS NULL OR created_at >= :cutoff
            ORDER BY created_at DESC
            LIMIT :limit
        """
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(query),
                {"cutoff": cutoff_str, "limit": self.max_messages},
            ).mappings().all()

        documents: List[Dict[str, object]] = []
        for row in rows:
            content = (row["content"] or "").strip()
            if not content:
                continue
            created_at_value = row["created_at"]
            if isinstance(created_at_value, datetime):
                created_at = created_at_value.astimezone(timezone.utc).isoformat()
            else:
                created_at = str(created_at_value or "")
            text = f"[{row['role']}] {content}"
            snippets = content.splitlines()
            snippet = snippets[0][:200] if snippets else content[:200]
            documents.append(
                {
                    "message_id": row["id"],
                    "session_id": row["session_id"],
                    "role": row["role"],
                    "created_at": created_at,
                    "text": text,
                    "snippet": snippet,
                }
            )
        return list(reversed(documents))


memory_index = MemoryIndex(
    db_url=DEFAULT_DB_URL,
    index_dir=DEFAULT_INDEX_DIR,
    lookback_days=DEFAULT_LOOKBACK_DAYS,
    max_messages=DEFAULT_MAX_MESSAGES,
    embed_model_name=DEFAULT_EMBED_MODEL,
    refresh_interval_hours=DEFAULT_REFRESH_INTERVAL_HOURS,
)


@app.tool(name="memory_search")
def memory_search(query: str, top_k: int = 5, min_score: float = 0.25) -> Dict[str, object]:
    """Search historical conversations and notes (vectors + keyword snippets)."""
    try:
        params = MemorySearchSchema(query=query, top_k=top_k, min_score=min_score)
        results = memory_index.search(params.query, params.top_k, params.min_score)
        return MCPResponse(ok=True, data={"query": params.query, "results": results}).to_dict()
    except ValidationError as exc:
        return MCPResponse(ok=False, error=str(exc)).to_dict()
    except Exception as exc:  # noqa: BLE001
        return MCPResponse(ok=False, error=str(exc)).to_dict()


@app.tool(name="memory_refresh")
def memory_refresh() -> Dict[str, object]:
    """Force rebuild the memory vector index from the latest database contents."""
    try:
        stats = memory_index.refresh(force=True)
        return MCPResponse(ok=True, data=stats).to_dict()
    except Exception as exc:  # noqa: BLE001
        return MCPResponse(ok=False, error=str(exc)).to_dict()


if __name__ == "__main__":
    app.run()

