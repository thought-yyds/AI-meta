"""Local retrieval tool for searching project files (LangChain-compatible)."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import ClassVar, List, Optional, Sequence, Set, Tuple, Type

from pydantic import BaseModel, Field

from .base import ContextAwareTool, ToolExecutionError


DEFAULT_EXTENSIONS = {".txt", ".md", ".rst", ".py", ".json", ".yaml", ".yml"}


class LocalRetrievalInput(BaseModel):
    """Schema describing the expected arguments for the retrieval tool."""

    query: str = Field(..., description="Query string to search for.")
    search_dir: Optional[str] = Field(
        None, description="Directory to search (defaults to the agent working directory)."
    )
    extensions: Optional[Sequence[str]] = Field(
        None, description="Optional list of allowed file extensions."
    )
    top_k: int = Field(5, description="Maximum number of matches to return.")
    max_files: int = Field(200, description="Maximum number of files to scan.")


class LocalRetrievalTool(ContextAwareTool):
    """Perform a lightweight lexical search over local text files."""

    name: str = "retrieval"
    description: str = (
        "Search local text files for a query string and return the top matches with context."
    )
    args_schema: ClassVar[Type[LocalRetrievalInput]] = LocalRetrievalInput

    def _run(
        self,
        query: str,
        search_dir: Optional[str] = None,
        extensions: Optional[Sequence[str]] = None,
        top_k: int = 5,
        max_files: int = 200,
    ) -> str:
        query = query.strip()
        if not query:
            raise ToolExecutionError("Parameter 'query' must be a non-empty string.")
        if top_k <= 0:
            raise ToolExecutionError("Parameter 'top_k' must be a positive integer.")
        if max_files <= 0:
            raise ToolExecutionError("Parameter 'max_files' must be a positive integer.")

        working_dir = Path(self.context.working_dir or Path.cwd()).resolve()
        search_root = (working_dir / search_dir).resolve() if search_dir else working_dir

        if not search_root.exists():
            raise ToolExecutionError(f"Search directory not found: {search_root}")

        allowed_exts: Set[str]
        if extensions is None:
            allowed_exts = DEFAULT_EXTENSIONS
        else:
            allowed_exts = {str(ext).lower() for ext in extensions}

        matches: List[Tuple[Path, int, List[str]]] = []
        query_lower = query.lower()

        scanned = 0
        for path in itertools.islice(search_root.rglob("*"), max_files):
            if not path.is_file():
                continue
            if path.suffix.lower() not in allowed_exts:
                continue
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            except OSError:
                continue

            count = text.lower().count(query_lower)
            if count == 0:
                continue

            snippets = self._extract_snippets(text, query, max_snippets=3)
            matches.append((path, count, snippets))
            if len(matches) >= top_k:
                break

        results = [
            {
                "path": str(path),
                "occurrences": count,
                "snippets": snippets,
            }
            for path, count, snippets in matches
        ]

        return self._as_json(
            {
                "query": query,
                "results": results,
                "scanned_files": scanned,
            }
        )

    @staticmethod
    def _extract_snippets(
        text: str, query: str, *, max_snippets: int = 3, window: int = 80
    ) -> List[str]:
        lowered = text.lower()
        query_lower = query.lower()
        snippets: List[str] = []
        start = 0
        for _ in range(max_snippets):
            idx = lowered.find(query_lower, start)
            if idx == -1:
                break
            snippet_start = max(0, idx - window)
            snippet_end = min(len(text), idx + len(query) + window)
            snippet = text[snippet_start:snippet_end].replace("\n", " ")
            snippets.append(snippet)
            start = idx + len(query)
        return snippets

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("LocalRetrievalTool does not support async execution.")

