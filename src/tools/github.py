"""Helper utilities for interacting with the Smithery GitHub MCP server."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from .base import ContextAwareTool, ToolContext, ToolExecutionError
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, ContentBlock

DEFAULT_GITHUB_MCP_URL = ""


class GitHubMCPError(RuntimeError):
    """Raised when the MCP GitHub service cannot be used."""


class GitHubMCPClient:
    """Thin synchronous wrapper around the async MCP HTTP client."""

    def __init__(self, url: Optional[str] = None) -> None:
        candidate = url or os.getenv("GITHUB_MCP_URL") or DEFAULT_GITHUB_MCP_URL
        if candidate is None:
            candidate = ""
        endpoint = candidate.strip()
        if not endpoint:
            raise GitHubMCPError("GitHub MCP endpoint URL is not configured.")
        self._url = endpoint
        self._tool_cache: List[Dict[str, Any]] | None = None

    def list_tools_json(self, *, force_refresh: bool = False) -> str:
        """Return the available tools and their schemas as a JSON string."""
        tools = self._run_async(self._list_tools(force_refresh=force_refresh))
        return json.dumps({"tools": tools}, ensure_ascii=False)

    def call_tool_json(self, tool_name: str, arguments: Dict[str, Any] | None = None) -> str:
        """Call a remote tool and serialize the response to JSON."""
        payload = self._run_async(self._call_tool(tool_name, arguments or {}))
        return json.dumps(payload, ensure_ascii=False)

    async def _list_tools(self, *, force_refresh: bool = False) -> List[Dict[str, Any]]:
        if self._tool_cache is not None and not force_refresh:
            return self._tool_cache

        try:
            async with streamablehttp_client(self._url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
        except Exception as exc:  # noqa: BLE001
            raise GitHubMCPError(f"无法获取 GitHub MCP 工具列表：{exc}") from exc

        self._tool_cache = [
            {
                "name": tool.name,
                "title": getattr(tool.annotations, "title", None),
                "description": tool.description,
                "input_schema": tool.inputSchema,
                "output_schema": tool.outputSchema,
            }
            for tool in result.tools
        ]
        return self._tool_cache

    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        try:
            async with streamablehttp_client(self._url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments or None)
        except Exception as exc:  # noqa: BLE001
            raise GitHubMCPError(f"调用远程工具 {tool_name} 失败：{exc}") from exc

        return self._format_call_tool_result(tool_name, arguments, result)

    @staticmethod
    def _format_call_tool_result(
        tool_name: str,
        arguments: Dict[str, Any],
        result: CallToolResult,
    ) -> Dict[str, Any]:
        return {
            "tool": tool_name,
            "arguments": arguments,
            "is_error": result.isError,
            "text": _extract_text(result.content),
            "structured_content": result.structuredContent,
            "raw_content": [_dump_content_block(block) for block in result.content],
        }

    @staticmethod
    def _run_async(coro: Any) -> Any:
        try:
            return asyncio.run(coro)
        except RuntimeError as exc:
            # asyncio.run cannot be nested; fallback to a dedicated loop.
            if "asyncio.run()" in str(exc):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()
            raise


class GitHubMCPToolInput(BaseModel):
    """Arguments for the LangChain GitHub MCP tool wrapper."""

    tool_name: str = Field(
        default="",
        description="Name of the remote GitHub MCP tool to call (e.g. 'list_repos'). "
        "Leave empty to retrieve the available tool list.",
    )
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON-serialisable arguments to forward to the remote tool.",
    )
    refresh_tools: bool = Field(
        default=False,
        description="Force refresh of cached remote tool metadata before validating tool_name.",
    )


class GitHubRepoTool(ContextAwareTool):
    """LangChain tool that proxies calls to the Smithery GitHub MCP server."""

    name: str = "github_mcp_tool"
    description: str = (
        "Call the Smithery GitHub MCP service to inspect repositories. "
        "Use this tool to list repositories, fetch repo metadata, or search code owned by the "
        "configured GitHub account. Provide 'tool_name' (e.g. 'list_repos') and JSON 'arguments'. "
        "Leave 'tool_name' empty to fetch the available MCP tools."
    )
    args_schema: Type[BaseModel] = GitHubMCPToolInput

    def __init__(
        self,
        *,
        context: Optional[ToolContext] = None,
        client: Optional[GitHubMCPClient] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(context=context, **kwargs)
        self._client = client or GitHubMCPClient()
        self._cached_tools: Dict[str, Dict[str, Any]] | None = None

    def _run(
        self,
        tool_name: str = "",
        arguments: Optional[Dict[str, Any]] = None,
        refresh_tools: bool = False,
    ) -> str:
        tool_name = (tool_name or "").strip()
        arguments = arguments or {}

        if not isinstance(arguments, dict):
            raise ToolExecutionError("Parameter 'arguments' must be a JSON object.")

        tools = self._get_available_tools(force_refresh=refresh_tools)

        if not tool_name:
            return self._as_json(
                {
                    "available_tools": [
                        {
                            "name": name,
                            "description": meta.get("description"),
                            "title": meta.get("title"),
                        }
                        for name, meta in tools.items()
                    ],
                    "message": "Provide 'tool_name' to invoke a specific GitHub MCP tool.",
                }
            )

        if tool_name not in tools:
            return self._as_json(
                {
                    "available_tools": [
                        {
                            "name": name,
                            "description": meta.get("description"),
                            "title": meta.get("title"),
                        }
                        for name, meta in tools.items()
                    ],
                    "message": (
                        f"GitHub MCP tool '{tool_name}' is not available. "
                        "Choose one of the tools listed above."
                    ),
                }
            )

        try:
            return self._client.call_tool_json(tool_name, arguments)
        except GitHubMCPError as exc:
            return self._as_json(
                {
                    "tool": tool_name,
                    "arguments": arguments,
                    "error": str(exc),
                    "message": (
                        "GitHub MCP request failed. "
                        "Double-check the arguments or retry later. "
                        "Use 'refresh_tools': true if new tools were added."
                    ),
                }
            )

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("GitHubRepoTool does not support async execution.")

    def _get_available_tools(self, *, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        if self._cached_tools is not None and not force_refresh:
            return self._cached_tools

        try:
            payload = json.loads(self._client.list_tools_json(force_refresh=force_refresh))
        except GitHubMCPError as exc:
            raise ToolExecutionError(str(exc)) from exc

        tools = payload.get("tools") or []
        if not tools:
            raise ToolExecutionError("No GitHub MCP tools are available from the configured endpoint.")

        self._cached_tools = {tool["name"]: tool for tool in tools if "name" in tool}
        return self._cached_tools

def _dump_content_block(block: ContentBlock) -> Dict[str, Any]:
    if hasattr(block, "model_dump"):
        return block.model_dump(mode="python")
    if isinstance(block, dict):
        return block
    return {"value": str(block)}


def _extract_text(content: List[ContentBlock]) -> str:
    texts: List[str] = []
    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            texts.append(getattr(block, "text", ""))
        elif block_type == "resource":
            resource = getattr(block, "resource", None)
            if resource is None:
                continue
            text_value = getattr(resource, "text", None) or getattr(resource, "data", None)
            if isinstance(text_value, str):
                texts.append(text_value)
        elif block_type == "resource_link":
            uri = getattr(block, "uri", None)
            if uri:
                texts.append(f"[resource link] {uri}")
    return "\n".join(filter(None, texts)).strip()


async def _print_available_tools() -> None:
    client = GitHubMCPClient()
    data = json.loads(client.list_tools_json(force_refresh=True))
    names = ", ".join(tool["name"] for tool in data["tools"])
    print(f"Available tools: {names}")


if __name__ == "__main__":
    asyncio.run(_print_available_tools())