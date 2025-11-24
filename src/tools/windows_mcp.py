"""Helper utilities for interacting with the WindowsMCP.Net MCP server."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import multiprocessing
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from .base import ContextAwareTool, ToolContext, ToolExecutionError

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.types import CallToolResult, ContentBlock
    # Try different import paths for stdio client
    try:
        from mcp.client.stdio import stdio_client
    except ImportError:
        try:
            from mcp.client import stdio_client
        except ImportError:
            # Fallback: use subprocess-based stdio
            stdio_client = None
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    stdio_client = None
    StdioServerParameters = None

# Try to find Windows-MCP.Net.exe in common locations
def _find_windows_mcp_exe() -> Optional[str]:
    """Try to find Windows-MCP.Net.exe in common locations."""
    # Common locations
    common_paths = [
        Path.home() / ".dotnet" / "tools" / "Windows-MCP.Net.exe",
        Path.home() / ".dotnet" / "tools" / "WindowsMCP.Net.exe",
        Path("C:/Program Files/dotnet/tools/Windows-MCP.Net.exe"),
        Path("C:/Program Files/dotnet/tools/WindowsMCP.Net.exe"),
    ]
    
    for path in common_paths:
        if path.exists():
            return str(path)
    
    # Try to find in PATH
    found = shutil.which("Windows-MCP.Net") or shutil.which("WindowsMCP.Net")
    if found:
        return found
    
    return None

# Try to use direct executable path first, fallback to dnx
_windows_mcp_exe = _find_windows_mcp_exe()
if _windows_mcp_exe:
    DEFAULT_WINDOWS_MCP_COMMAND = _windows_mcp_exe
    DEFAULT_WINDOWS_MCP_ARGS = []
else:
    DEFAULT_WINDOWS_MCP_COMMAND = "dnx"
    DEFAULT_WINDOWS_MCP_ARGS = ["WindowsMCP.Net@", "--yes"]

# Configure logging for MCP client to reduce noise from non-JSON output
# Windows-MCP.Net outputs progress messages (like "Downloading...", "Extracting...")
# to stdout, which causes JSONRPC parsing errors. These are harmless but noisy.
_mcp_logger = logging.getLogger("mcp.client.stdio")
# Set to WARNING level to suppress JSON parsing errors from progress messages
# These errors don't affect functionality - Windows-MCP.Net still works correctly
_mcp_logger.setLevel(logging.WARNING)


class WindowsMCPError(RuntimeError):
    """Raised when the WindowsMCP.Net service cannot be used."""


class WindowsMCPClient:
    """Thin synchronous wrapper around the async MCP stdio client."""

    def __init__(
        self,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        if not MCP_AVAILABLE:
            raise WindowsMCPError(
                "MCP Python SDK is not available. Please install it with: pip install mcp"
            )
        
        # Get command from parameter, env var, or default
        # First, try to find the executable directly if not specified
        env_command = os.getenv("WINDOWS_MCP_COMMAND")
        
        if not command and not env_command:
            # Try to find Windows-MCP.Net.exe in common locations
            exe_path = _find_windows_mcp_exe()
            if exe_path:
                self._command = exe_path
                self._args = args or []
            else:
                self._command = DEFAULT_WINDOWS_MCP_COMMAND
                self._args = args or self._get_default_args()
        else:
            self._command = command or env_command or DEFAULT_WINDOWS_MCP_COMMAND
            self._args = args or self._get_default_args()
        
        # If command is dnx or dnx.CMD, try to use direct executable path instead
        # This fixes issues where dnx command doesn't work properly
        if self._command and ("dnx" in self._command.lower() or "dnx.cmd" in self._command.lower()):
            logger = logging.getLogger(__name__)
            exe_path = _find_windows_mcp_exe()
            if exe_path:
                logger.info(f"Detected dnx command, switching to direct executable: {exe_path}")
                self._command = exe_path
                self._args = args or []
        
        self._env = env or {}
        self._tool_cache: List[Dict[str, Any]] | None = None
        
        # Verify command exists
        # Check if it's an absolute path (full path to executable)
        command_path = Path(self._command)
        is_absolute_path = command_path.is_absolute()
        
        if is_absolute_path:
            # Direct path specified - check if file exists
            # Default to .Net.exe extension (actual executable name is Windows-MCP.Net.exe)
            if not command_path.exists():
                # If no extension, try adding .Net.exe
                if not command_path.suffix:
                    net_exe_path = command_path.with_suffix('.Net.exe')
                    if net_exe_path.exists():
                        command_path = net_exe_path
                        self._command = str(command_path)
                    else:
                        raise WindowsMCPError(
                            f"WindowsMCP.Net executable not found at: {self._command} or {net_exe_path}"
                        )
                # If has .Net extension, try adding .exe to make .Net.exe
                elif command_path.suffix.lower() == '.net':
                    net_exe_path = command_path.with_suffix('.Net.exe')
                    if net_exe_path.exists():
                        command_path = net_exe_path
                        self._command = str(command_path)
                    else:
                        raise WindowsMCPError(
                            f"WindowsMCP.Net executable not found at: {self._command} or {net_exe_path}"
                        )
                # If has .exe but not .Net.exe, try .Net.exe
                elif command_path.suffix.lower() == '.exe' and not str(command_path).lower().endswith('.net.exe'):
                    net_exe_path = command_path.parent / (command_path.stem + '.Net.exe')
                    if net_exe_path.exists():
                        command_path = net_exe_path
                        self._command = str(command_path)
                    else:
                        raise WindowsMCPError(
                            f"WindowsMCP.Net executable not found at: {self._command} or {net_exe_path}"
                        )
                else:
                    raise WindowsMCPError(
                        f"WindowsMCP.Net executable not found at: {self._command}"
                    )
            # If path has no extension but file exists, still prefer .Net.exe for consistency
            elif not command_path.suffix:
                net_exe_path = command_path.with_suffix('.Net.exe')
                if net_exe_path.exists():
                    command_path = net_exe_path
                    self._command = str(command_path)
            if not command_path.is_file():
                raise WindowsMCPError(
                    f"WindowsMCP.Net path is not a file: {self._command}"
                )
        else:
            # Command name - search in PATH
            found_command = shutil.which(self._command)
            if not found_command:
                # Try alternative: dotnet tool run
                if self._command == "dnx" and shutil.which("dotnet"):
                    self._command = "dotnet"
                    self._args = ["tool", "run", "--", "WindowsMCP.Net"]
                else:
                    raise WindowsMCPError(
                        f"WindowsMCP.Net command '{self._command}' not found in PATH. "
                        "Options:\n"
                        "1. Install globally: dotnet tool install --global WindowsMCP.Net\n"
                        "2. Add to PATH: Add the directory containing the executable to system PATH\n"
                        "3. Use full path: Set WINDOWS_MCP_COMMAND to the full path (e.g., C:\\path\\to\\WindowsMCP.Net.exe)"
                    )
            else:
                # Use the found command (may be different from input if resolved from PATH)
                self._command = found_command

    def _get_default_args(self) -> List[str]:
        """Get default arguments based on command type."""
        # Check if command is a full path to executable
        command_path = Path(self._command)
        is_absolute_path = command_path.is_absolute()
        
        # Get args from environment variable if set
        env_args = os.getenv("WINDOWS_MCP_ARGS")
        if env_args:
            try:
                return json.loads(env_args)
            except json.JSONDecodeError:
                # If not valid JSON, treat as space-separated string
                return env_args.split()
        
        # If it's a direct executable path, no default args needed
        if is_absolute_path:
            return []
        
        # Handle command names
        if self._command == "dnx" or (isinstance(self._command, str) and "dnx" in self._command.lower()):
            return DEFAULT_WINDOWS_MCP_ARGS
        elif self._command == "dotnet" or (isinstance(self._command, str) and "dotnet" in self._command.lower()):
            return ["tool", "run", "--", "WindowsMCP.Net"]
        else:
            return []

    def list_tools_json(self, *, force_refresh: bool = False) -> str:
        """Return the available tools and their schemas as a JSON string."""
        # Create a wrapper that creates the coroutine in the new thread
        async def _wrapper():
            return await self._list_tools(force_refresh=force_refresh)
        tools = self._run_async(_wrapper())
        return json.dumps({"tools": tools}, ensure_ascii=False)

    def call_tool_json(self, tool_name: str, arguments: Dict[str, Any] | None = None) -> str:
        """Call a remote tool and serialize the response to JSON."""
        # Create a wrapper that creates the coroutine in the new thread
        async def _wrapper():
            return await self._call_tool(tool_name, arguments or {})
        payload = self._run_async(_wrapper())
        return json.dumps(payload, ensure_ascii=False)

    async def _list_tools(self, *, force_refresh: bool = False) -> List[Dict[str, Any]]:
        if self._tool_cache is not None and not force_refresh:
            return self._tool_cache

        if stdio_client is None:
            raise WindowsMCPError(
                "stdio_client is not available. Please ensure MCP SDK is properly installed."
            )

        try:
            # Create server parameters with command, args, and env
            server_params = StdioServerParameters(
                command=self._command,
                args=self._args,
                env=self._env if self._env else None,
            )
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
        except Exception as exc:  # noqa: BLE001
            # Provide more detailed error information
            error_msg = str(exc)
            error_type = type(exc).__name__
            
            # Check for common issues
            if "TaskGroup" in error_msg or "unhandled errors" in error_msg:
                detailed_msg = (
                    f"无法获取 WindowsMCP.Net 工具列表：{error_msg}\n"
                    f"错误类型：{error_type}\n"
                    "可能的原因：\n"
                    "1. WindowsMCP.Net 进程启动失败（检查命令路径是否正确）\n"
                    "2. WindowsMCP.Net 进程崩溃或异常退出\n"
                    "3. 事件循环冲突（尝试重启服务）\n"
                    f"命令：{self._command}\n"
                    f"参数：{self._args}"
                )
            else:
                detailed_msg = f"无法获取 WindowsMCP.Net 工具列表：{error_msg}"
            
            raise WindowsMCPError(detailed_msg) from exc

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
        if stdio_client is None:
            raise WindowsMCPError(
                "stdio_client is not available. Please ensure MCP SDK is properly installed."
            )

        try:
            # Create server parameters with command, args, and env
            server_params = StdioServerParameters(
                command=self._command,
                args=self._args,
                env=self._env if self._env else None,
            )
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments or None)
        except Exception as exc:  # noqa: BLE001
            # Provide more detailed error information
            error_msg = str(exc)
            error_type = type(exc).__name__
            
            # Check for common issues
            if "Connection closed" in error_msg or "connection closed" in error_msg.lower():
                # Connection closed usually means the process started but immediately exited
                detailed_msg = (
                    f"调用 WindowsMCP.Net 工具 {tool_name} 失败：连接已关闭\n"
                    f"错误类型：{error_type}\n"
                    "可能的原因：\n"
                    "1. WindowsMCP.Net 进程启动后立即退出（检查命令路径和参数是否正确）\n"
                    "2. 可执行文件路径不正确（尝试使用完整路径：C:\\Users\\Lenovo\\.dotnet\\tools\\Windows-MCP.Net.exe）\n"
                    "3. 进程权限问题或依赖项缺失\n"
                    f"当前命令：{self._command}\n"
                    f"当前参数：{self._args}\n"
                    "建议：\n"
                    "1. 设置环境变量：WINDOWS_MCP_COMMAND=C:\\Users\\Lenovo\\.dotnet\\tools\\Windows-MCP.Net.exe\n"
                    "2. 设置环境变量：WINDOWS_MCP_ARGS=[]\n"
                    "3. 重启服务后重试"
                )
            elif "TaskGroup" in error_msg or "unhandled errors" in error_msg:
                detailed_msg = (
                    f"调用 WindowsMCP.Net 工具 {tool_name} 失败：{error_msg}\n"
                    f"错误类型：{error_type}\n"
                    "可能的原因：\n"
                    "1. WindowsMCP.Net 进程启动失败（检查命令路径是否正确）\n"
                    "2. WindowsMCP.Net 进程崩溃或异常退出\n"
                    "3. 事件循环冲突（尝试重启服务）\n"
                    f"命令：{self._command}\n"
                    f"参数：{self._args}"
                )
            else:
                detailed_msg = f"调用 WindowsMCP.Net 工具 {tool_name} 失败：{error_msg}"
            
            raise WindowsMCPError(detailed_msg) from exc

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
        """Run an async coroutine without introducing thread pools or extra workers."""
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        
        if running_loop and running_loop.is_running():
            raise WindowsMCPError(
                "WindowsMCP.Net 调用失败：当前线程中已经有事件循环在运行，"
                "无法同步等待远程 MCP 响应。请在同步上下文中调用或使用独立线程。"
            )
        
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            asyncio.set_event_loop(None)
            loop.close()


class WindowsMCPToolInput(BaseModel):
    """Arguments for the LangChain WindowsMCP.Net tool wrapper."""

    tool_name: str = Field(
        default="",
        description="Name of the remote WindowsMCP.Net tool to call (e.g. 'click', 'type_text', 'get_window_info'). "
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


class WindowsMCPTool(ContextAwareTool):
    """LangChain tool that proxies calls to the WindowsMCP.Net MCP server."""

    name: str = "windows_mcp_tool"
    description: str = (
        "Call the WindowsMCP.Net MCP service to interact with Windows desktop environment. "
        "This tool provides desktop automation capabilities including: "
        "- Mouse operations: click, drag, scroll, move mouse "
        "- Keyboard operations: type text, press keys, copy/paste "
        "- Window management: get window info, resize windows, launch applications "
        "- System operations: get system status, execute PowerShell commands "
        "- Web scraping: extract information from web pages "
        "Provide 'tool_name' (e.g. 'click', 'type_text', 'get_window_info') and JSON 'arguments'. "
        "Leave 'tool_name' empty to fetch the available MCP tools."
    )
    args_schema: Type[BaseModel] = WindowsMCPToolInput

    def __init__(
        self,
        *,
        context: Optional[ToolContext] = None,
        client: Optional[WindowsMCPClient] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(context=context, **kwargs)
        try:
            self._client = client or WindowsMCPClient()
            self._cached_tools: Dict[str, Dict[str, Any]] | None = None
        except WindowsMCPError as e:
            # Store error but don't raise - allow tool to be created but show error when used
            self._client = None
            self._initialization_error = str(e)

    def _run(
        self,
        tool_name: str = "",
        arguments: Optional[Dict[str, Any]] = None,
        refresh_tools: bool = False,
    ) -> str:
        if self._client is None:
            error_msg = getattr(self, "_initialization_error", "WindowsMCP.Net client not initialized")
            return self._as_json({
                "error": error_msg,
                "message": (
                    "WindowsMCP.Net is not configured. "
                    "Please install it with: dotnet tool install --global WindowsMCP.Net"
                ),
            })

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
                    "message": "Provide 'tool_name' to invoke a specific WindowsMCP.Net tool.",
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
                        f"WindowsMCP.Net tool '{tool_name}' is not available. "
                        "Choose one of the tools listed above."
                    ),
                }
            )

        try:
            return self._client.call_tool_json(tool_name, arguments)
        except WindowsMCPError as exc:
            return self._as_json(
                {
                    "tool": tool_name,
                    "arguments": arguments,
                    "error": str(exc),
                    "message": (
                        "WindowsMCP.Net request failed. "
                        "Double-check the arguments or retry later. "
                        "Use 'refresh_tools': true if new tools were added."
                    ),
                }
            )

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("WindowsMCPTool does not support async execution.")

    def _get_available_tools(self, *, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        if self._cached_tools is not None and not force_refresh:
            return self._cached_tools

        try:
            payload = json.loads(self._client.list_tools_json(force_refresh=force_refresh))
        except WindowsMCPError as exc:
            raise ToolExecutionError(str(exc)) from exc

        tools = payload.get("tools") or []
        if not tools:
            raise ToolExecutionError("No WindowsMCP.Net tools are available from the configured endpoint.")

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


