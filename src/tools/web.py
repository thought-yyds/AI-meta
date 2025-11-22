"""Tavily web content retrieval tool for LangChain agents."""

from __future__ import annotations

import os
from typing import Any, ClassVar, Optional, Type

from pydantic import BaseModel, Field

from .base import ContextAwareTool, ToolContext, ToolExecutionError

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


class TavilyWebInput(BaseModel):
    """Expected arguments for the Tavily web search tool."""

    query: str = Field(..., description="Web search query describing the information to retrieve.")
    search_depth: str = Field(
        "advanced",
        description="Search depth for Tavily. Supported values: 'basic' or 'advanced'.",
    )
    max_results: int = Field(
        5,
        description="Maximum number of results to return (1-10).",
    )
    include_answer: bool = Field(
        True,
        description="Include Tavily's synthesized answer when available.",
    )
    include_raw_content: bool = Field(
        False,
        description="If true, return the full content for each result. Otherwise return a shortened preview.",
    )


class TavilyWebTool(ContextAwareTool):
    """Fetch web content using the Tavily API."""

    name: str = "web_search"
    description: str = "Use Tavily to search the web and return structured page summaries and content."
    args_schema: ClassVar[Type[TavilyWebInput]] = TavilyWebInput

    def __init__(
        self,
        *,
        context: Optional[ToolContext] = None,
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(context=context, **kwargs)
        self._api_key = api_key or self._load_api_key()
        self._client = None

    def _load_api_key(self) -> Optional[str]:
        if load_dotenv is not None:
            load_dotenv(override=False)

        return os.getenv("TAVILY_API_KEY")

    def _ensure_client(self):
        if self._client is not None:
            return self._client

        if not self._api_key:
            raise ToolExecutionError(
                "Tavily API key is not configured. Set the 'TAVILY_API_KEY' environment variable."
            )

        try:
            from tavily import TavilyClient  # type: ignore
        except ImportError as exc:  # noqa: BLE001
            raise ToolExecutionError(
                "Missing dependency 'tavily'. Install it with 'pip install tavily'."
            ) from exc

        try:
            self._client = TavilyClient(api_key=self._api_key)
        except Exception as exc:  # noqa: BLE001
            raise ToolExecutionError(f"Failed to initialise Tavily client: {exc}") from exc

        return self._client

    def _run(
        self,
        query: str,
        search_depth: str = "advanced",
        max_results: int = 5,
        include_answer: bool = True,
        include_raw_content: bool = False,
    ) -> str:
        query = query.strip()
        if not query:
            raise ToolExecutionError("Parameter 'query' must be a non-empty string.")

        depth = search_depth.lower().strip()
        if depth not in {"basic", "advanced"}:
            raise ToolExecutionError("Parameter 'search_depth' must be either 'basic' or 'advanced'.")

        if not (1 <= max_results <= 10):
            raise ToolExecutionError("Parameter 'max_results' must be between 1 and 10.")

        client = self._ensure_client()

        try:
            response = client.search(
                query=query,
                search_depth=depth,
                max_results=max_results,
                include_answer=include_answer,
                include_raw_content=include_raw_content,
            )
        except Exception as exc:  # noqa: BLE001
            raise ToolExecutionError(f"Tavily search failed: {exc}") from exc

        results = []
        for item in response.get("results", [])[:max_results]:
            preview = item.get("content") or ""
            if not include_raw_content and preview:
                preview = preview[:500]
            results.append(
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "score": item.get("score"),
                    "content": preview,
                }
            )

        payload = {
            "query": query,
            "search_depth": depth,
            "results": results,
            "results_count": len(results),
        }

        if include_answer and response.get("answer"):
            payload["answer"] = response["answer"]

        if response.get("followup_questions"):
            payload["followup_questions"] = response["followup_questions"]

        return self._as_json(payload)

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("TavilyWebTool does not support async execution.")


