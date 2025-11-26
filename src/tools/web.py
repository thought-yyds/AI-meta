"""FastMCP service that exposes the Tavily web search tool."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv(override=False)

app = FastMCP("web-search")


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


class TavilyRequest(BaseModel):
    query: str = Field(..., description="Web search query.")
    search_depth: str = Field(
        "advanced",
        description="Search depth for Tavily. Supported values: 'basic' or 'advanced'.",
    )
    max_results: int = Field(5, ge=1, le=10, description="Maximum number of results to return (1-10).")
    include_answer: bool = Field(True, description="Include Tavily's synthesized answer when available.")
    include_raw_content: bool = Field(False, description="Return full content for each result.")


@app.tool(name="web_search")
def web_search(
    query: str,
    search_depth: str = "advanced",
    max_results: int = 5,
    include_answer: bool = True,
    include_raw_content: bool = False,
) -> Dict[str, object]:
    """Use Tavily to search the web and return structured page summaries and content."""
    try:
        params = TavilyRequest(
            query=query.strip(),
            search_depth=search_depth,
            max_results=max_results,
            include_answer=include_answer,
            include_raw_content=include_raw_content,
        )
        if not params.query:
            raise ValueError("Parameter 'query' must be a non-empty string.")

        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError("Environment variable TAVILY_API_KEY is not set.")

        try:
            from tavily import TavilyClient  # type: ignore
        except ImportError as exc:  # noqa: BLE001
            raise RuntimeError("Missing dependency 'tavily'. Install it with 'pip install tavily'.") from exc

        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=params.query,
            search_depth=params.search_depth,
            max_results=params.max_results,
            include_answer=params.include_answer,
            include_raw_content=params.include_raw_content,
        )

        data = {
            "query": params.query,
            "search_depth": params.search_depth,
            "results": [
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "score": item.get("score"),
                    "content": item.get("content") if params.include_raw_content else (item.get("content") or "")[:500],
                }
                for item in response.get("results", [])[: params.max_results]
            ],
        }

        if params.include_answer and response.get("answer"):
            data["answer"] = response["answer"]
        if response.get("followup_questions"):
            data["followup_questions"] = response["followup_questions"]

        return MCPResponse(ok=True, data=data).to_dict()
    except ValidationError as exc:
        return MCPResponse(ok=False, error=str(exc)).to_dict()
    except Exception as exc:  # noqa: BLE001
        return MCPResponse(ok=False, error=str(exc)).to_dict()


if __name__ == "__main__":
    app.run()


