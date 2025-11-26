"""FastMCP service that exposes GitHub helper tools."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional

import requests
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv(override=False)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_API_BASE = os.getenv("GITHUB_API_BASE", "https://api.github.com")

SESSION = requests.Session()
SESSION.headers.update(
    {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Personal-Agent-GitHub-Tool",
    }
)
if GITHUB_TOKEN:
    SESSION.headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

app = FastMCP("github-tools")


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


class RepoInfoSchema(BaseModel):
    owner: str = Field(..., description="GitHub owner/org name.")
    repo: str = Field(..., description="Repository name.")


@app.tool(name="github_repo_info")
def github_repo_info(owner: str, repo: str) -> Dict[str, object]:
    """Fetch metadata about a GitHub repository (stars, forks, open issues, description)."""
    try:
        params = RepoInfoSchema(owner=owner, repo=repo)
        url = f"{GITHUB_API_BASE}/repos/{params.owner}/{params.repo}"
        response = SESSION.get(url, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(f"GitHub API error ({response.status_code}): {response.text}")
        data = response.json()
        payload = {
            "full_name": data.get("full_name"),
            "description": data.get("description"),
            "stars": data.get("stargazers_count"),
            "forks": data.get("forks_count"),
            "open_issues": data.get("open_issues_count"),
            "default_branch": data.get("default_branch"),
            "url": data.get("html_url"),
            "topics": data.get("topics"),
            "license": data.get("license", {}).get("spdx_id") if data.get("license") else None,
            "updated_at": data.get("updated_at"),
        }
        return MCPResponse(ok=True, data=payload).to_dict()
    except ValidationError as exc:
        return MCPResponse(ok=False, error=str(exc)).to_dict()
    except Exception as exc:  # noqa: BLE001
        return MCPResponse(ok=False, error=str(exc)).to_dict()


class SearchCodeSchema(BaseModel):
    query: str = Field(..., description="Code search query. Supports qualifiers like repo:, language:, path:.")
    limit: int = Field(5, ge=1, le=30, description="Maximum number of matches to return.")


@app.tool(name="github_search_code")
def github_search_code(query: str, limit: int = 5) -> Dict[str, object]:
    """Search code on GitHub using the official search API."""
    try:
        params = SearchCodeSchema(query=query.strip(), limit=limit)
        if not params.query:
            raise ValueError("Parameter 'query' must be a non-empty string.")

        url = f"{GITHUB_API_BASE}/search/code"
        response = SESSION.get(url, params={"q": params.query, "per_page": params.limit}, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(f"GitHub API error ({response.status_code}): {response.text}")

        data = response.json()
        items = data.get("items", [])[: params.limit]
        results = [
            {
                "name": item.get("name"),
                "path": item.get("path"),
                "repository": item.get("repository", {}).get("full_name"),
                "html_url": item.get("html_url"),
                "score": item.get("score"),
            }
            for item in items
        ]
        return MCPResponse(ok=True, data={"query": params.query, "results": results}).to_dict()
    except ValidationError as exc:
        return MCPResponse(ok=False, error=str(exc)).to_dict()
    except Exception as exc:  # noqa: BLE001
        return MCPResponse(ok=False, error=str(exc)).to_dict()


if __name__ == "__main__":
    app.run()