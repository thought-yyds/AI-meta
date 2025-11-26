"""LangChain tool that calls locally hosted FastMCP services."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, ClassVar

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import Tool
from pydantic import BaseModel, Field

from .base import ContextAwareTool, ToolContext, ToolExecutionError


BASE_DIR = Path(__file__).resolve().parent


@dataclass
class ServiceDefinition:
    name: str
    command: List[str]
    env: Optional[Dict[str, str]] = None


DEFAULT_SERVICES: List[ServiceDefinition] = [
    ServiceDefinition("file_parser_service", [sys.executable, str(BASE_DIR / "parser.py")]),
    ServiceDefinition("web_search_service", [sys.executable, str(BASE_DIR / "web.py")]),
    ServiceDefinition("calendar_service", [sys.executable, str(BASE_DIR / "calendar.py")]),
    ServiceDefinition("github_service", [sys.executable, str(BASE_DIR / "github.py")]),
    ServiceDefinition("qq_mail_service", [sys.executable, str(BASE_DIR / "QMailTool.py")]),
    ServiceDefinition("memory_service", [sys.executable, str(BASE_DIR / "memory.py")]),
    ServiceDefinition("amap_service", [sys.executable, str(BASE_DIR / "map.py")]),
]


class LocalMCPToolInput(BaseModel):
    tool_name: str = Field(..., description="Name of the MCP tool to invoke (e.g. 'file_parser').")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="JSON arguments to pass to the tool.")
    refresh_services: bool = Field(
        False,
        description="Force refresh of cached service metadata before invoking the tool.",
    )


class LocalMCPTool(ContextAwareTool):
    """Call locally hosted FastMCP services through a single LangChain tool."""

    name: str = "local_mcp_tool"
    description: str = (
        "Call locally hosted FastMCP services (file_parser, web_search, github_repo_info, github_search_code, "
        "add_calendar_event, send_mail, list_recent_mail, memory_search, plan_trip, etc.). "
        "Provide 'tool_name' and JSON 'arguments'."
    )
    args_schema: ClassVar[Type[LocalMCPToolInput]] = LocalMCPToolInput

    def __init__(
        self,
        *,
        service_definitions: Optional[List[ServiceDefinition]] = None,
        context: Optional[ToolContext] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(context=context, **kwargs)
        self._service_definitions = service_definitions or DEFAULT_SERVICES
        self._service_clients = [LocalMCPServiceClient(defn) for defn in self._service_definitions]
        self._tool_map: Dict[str, LocalMCPServiceClient] = {}

    def _run(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        refresh_services: bool = False,
    ) -> str:
        tool_name = (tool_name or "").strip()
        payload = arguments or {}

        if not tool_name:
            tools = self._list_all_tools(force_refresh=refresh_services)
            return self._as_json(
                {
                    "available_tools": tools,
                    "message": "Provide 'tool_name' to invoke a specific MCP tool.",
                }
            )

        if not isinstance(payload, dict):
            raise ToolExecutionError("Parameter 'arguments' must be a JSON object.")

        if refresh_services or tool_name not in self._tool_map:
            self._refresh_tool_map(force_refresh=refresh_services)

        service_client = self._tool_map.get(tool_name)
        if service_client is None:
            tools = self._list_all_tools(force_refresh=True)
            return self._as_json(
                {
                    "available_tools": tools,
                    "message": f"Tool '{tool_name}' is not available. Choose one of the tools listed above.",
                }
            )

        try:
            return service_client.call_tool_json(tool_name, payload)
        except ToolExecutionError as exc:
            return self._as_json({"tool": tool_name, "arguments": payload, "error": str(exc)})

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("LocalMCPTool does not support async execution.")

    def _refresh_tool_map(self, force_refresh: bool = False) -> None:
        self._tool_map.clear()
        for client in self._service_clients:
            try:
                tools = client.list_tools(force_refresh=force_refresh)
            except ToolExecutionError:
                continue
            for tool in tools:
                if tool.name:
                    self._tool_map[tool.name] = client

    def _list_all_tools(self, force_refresh: bool = False) -> List[Dict[str, str]]:
        tools: List[Dict[str, str]] = []
        for client in self._service_clients:
            try:
                for tool in client.list_tools(force_refresh=force_refresh):
                    tools.append({"name": tool.name, "description": tool.description or ""})
            except ToolExecutionError:
                continue
        return tools

    def list_available_tools(self, *, force_refresh: bool = False) -> List[Dict[str, str]]:
        """Public helper for callers that want to inspect available MCP tools."""
        return self._list_all_tools(force_refresh=force_refresh)


class LocalMCPServiceClient:
    """Small helper that spawns a FastMCP service via stdio and proxies requests."""

    def __init__(self, definition: ServiceDefinition) -> None:
        self.definition = definition
        self._tool_cache: Optional[List[Tool]] = None

    def list_tools(self, *, force_refresh: bool = False) -> List[Tool]:
        if self._tool_cache is not None and not force_refresh:
            return self._tool_cache

        try:
            tools = asyncio.run(self._list_tools())
        except RuntimeError:
            tools = self._run_in_loop(self._list_tools())

        self._tool_cache = tools
        return tools

    def call_tool_json(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        try:
            payload = asyncio.run(self._call_tool(tool_name, arguments))
        except RuntimeError:
            payload = self._run_in_loop(self._call_tool(tool_name, arguments))
        return json.dumps(payload, ensure_ascii=False)

    async def _list_tools(self) -> List[Tool]:
        params = self._server_parameters()
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return result.tools

    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        params = self._server_parameters()
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments or None)
                return {
                    "tool": tool_name,
                    "arguments": arguments,
                    "is_error": result.isError,
                    "content": [block.model_dump(mode="python") for block in result.content],
                    "structured_content": result.structuredContent,
                }

    def _server_parameters(self) -> StdioServerParameters:
        command, *args = self.definition.command
        return StdioServerParameters(command=command, args=args, env=self.definition.env)

    @staticmethod
    def _run_in_loop(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


