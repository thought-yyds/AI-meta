"""Meeting tools for creating and joining meetings using WindowsMCP automation."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Sequence, Type

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False

from pydantic import BaseModel, Field

from .base import ContextAwareTool, ToolContext, ToolExecutionError
from .windows_mcp import WindowsMCPClient, WindowsMCPError

try:
    from ..llm.client import DoubaoService
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    DoubaoService = None


TENCENT_MEETING_ALIASES: Sequence[str] = (
    "腾讯会议",
    "tencent meeting",
    "voov meeting",
    "voov",
    "tencentmeeting",
    "wemeet",
    "wemeetapp",
)

TENCENT_MEETING_ALIAS_SET = {alias.casefold() for alias in TENCENT_MEETING_ALIASES}

DEFAULT_TENCENT_MEETING_PATHS: Sequence[Path] = (
    Path(r"C:\Program Files\Tencent\VooVMeeting\VooVMeeting.exe"),
    Path(r"C:\Program Files (x86)\Tencent\VooVMeeting\VooVMeeting.exe"),
    Path.home() / r"AppData\Local\Tencent\VooVMeeting\VooVMeeting.exe",
    Path(r"C:\Program Files\Tencent\WeMeet\wemeetapp.exe"),
    Path(r"C:\Program Files (x86)\Tencent\WeMeet\wemeetapp.exe"),
    Path(r"D:\Program Files\Tencent\WeMeet\wemeetapp.exe"),
    Path(r"D:\Party\WeMeet\wemeetapp.exe"),
)

if WINREG_AVAILABLE:
    TENCENT_REGISTRY_PATHS: Sequence[tuple[int, str]] = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\VooVMeeting.exe"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\VooVMeeting.exe"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\wemeetapp.exe"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\wemeetapp.exe"),
    )
else:  # pragma: no cover - non-Windows environments
    TENCENT_REGISTRY_PATHS = ()


def _normalize(text: str) -> str:
    return text.casefold().strip()


def _looks_like_path(value: str) -> bool:
    if not value:
        return False
    lowered = value.casefold()
    return (
        ":" in value
        or "\\" in value
        or "/" in value
        or lowered.endswith(".exe")
        or lowered.endswith(".lnk")
    )


def _resolve_tencent_meeting_executable(meeting_app: str) -> Optional[Path]:
    candidates: List[Path] = []
    for candidate in (meeting_app, os.environ.get("TENCENT_MEETING_EXE")):
        if not candidate:
            continue
        try:
            candidates.append(Path(candidate).expanduser())
        except (OSError, TypeError):
            continue

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    for default_path in DEFAULT_TENCENT_MEETING_PATHS:
        if default_path.is_file():
            return default_path

    if WINREG_AVAILABLE:
        for hive, reg_path in TENCENT_REGISTRY_PATHS:
            try:
                with winreg.OpenKey(hive, reg_path) as key:  # type: ignore[arg-type]
                    exe_path = winreg.QueryValue(key, None)
                    path_obj = Path(exe_path)
                    if path_obj.is_file():
                        return path_obj
            except OSError:
                continue

    return None


def _is_supported_meeting_app(meeting_app: str) -> bool:
    if not meeting_app:
        return False

    exe_path = _resolve_tencent_meeting_executable(meeting_app)
    if exe_path is not None:
        return True

    normalized = _normalize(meeting_app)
    return normalized in TENCENT_MEETING_ALIAS_SET


def _build_tencent_launch_payload(meeting_app: str) -> Dict[str, str]:
    exe_path = _resolve_tencent_meeting_executable(meeting_app)
    if exe_path:
        return {
            "name": str(exe_path),
            "cwd": str(exe_path.parent),
        }
    return {"name": meeting_app}


def _launch_meeting_app(
    meeting_app: str,
    client: WindowsMCPClient,
    steps: List[str],
) -> bool:
    """仅使用 WindowsMCP 启动会议应用，并确保传入 cwd。"""

    if not _is_supported_meeting_app(meeting_app):
        steps.append("⚠️ 当前版本仅支持腾讯会议，请传入 '腾讯会议' 或 wemeetapp.exe 的路径。")
        return False

    payload = _build_tencent_launch_payload(meeting_app)
    steps.append("尝试使用 WindowsMCP 的 launch_app 启动腾讯会议 ...")
    if "cwd" in payload:
        steps.append(f"使用可执行文件: {payload['name']}")
        steps.append(f"工作目录: {payload['cwd']}")
    else:
        steps.append("未找到腾讯会议的可执行文件路径，将直接传入应用名称给 launch_app。")

    try:
        launch_result = json.loads(client.call_tool_json("launch_app", payload))
    except Exception as exc:  # pragma: no cover - depends on MCP availability
        steps.append(f"⚠️ launch_app 调用异常: {exc}")
        return False

    if launch_result.get("is_error"):
        steps.append(f"⚠️ launch_app 返回错误: {launch_result.get('text', '未知错误')}")
        return False

    steps.append("✅ launch_app 调用成功")
    return True


class CreateMeetingInput(BaseModel):
    """Input schema for creating a meeting."""

    meeting_app: str = Field(
        default="腾讯会议",
        description="当前版本仅支持腾讯会议。可传 '腾讯会议' 或 wemeetapp.exe 的绝对路径。",
    )
    meeting_title: Optional[str] = Field(
        None,
        description="会议标题（可选）。如果不提供，将使用默认标题。",
    )
    wait_seconds: int = Field(
        default=3,
        description="操作之间的等待时间（秒），用于等待应用响应。默认为 3 秒。",
    )


class JoinMeetingInput(BaseModel):
    """Input schema for joining a meeting."""

    meeting_id: Optional[str] = Field(
        None,
        description="会议ID或会议号（可选）。如果提供，将自动输入会议号。",
    )
    meeting_link: Optional[str] = Field(
        None,
        description="会议链接（可选）。如果提供，将在浏览器中打开链接。",
    )
    meeting_app: str = Field(
        default="腾讯会议",
        description="当前版本仅支持腾讯会议。可传 '腾讯会议' 或 wemeetapp.exe 的绝对路径。",
    )
    password: Optional[str] = Field(
        None,
        description="会议密码（可选）。如果需要密码才能加入会议。",
    )
    wait_seconds: int = Field(
        default=3,
        description="操作之间的等待时间（秒），用于等待应用响应。默认为 3 秒。",
    )


class CreateMeetingTool(ContextAwareTool):
    """创建会议的工具，通过自动化操作会议应用来创建新会议。"""

    name: str = "create_meeting"
    description: str = (
        "创建新的腾讯会议。工具会自动启动腾讯会议（仅支持腾讯会议），"
        "并指导你在应用内完成创建流程，同时尽量提取会议号或链接。"
    )
    args_schema: ClassVar[Type[CreateMeetingInput]] = CreateMeetingInput

    def __init__(
        self,
        *,
        context: Optional[ToolContext] = None,
        client: Optional[WindowsMCPClient] = None,
        **kwargs,
    ) -> None:
        super().__init__(context=context, **kwargs)
        try:
            self._client = client or WindowsMCPClient()
        except WindowsMCPError as e:
            self._client = None
            self._initialization_error = str(e)

    def _run(
        self,
        meeting_app: str = "腾讯会议",
        meeting_title: Optional[str] = None,
        wait_seconds: int = 3,
    ) -> str:
        if self._client is None:
            error_msg = getattr(self, "_initialization_error", "WindowsMCP.Net client not initialized")
            return self._as_json({
                "error": error_msg,
                "message": "WindowsMCP.Net 未配置，无法创建会议。",
            })

        if not _is_supported_meeting_app(meeting_app):
            return self._as_json({
                "status": "error",
                "error": "unsupported_meeting_app",
                "message": (
                    "当前仅支持腾讯会议。请传入 '腾讯会议'、wemeetapp.exe 的绝对路径，"
                    "或在环境变量 TENCENT_MEETING_EXE 中配置可执行文件路径。"
                ),
            })

        try:
            steps = []
            result_info = {}

            # 步骤1: 使用 WindowsMCP 启动会议应用
            launch_success = _launch_meeting_app(meeting_app, self._client, steps)
            if not launch_success:
                steps.append(f"⚠️ 如果 {meeting_app} 未自动打开，请手动启动后继续。")

            # 等待应用启动（注意：launch_app 可能只发送了启动命令，但应用未真正启动）
            steps.append(f"等待 {meeting_app} 启动（{wait_seconds}秒）...")
            steps.append("⚠️ 注意：应用可能启动后立即退出（权限、配置问题），窗口可能被隐藏或最小化到系统托盘")
            time.sleep(wait_seconds)

            # 步骤2: 尝试切换到应用窗口
            steps.append(f"正在将 {meeting_app} 窗口带到前台...")
            try:
                switch_result = json.loads(self._client.call_tool_json("switch_app", {"name": meeting_app}))
                if switch_result.get("is_error"):
                    steps.append(f"⚠️ 无法切换到 {meeting_app} 窗口: {switch_result.get('text', '未知错误')}")
                    steps.append("提示: 请手动检查任务栏是否有腾讯会议图标，或使用 Alt+Tab 切换窗口")
                else:
                    steps.append(f"✅ 成功切换到 {meeting_app} 窗口")
                time.sleep(2)
            except Exception as e:
                steps.append(f"⚠️ 切换窗口时出错: {e}")

            # 步骤3: 提示用户使用 WindowsMCP 工具进行操作
            steps.append("提示: 请使用 windows_mcp_tool 进行创建会议等操作，或手动在应用界面中操作")

            # 步骤4: 等待并尝试获取会议信息
            time.sleep(wait_seconds)
            steps.append("正在获取会议信息...")
            try:
                screen_text = json.loads(self._client.call_tool_json("extract_text_from_screen", {}))
                if screen_text and not screen_text.get("is_error"):
                    text_content = screen_text.get("text", "")
                    # 查找会议号
                    meeting_id_pattern = r"会议号[：:]\s*(\d+)"
                    match = re.search(meeting_id_pattern, text_content)
                    if match:
                        result_info["meeting_id"] = match.group(1)
                    # 查找会议链接
                    url_pattern = r"https?://[^\s]+"
                    urls = re.findall(url_pattern, text_content)
                    if urls:
                        result_info["meeting_links"] = urls
            except Exception:
                pass

            return self._as_json({
                "status": "partial",
                "steps": steps,
                "meeting_app": meeting_app,
                "meeting_title": meeting_title,
                **result_info,
                "message": f"会议创建流程已执行。请检查 {meeting_app} 窗口确认会议是否已成功创建。",
            })

        except ToolExecutionError:
            raise
        except Exception as e:
            return self._as_json({
                "status": "error",
                "error": str(e),
                "message": f"创建会议时发生错误: {e}",
            })

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("CreateMeetingTool does not support async execution.")


class JoinMeetingTool(ContextAwareTool):
    """加入会议的工具，通过自动化操作会议应用或浏览器来加入现有会议。"""

    name: str = "join_meeting"
    description: str = (
        "加入现有的腾讯会议。可通过会议ID或会议链接辅助加入。"
        "工具会尝试自动打开腾讯会议并定位到加入会议入口，或在浏览器中打开会议链接。"
    )
    args_schema: ClassVar[Type[JoinMeetingInput]] = JoinMeetingInput

    def __init__(
        self,
        *,
        context: Optional[ToolContext] = None,
        client: Optional[WindowsMCPClient] = None,
        **kwargs,
    ) -> None:
        super().__init__(context=context, **kwargs)
        try:
            self._client = client or WindowsMCPClient()
        except WindowsMCPError as e:
            self._client = None
            self._initialization_error = str(e)

    def _run(
        self,
        meeting_id: Optional[str] = None,
        meeting_link: Optional[str] = None,
        meeting_app: str = "腾讯会议",
        password: Optional[str] = None,
        wait_seconds: int = 3,
    ) -> str:
        if self._client is None:
            error_msg = getattr(self, "_initialization_error", "WindowsMCP.Net client not initialized")
            return self._as_json({
                "error": error_msg,
                "message": "WindowsMCP.Net 未配置，无法加入会议。",
            })

        if not _is_supported_meeting_app(meeting_app):
            return self._as_json({
                "status": "error",
                "error": "unsupported_meeting_app",
                "message": (
                    "当前仅支持腾讯会议。请传入 '腾讯会议'、wemeetapp.exe 的绝对路径，"
                    "或在环境变量 TENCENT_MEETING_EXE 中配置可执行文件路径。"
                ),
            })

        if not meeting_id and not meeting_link:
            return self._as_json({
                "error": "missing_parameters",
                "message": "必须提供 meeting_id（会议号）或 meeting_link（会议链接）之一。",
            })

        try:
            steps = []
            result_info = {}

            # 如果有会议链接，优先使用链接
            if meeting_link:
                steps.append(f"正在浏览器中打开会议链接: {meeting_link}")
                try:
                    open_result = json.loads(self._client.call_tool_json("open_browser", {"url": meeting_link}))
                    if open_result.get("is_error"):
                        raise ToolExecutionError(f"无法打开会议链接: {open_result.get('text', '未知错误')}")
                    time.sleep(wait_seconds)
                    return self._as_json({
                        "status": "success",
                        "steps": steps,
                        "meeting_link": meeting_link,
                        "message": "已在浏览器中打开会议链接，请按照提示加入会议。",
                    })
                except Exception as e:
                    raise ToolExecutionError(f"打开会议链接失败: {e}") from e

            # 使用会议ID加入
            if meeting_id:
                # 步骤1: 使用 WindowsMCP 启动会议应用
                launch_success = _launch_meeting_app(meeting_app, self._client, steps)
                if not launch_success:
                    steps.append(f"⚠️ 如果 {meeting_app} 未自动打开，请手动启动后继续。")

                time.sleep(wait_seconds)

                # 尝试将窗口带到前台，避免窗口被遮挡
                steps.append(f"正在将 {meeting_app} 窗口带到前台...")
                try:
                    switch_result = json.loads(self._client.call_tool_json("switch_app", {"name": meeting_app}))
                    if switch_result.get("is_error"):
                        steps.append(f"⚠️ 无法切换到 {meeting_app} 窗口: {switch_result.get('text', '未知错误')}")
                    else:
                        steps.append(f"✅ 成功切换到 {meeting_app} 窗口")
                    time.sleep(1)
                except Exception as e:
                    steps.append(f"⚠️ 切换窗口时出错: {e}")

                # 步骤2: 查找"加入会议"按钮或输入框
                steps.append("正在查找加入会议入口...")
                join_texts = ["加入会议", "Join Meeting", "Enter Meeting", "会议号", "Meeting ID"]
                
                found_join = False
                for text in join_texts:
                    try:
                        coords_result = json.loads(
                            self._client.call_tool_json("get_text_coordinates", {"text": text})
                        )
                        if not coords_result.get("is_error") and coords_result.get("text"):
                            found_join = True
                            steps.append(f"找到 '{text}'，准备输入会议号...")
                            break
                    except Exception:
                        continue

                if not found_join:
                    # 尝试使用 OCR 查找
                    try:
                        screen_text = json.loads(self._client.call_tool_json("extract_text_from_screen", {}))
                        if screen_text and not screen_text.get("is_error"):
                            text_content = screen_text.get("text", "")
                            for text in join_texts:
                                if text in text_content:
                                    found_join = True
                                    break
                    except Exception:
                        pass

                if not found_join:
                    return self._as_json({
                        "status": "partial",
                        "steps": steps,
                        "message": (
                            f"已启动 {meeting_app}，但无法自动找到加入会议入口。"
                            "请手动点击加入会议按钮，或使用 windows_mcp_tool 进行更精确的操作。"
                        ),
                        "meeting_id": meeting_id,
                        "suggestion": "可以尝试使用 get_desktop_state 工具查看当前屏幕状态，然后手动操作。",
                    })

                # 步骤3: 输入会议号
                steps.append(f"正在输入会议号: {meeting_id}")
                # 注意：这里需要找到输入框的位置，然后使用 type 工具输入
                # 由于无法精确定位输入框，这里提供指导信息
                time.sleep(wait_seconds)

                # 步骤4: 如果有密码，输入密码
                if password:
                    steps.append("正在输入会议密码...")
                    time.sleep(wait_seconds)

                # 步骤5: 点击加入按钮
                steps.append("正在点击加入按钮...")
                time.sleep(wait_seconds)

                return self._as_json({
                    "status": "success",
                    "steps": steps,
                    "meeting_app": meeting_app,
                    "meeting_id": meeting_id,
                    "has_password": password is not None,
                    "message": (
                        f"加入会议流程已执行。会议号: {meeting_id}。"
                        "请检查 {meeting_app} 窗口确认是否已成功加入会议。"
                    ),
                })

        except ToolExecutionError:
            raise
        except Exception as e:
            return self._as_json({
                "status": "error",
                "error": str(e),
                "message": f"加入会议时发生错误: {e}",
            })

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("JoinMeetingTool does not support async execution.")


# ==================== MeetingCaptureTool 相关工具 ====================

class CaptureSlideContentInput(BaseModel):
    """Input schema for capturing slide content."""

    save_path: Optional[str] = Field(
        None,
        description="保存截图的路径（可选）。如果不提供，将保存到工作目录的 captures 文件夹。",
    )


class CaptureSpecificRegionInput(BaseModel):
    """Input schema for capturing a specific screen region."""

    x: int = Field(description="区域左上角 X 坐标")
    y: int = Field(description="区域左上角 Y 坐标")
    width: int = Field(description="区域宽度")
    height: int = Field(description="区域高度")
    save_path: Optional[str] = Field(
        None,
        description="保存截图的路径（可选）。如果不提供，将保存到工作目录的 captures 文件夹。",
    )


class MonitorScreenChangesInput(BaseModel):
    """Input schema for monitoring screen changes."""

    interval: int = Field(
        default=5,
        description="检查间隔（秒）。默认为 5 秒。建议范围：3-10 秒。",
    )
    duration: int = Field(
        default=60,
        description=(
            "监控持续时间（秒）。默认为 60 秒。"
            "注意：由于 HTTP 请求超时限制，建议不超过 300 秒（5 分钟）。"
            "如需长时间监控，可以多次调用此工具。"
        ),
    )


class AutoCaptureImportantRegionsInput(BaseModel):
    """Input schema for auto-capturing important regions."""

    target_types: Optional[List[str]] = Field(
        default=None,
        description="要捕获的区域类型列表，如 ['ppt', 'whiteboard', 'chat', 'discussion']。"
        "如果为空，将自动识别所有重要区域。可选值：'ppt'（PPT/共享屏幕）、'whiteboard'（白板）、"
        "'chat'（聊天区）、'discussion'（讨论区）、'participants'（参与者列表）。",
    )
    max_regions: int = Field(
        default=5,
        description="最多捕获的区域数量。默认为 5。",
    )


class CaptureSlideContentTool(ContextAwareTool):
    """捕获会议PPT/共享屏幕内容的工具。"""

    name: str = "capture_slide_content"
    description: str = (
        "专门捕获会议PPT/共享屏幕内容。"
        "使用OCR提取屏幕上的文字，并保存截图。"
        "返回识别出的文字、截图路径和时间戳。"
        "注意：此工具运行在后端服务中，直接访问 Windows 系统 API 进行截图，"
        "即使浏览器窗口最小化也能正常工作。"
    )
    args_schema: ClassVar[Type[CaptureSlideContentInput]] = CaptureSlideContentInput

    def __init__(
        self,
        *,
        context: Optional[ToolContext] = None,
        client: Optional[WindowsMCPClient] = None,
        **kwargs,
    ) -> None:
        super().__init__(context=context, **kwargs)
        try:
            self._client = client or WindowsMCPClient()
        except WindowsMCPError as e:
            self._client = None
            self._initialization_error = str(e)

    def _run(self, save_path: Optional[str] = None) -> str:
        if self._client is None:
            error_msg = getattr(self, "_initialization_error", "WindowsMCP.Net client not initialized")
            return self._as_json({
                "error": error_msg,
                "message": "WindowsMCP.Net 未配置，无法捕获屏幕内容。",
            })

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 确定保存路径
            if save_path:
                save_dir = Path(save_path).parent
                save_dir.mkdir(parents=True, exist_ok=True)
                image_path = save_path
            else:
                working_dir = Path(self.context.working_dir or Path.cwd())
                captures_dir = working_dir / "captures"
                captures_dir.mkdir(parents=True, exist_ok=True)
                image_path = str(captures_dir / f"slide_{timestamp}.png")

            # 使用 WindowsMCP 提取屏幕文本
            screen_text_result = json.loads(self._client.call_tool_json("extract_text_from_screen", {}))
            
            if screen_text_result.get("is_error"):
                return self._as_json({
                    "status": "error",
                    "error": screen_text_result.get("text", "未知错误"),
                    "message": "提取屏幕文本失败。",
                })

            text_content = screen_text_result.get("text", "")
            
            # 尝试获取截图（如果 WindowsMCP 支持）
            # 注意：这里假设 WindowsMCP 可能返回截图路径，实际需要根据 API 调整
            screenshot_path = None
            try:
                # 尝试调用截图工具（如果存在）
                screenshot_result = json.loads(
                    self._client.call_tool_json("screenshot", {"path": image_path})
                )
                if not screenshot_result.get("is_error"):
                    screenshot_path = screenshot_result.get("path") or image_path
            except Exception:
                # 如果截图工具不存在，使用默认路径
                screenshot_path = image_path

            return self._as_json({
                "status": "success",
                "text": text_content,
                "image_path": screenshot_path or image_path,
                "timestamp": timestamp,
                "message": "成功捕获屏幕内容。",
            })

        except Exception as e:
            return self._as_json({
                "status": "error",
                "error": str(e),
                "message": f"捕获屏幕内容时发生错误: {e}",
            })

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("CaptureSlideContentTool does not support async execution.")


class CaptureSpecificRegionTool(ContextAwareTool):
    """捕获屏幕特定区域的工具，用于抓取重点讨论内容。"""

    name: str = "capture_specific_region"
    description: str = (
        "捕获屏幕特定区域（如白板、讨论区）。"
        "用于抓取重点讨论内容。需要提供区域的坐标和尺寸。"
    )
    args_schema: ClassVar[Type[CaptureSpecificRegionInput]] = CaptureSpecificRegionInput

    def __init__(
        self,
        *,
        context: Optional[ToolContext] = None,
        client: Optional[WindowsMCPClient] = None,
        **kwargs,
    ) -> None:
        super().__init__(context=context, **kwargs)
        try:
            self._client = client or WindowsMCPClient()
        except WindowsMCPError as e:
            self._client = None
            self._initialization_error = str(e)

    def _run(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        save_path: Optional[str] = None,
    ) -> str:
        if self._client is None:
            error_msg = getattr(self, "_initialization_error", "WindowsMCP.Net client not initialized")
            return self._as_json({
                "error": error_msg,
                "message": "WindowsMCP.Net 未配置，无法捕获区域内容。",
            })

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 确定保存路径
            if save_path:
                save_dir = Path(save_path).parent
                save_dir.mkdir(parents=True, exist_ok=True)
                image_path = save_path
            else:
                working_dir = Path(self.context.working_dir or Path.cwd())
                captures_dir = working_dir / "captures"
                captures_dir.mkdir(parents=True, exist_ok=True)
                image_path = str(captures_dir / f"region_{timestamp}.png")

            # 尝试使用 WindowsMCP 截图指定区域
            # 注意：需要根据 WindowsMCP 的实际 API 调整
            try:
                screenshot_result = json.loads(
                    self._client.call_tool_json(
                        "screenshot",
                        {
                            "path": image_path,
                            "x": x,
                            "y": y,
                            "width": width,
                            "height": height,
                        }
                    )
                )
                if screenshot_result.get("is_error"):
                    return self._as_json({
                        "status": "error",
                        "error": screenshot_result.get("text", "截图失败"),
                        "message": "无法截取指定区域。",
                    })
                image_path = screenshot_result.get("path") or image_path
            except Exception as e:
                # 如果区域截图不支持，返回提示
                return self._as_json({
                    "status": "partial",
                    "message": f"区域截图功能可能不可用: {e}。请使用 capture_slide_content 工具捕获全屏，然后手动裁剪。",
                    "suggested_path": image_path,
                    "region": {"x": x, "y": y, "width": width, "height": height},
                })

            # 提取该区域的文本
            text_content = ""
            try:
                # 尝试提取区域文本（如果支持）
                region_text_result = json.loads(
                    self._client.call_tool_json(
                        "extract_text_from_screen",
                        {"x": x, "y": y, "width": width, "height": height}
                    )
                )
                if not region_text_result.get("is_error"):
                    text_content = region_text_result.get("text", "")
            except Exception:
                pass

            return self._as_json({
                "status": "success",
                "text": text_content,
                "image_path": image_path,
                "timestamp": timestamp,
                "region": {"x": x, "y": y, "width": width, "height": height},
                "message": "成功捕获指定区域内容。",
            })

        except Exception as e:
            return self._as_json({
                "status": "error",
                "error": str(e),
                "message": f"捕获区域内容时发生错误: {e}",
            })

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("CaptureSpecificRegionTool does not support async execution.")


class MonitorScreenChangesTool(ContextAwareTool):
    """持续监控屏幕变化，检测幻灯片翻页或内容更新的工具。"""

    name: str = "monitor_screen_changes"
    description: str = (
        "持续监控屏幕变化，检测幻灯片翻页或内容更新。"
        "每 interval 秒检查一次变化，持续 duration 秒。"
        "当检测到变化时，会自动捕获新的屏幕内容。"
        "注意：此工具运行在后端服务中，即使浏览器窗口最小化也能正常工作。"
        "建议 duration 不要设置过长（建议不超过 300 秒），以避免 HTTP 请求超时。"
    )
    args_schema: ClassVar[Type[MonitorScreenChangesInput]] = MonitorScreenChangesInput

    def __init__(
        self,
        *,
        context: Optional[ToolContext] = None,
        client: Optional[WindowsMCPClient] = None,
        **kwargs,
    ) -> None:
        super().__init__(context=context, **kwargs)
        try:
            self._client = client or WindowsMCPClient()
        except WindowsMCPError as e:
            self._client = None
            self._initialization_error = str(e)

    def _run(self, interval: int = 5, duration: int = 60) -> str:
        if self._client is None:
            error_msg = getattr(self, "_initialization_error", "WindowsMCP.Net client not initialized")
            return self._as_json({
                "error": error_msg,
                "message": "WindowsMCP.Net 未配置，无法监控屏幕变化。",
            })

        try:
            working_dir = Path(self.context.working_dir or Path.cwd())
            captures_dir = working_dir / "captures"
            captures_dir.mkdir(parents=True, exist_ok=True)

            changes_detected = []
            previous_text = ""
            start_time = time.time()
            check_count = 0

            while time.time() - start_time < duration:
                check_count += 1
                
                # 提取当前屏幕文本
                try:
                    screen_text_result = json.loads(
                        self._client.call_tool_json("extract_text_from_screen", {})
                    )
                    if screen_text_result.get("is_error"):
                        time.sleep(interval)
                        continue

                    current_text = screen_text_result.get("text", "")
                    
                    # 简单比较：如果文本内容变化超过一定阈值，认为有变化
                    if previous_text and current_text != previous_text:
                        # 计算变化程度（简单方法：字符差异）
                        if len(current_text) != len(previous_text) or current_text != previous_text:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            image_path = str(captures_dir / f"change_{timestamp}.png")
                            
                            # 保存截图
                            try:
                                screenshot_result = json.loads(
                                    self._client.call_tool_json("screenshot", {"path": image_path})
                                )
                                if not screenshot_result.get("is_error"):
                                    image_path = screenshot_result.get("path") or image_path
                            except Exception:
                                pass

                            changes_detected.append({
                                "timestamp": timestamp,
                                "text": current_text[:200],  # 只保存前200字符作为预览
                                "image_path": image_path,
                                "check_number": check_count,
                            })

                    previous_text = current_text
                except Exception as e:
                    # 如果提取失败，继续监控
                    pass

                time.sleep(interval)

            return self._as_json({
                "status": "success",
                "monitoring_duration": duration,
                "check_interval": interval,
                "total_checks": check_count,
                "changes_detected": len(changes_detected),
                "changes": changes_detected,
                "message": f"监控完成，检测到 {len(changes_detected)} 次变化。",
            })

        except Exception as e:
            return self._as_json({
                "status": "error",
                "error": str(e),
                "message": f"监控屏幕变化时发生错误: {e}",
            })

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("MonitorScreenChangesTool does not support async execution.")


class AutoCaptureImportantRegionsTool(ContextAwareTool):
    """自动识别并截图屏幕重要区域的工具。使用AI分析屏幕内容，自动识别PPT、白板、聊天区等重要区域并截图。"""

    name: str = "auto_capture_important_regions"
    description: str = (
        "自动识别并截图屏幕上的重要区域（如PPT、白板、聊天区、讨论区等）。"
        "工具会先分析屏幕内容，使用AI识别重要区域，然后自动对这些区域进行截图。"
        "无需手动指定坐标，完全自动化。"
    )
    args_schema: ClassVar[Type[AutoCaptureImportantRegionsInput]] = AutoCaptureImportantRegionsInput

    def __init__(
        self,
        *,
        context: Optional[ToolContext] = None,
        client: Optional[WindowsMCPClient] = None,
        llm_service: Optional[Any] = None,
        **kwargs,
    ) -> None:
        super().__init__(context=context, **kwargs)
        try:
            self._client = client or WindowsMCPClient()
        except WindowsMCPError as e:
            self._client = None
            self._initialization_error = str(e)
        
        # 初始化 LLM 服务（如果可用）
        if LLM_AVAILABLE and DoubaoService:
            try:
                self._llm_service = llm_service or DoubaoService()
            except Exception:
                self._llm_service = None
        else:
            self._llm_service = None

    def _run(
        self,
        target_types: Optional[List[str]] = None,
        max_regions: int = 5,
    ) -> str:
        if self._client is None:
            error_msg = getattr(self, "_initialization_error", "WindowsMCP.Net client not initialized")
            return self._as_json({
                "error": error_msg,
                "message": "WindowsMCP.Net 未配置，无法自动捕获区域。",
            })

        if self._llm_service is None:
            return self._as_json({
                "status": "error",
                "error": "LLM服务未配置",
                "message": "需要LLM服务来分析屏幕内容。请配置DoubaoService。",
            })

        try:
            working_dir = Path(self.context.working_dir or Path.cwd())
            captures_dir = working_dir / "captures"
            captures_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 步骤1: 截取全屏并提取文本
            try:
                # 先截取全屏
                full_screen_path = str(captures_dir / f"fullscreen_{timestamp}.png")
                screenshot_result = json.loads(
                    self._client.call_tool_json("screenshot", {"path": full_screen_path})
                )
                if screenshot_result.get("is_error"):
                    return self._as_json({
                        "status": "error",
                        "error": screenshot_result.get("text", "截图失败"),
                        "message": "无法截取全屏。",
                    })

                # 提取全屏文本
                screen_text_result = json.loads(
                    self._client.call_tool_json("extract_text_from_screen", {})
                )
                screen_text = screen_text_result.get("text", "") if not screen_text_result.get("is_error") else ""
            except Exception as e:
                return self._as_json({
                    "status": "error",
                    "error": str(e),
                    "message": f"获取屏幕内容时发生错误: {e}",
                })

            # 步骤2: 使用LLM分析屏幕内容，识别重要区域
            try:
                # 构建提示词
                target_types_str = ", ".join(target_types) if target_types else "所有重要区域"
                prompt = f"""分析以下屏幕文本内容，识别出需要截图的重要区域。

屏幕文本内容：
{screen_text[:2000]}  # 限制长度避免超出token限制

需要识别的区域类型：{target_types_str}
最多识别 {max_regions} 个区域。

请识别以下类型的区域：
- PPT/共享屏幕区域：包含演示文稿、幻灯片内容
- 白板区域：包含手写内容、绘图
- 聊天区：包含聊天消息、讨论内容
- 讨论区：包含参与者讨论、评论
- 参与者列表：包含参会人员信息

对于每个识别出的区域，请返回JSON格式：
{{
  "regions": [
    {{
      "type": "ppt|whiteboard|chat|discussion|participants",
      "description": "区域描述",
      "x": 左上角x坐标,
      "y": 左上角y坐标,
      "width": 区域宽度,
      "height": 区域高度,
      "priority": 优先级(1-5, 5最高)
    }}
  ]
}}

注意：
- 坐标基于屏幕像素，左上角为(0,0)
- 如果无法确定精确坐标，可以基于文本位置估算
- 优先返回高优先级的区域
- 最多返回 {max_regions} 个区域

只返回JSON，不要其他文字。"""

                # 调用LLM分析
                llm_response = self._llm_service.complete(
                    prompt,
                    system_prompt="你是一个屏幕内容分析专家，擅长识别会议软件中的重要区域。",
                )
                
                # 解析LLM响应
                response_text = llm_response.get("message", "") if isinstance(llm_response, dict) else str(llm_response)
                
                # 尝试提取JSON
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    regions_data = json.loads(json_match.group())
                else:
                    # 如果无法提取JSON，尝试直接解析
                    regions_data = json.loads(response_text)
                
                identified_regions = regions_data.get("regions", [])
                
                # 按优先级排序
                identified_regions.sort(key=lambda r: r.get("priority", 0), reverse=True)
                identified_regions = identified_regions[:max_regions]
                
            except Exception as e:
                # 如果LLM分析失败，返回全屏截图
                return self._as_json({
                    "status": "partial",
                    "message": f"AI分析失败: {e}。已保存全屏截图。",
                    "fullscreen_path": full_screen_path,
                    "screen_text": screen_text[:500],
                    "error": str(e),
                })

            # 步骤3: 对识别出的区域进行截图
            captured_regions = []
            for idx, region in enumerate(identified_regions):
                try:
                    region_type = region.get("type", "unknown")
                    x = region.get("x", 0)
                    y = region.get("y", 0)
                    width = region.get("width", 100)
                    height = region.get("height", 100)
                    
                    # 截图该区域
                    region_path = str(captures_dir / f"region_{region_type}_{timestamp}_{idx+1}.png")
                    screenshot_result = json.loads(
                        self._client.call_tool_json(
                            "screenshot",
                            {
                                "path": region_path,
                                "x": x,
                                "y": y,
                                "width": width,
                                "height": height,
                            }
                        )
                    )
                    
                    if not screenshot_result.get("is_error"):
                        # 提取该区域的文本
                        region_text = ""
                        try:
                            region_text_result = json.loads(
                                self._client.call_tool_json(
                                    "extract_text_from_screen",
                                    {"x": x, "y": y, "width": width, "height": height}
                                )
                            )
                            if not region_text_result.get("is_error"):
                                region_text = region_text_result.get("text", "")
                        except Exception:
                            pass
                        
                        captured_regions.append({
                            "type": region_type,
                            "description": region.get("description", ""),
                            "x": x,
                            "y": y,
                            "width": width,
                            "height": height,
                            "image_path": region_path,
                            "text": region_text,
                            "priority": region.get("priority", 0),
                        })
                except Exception as e:
                    # 单个区域截图失败，继续处理其他区域
                    continue

            return self._as_json({
                "status": "success",
                "message": f"成功识别并捕获 {len(captured_regions)} 个重要区域。",
                "fullscreen_path": full_screen_path,
                "screen_text": screen_text[:500],  # 只返回前500字符
                "regions": captured_regions,
                "total_regions": len(captured_regions),
                "timestamp": timestamp,
            })

        except Exception as e:
            return self._as_json({
                "status": "error",
                "error": str(e),
                "message": f"自动捕获重要区域时发生错误: {e}",
            })

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("AutoCaptureImportantRegionsTool does not support async execution.")


# ==================== ContentParserTool 相关工具 ====================

class ExtractStructuredAgendaInput(BaseModel):
    """Input schema for extracting structured agenda."""

    ocr_text: str = Field(description="从OCR获取的文本内容")


class IdentifyActionItemsInput(BaseModel):
    """Input schema for identifying action items."""

    discussion_text: str = Field(description="讨论文本内容")


class ExtractDecisionsInput(BaseModel):
    """Input schema for extracting decisions."""

    text: str = Field(description="需要分析的文本内容")


class SummarizeKeyPointsInput(BaseModel):
    """Input schema for summarizing key points."""

    full_text: str = Field(description="完整的会议文本内容")


class ExtractStructuredAgendaTool(ContextAwareTool):
    """从OCR文本中提取结构化议程的工具。"""

    name: str = "extract_structured_agenda"
    description: str = (
        "从OCR文本中提取结构化议程。"
        "返回议程项列表，每个议程项包含：议程项名称、预计时间、主讲人等信息。"
    )
    args_schema: ClassVar[Type[ExtractStructuredAgendaInput]] = ExtractStructuredAgendaInput

    def __init__(
        self,
        *,
        context: Optional[ToolContext] = None,
        llm_service: Optional[DoubaoService] = None,
        **kwargs,
    ) -> None:
        super().__init__(context=context, **kwargs)
        if not LLM_AVAILABLE:
            self._llm_service = None
            self._initialization_error = "LLM service not available"
        else:
            try:
                self._llm_service = llm_service or DoubaoService()
            except Exception as e:
                self._llm_service = None
                self._initialization_error = str(e)

    def _run(self, ocr_text: str) -> str:
        if self._llm_service is None:
            error_msg = getattr(self, "_initialization_error", "LLM service not initialized")
            return self._as_json({
                "error": error_msg,
                "message": "LLM 服务未配置，无法提取议程。",
            })

        try:
            prompt = f"""请从以下会议文本中提取结构化议程。文本可能来自OCR识别，可能包含一些识别错误。

文本内容：
{ocr_text}

请提取议程信息，返回JSON格式，包含以下字段：
- item: 议程项名称
- time: 预计时间（如果有）
- presenter: 主讲人（如果有）

如果没有明确的议程信息，返回空数组。

只返回JSON数组，不要其他说明文字。格式示例：
[
  {{"item": "项目进展汇报", "time": "10:00-10:30", "presenter": "张三"}},
  {{"item": "技术方案讨论", "time": "10:30-11:00", "presenter": "李四"}}
]"""

            response = self._llm_service.complete(
                prompt,
                system_prompt="你是一个专业的会议助手，擅长从文本中提取结构化信息。",
                temperature=0.3,
            )

            # 尝试解析JSON响应
            message = response.get("message", "")
            # 尝试提取JSON部分
            json_match = re.search(r'\[.*\]', message, re.DOTALL)
            if json_match:
                agenda = json.loads(json_match.group())
            else:
                # 如果无法解析，返回空数组
                agenda = []

            return self._as_json({
                "status": "success",
                "agenda": agenda,
                "message": f"成功提取 {len(agenda)} 个议程项。",
            })

        except json.JSONDecodeError as e:
            return self._as_json({
                "status": "error",
                "error": f"JSON解析失败: {e}",
                "agenda": [],
                "message": "无法解析LLM返回的议程信息。",
            })
        except Exception as e:
            return self._as_json({
                "status": "error",
                "error": str(e),
                "agenda": [],
                "message": f"提取议程时发生错误: {e}",
            })

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("ExtractStructuredAgendaTool does not support async execution.")


class IdentifyActionItemsTool(ContextAwareTool):
    """识别讨论中的行动项和责任人的工具。"""

    name: str = "identify_action_items"
    description: str = (
        "识别讨论中的行动项和责任人。"
        "返回行动项列表，每个行动项包含：具体行动、负责人、截止时间等信息。"
    )
    args_schema: ClassVar[Type[IdentifyActionItemsInput]] = IdentifyActionItemsInput

    def __init__(
        self,
        *,
        context: Optional[ToolContext] = None,
        llm_service: Optional[DoubaoService] = None,
        **kwargs,
    ) -> None:
        super().__init__(context=context, **kwargs)
        if not LLM_AVAILABLE:
            self._llm_service = None
            self._initialization_error = "LLM service not available"
        else:
            try:
                self._llm_service = llm_service or DoubaoService()
            except Exception as e:
                self._llm_service = None
                self._initialization_error = str(e)

    def _run(self, discussion_text: str) -> str:
        if self._llm_service is None:
            error_msg = getattr(self, "_initialization_error", "LLM service not initialized")
            return self._as_json({
                "error": error_msg,
                "message": "LLM 服务未配置，无法识别行动项。",
            })

        try:
            prompt = f"""请从以下会议讨论文本中识别行动项和责任人。

讨论内容：
{discussion_text}

请识别所有行动项，返回JSON格式，每个行动项包含以下字段：
- action: 具体行动内容
- owner: 负责人（如果有明确指定）
- deadline: 截止时间（如果有明确指定）

如果没有明确的行动项，返回空数组。

只返回JSON数组，不要其他说明文字。格式示例：
[
  {{"action": "完成项目文档", "owner": "张三", "deadline": "2024-01-15"}},
  {{"action": "准备技术方案", "owner": "李四", "deadline": "下周"}}
]"""

            response = self._llm_service.complete(
                prompt,
                system_prompt="你是一个专业的会议助手，擅长从讨论中识别行动项和责任分配。",
                temperature=0.3,
            )

            # 尝试解析JSON响应
            message = response.get("message", "")
            json_match = re.search(r'\[.*\]', message, re.DOTALL)
            if json_match:
                action_items = json.loads(json_match.group())
            else:
                action_items = []

            return self._as_json({
                "status": "success",
                "action_items": action_items,
                "message": f"成功识别 {len(action_items)} 个行动项。",
            })

        except json.JSONDecodeError as e:
            return self._as_json({
                "status": "error",
                "error": f"JSON解析失败: {e}",
                "action_items": [],
                "message": "无法解析LLM返回的行动项信息。",
            })
        except Exception as e:
            return self._as_json({
                "status": "error",
                "error": str(e),
                "action_items": [],
                "message": f"识别行动项时发生错误: {e}",
            })

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("IdentifyActionItemsTool does not support async execution.")


class ExtractDecisionsTool(ContextAwareTool):
    """提取会议中的决策和结论的工具。"""

    name: str = "extract_decisions"
    description: str = (
        "提取会议中的决策和结论。"
        "返回决策列表，每个决策包含：决策内容、依据、影响等信息。"
    )
    args_schema: ClassVar[Type[ExtractDecisionsInput]] = ExtractDecisionsInput

    def __init__(
        self,
        *,
        context: Optional[ToolContext] = None,
        llm_service: Optional[DoubaoService] = None,
        **kwargs,
    ) -> None:
        super().__init__(context=context, **kwargs)
        if not LLM_AVAILABLE:
            self._llm_service = None
            self._initialization_error = "LLM service not available"
        else:
            try:
                self._llm_service = llm_service or DoubaoService()
            except Exception as e:
                self._llm_service = None
                self._initialization_error = str(e)

    def _run(self, text: str) -> str:
        if self._llm_service is None:
            error_msg = getattr(self, "_initialization_error", "LLM service not initialized")
            return self._as_json({
                "error": error_msg,
                "message": "LLM 服务未配置，无法提取决策。",
            })

        try:
            prompt = f"""请从以下会议文本中提取决策和结论。

文本内容：
{text}

请识别所有决策，返回JSON格式，每个决策包含以下字段：
- decision: 决策内容
- basis: 决策依据（如果有）
- impact: 影响范围（如果有）

如果没有明确的决策，返回空数组。

只返回JSON数组，不要其他说明文字。格式示例：
[
  {{"decision": "采用方案A", "basis": "成本更低，实施周期短", "impact": "项目预算减少20%"}},
  {{"decision": "延期发布", "basis": "测试未完成", "impact": "发布时间推迟2周"}}
]"""

            response = self._llm_service.complete(
                prompt,
                system_prompt="你是一个专业的会议助手，擅长从文本中提取决策和结论。",
                temperature=0.3,
            )

            # 尝试解析JSON响应
            message = response.get("message", "")
            json_match = re.search(r'\[.*\]', message, re.DOTALL)
            if json_match:
                decisions = json.loads(json_match.group())
            else:
                decisions = []

            return self._as_json({
                "status": "success",
                "decisions": decisions,
                "message": f"成功提取 {len(decisions)} 个决策。",
            })

        except json.JSONDecodeError as e:
            return self._as_json({
                "status": "error",
                "error": f"JSON解析失败: {e}",
                "decisions": [],
                "message": "无法解析LLM返回的决策信息。",
            })
        except Exception as e:
            return self._as_json({
                "status": "error",
                "error": str(e),
                "decisions": [],
                "message": f"提取决策时发生错误: {e}",
            })

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("ExtractDecisionsTool does not support async execution.")


class SummarizeKeyPointsTool(ContextAwareTool):
    """总结会议核心要点的工具。"""

    name: str = "summarize_key_points"
    description: str = (
        "总结会议核心要点。"
        "返回包含关键决策、行动项、开放问题等结构化摘要。"
    )
    args_schema: ClassVar[Type[SummarizeKeyPointsInput]] = SummarizeKeyPointsInput

    def __init__(
        self,
        *,
        context: Optional[ToolContext] = None,
        llm_service: Optional[DoubaoService] = None,
        **kwargs,
    ) -> None:
        super().__init__(context=context, **kwargs)
        if not LLM_AVAILABLE:
            self._llm_service = None
            self._initialization_error = "LLM service not available"
        else:
            try:
                self._llm_service = llm_service or DoubaoService()
            except Exception as e:
                self._llm_service = None
                self._initialization_error = str(e)

    def _run(self, full_text: str) -> str:
        if self._llm_service is None:
            error_msg = getattr(self, "_initialization_error", "LLM service not initialized")
            return self._as_json({
                "error": error_msg,
                "message": "LLM 服务未配置，无法总结要点。",
            })

        try:
            prompt = f"""请总结以下会议文本的核心要点。

会议文本：
{full_text}

请返回JSON格式，包含以下字段：
- key_decisions: 关键决策列表（字符串数组）
- action_items: 行动项列表（字符串数组）
- open_questions: 开放问题列表（字符串数组）

只返回JSON对象，不要其他说明文字。格式示例：
{{
  "key_decisions": ["采用方案A", "延期发布"],
  "action_items": ["完成项目文档 - 张三 - 2024-01-15", "准备技术方案 - 李四 - 下周"],
  "open_questions": ["如何优化性能？", "预算是否充足？"]
}}"""

            response = self._llm_service.complete(
                prompt,
                system_prompt="你是一个专业的会议助手，擅长总结会议核心要点。",
                temperature=0.3,
            )

            # 尝试解析JSON响应
            message = response.get("message", "")
            json_match = re.search(r'\{.*\}', message, re.DOTALL)
            if json_match:
                summary = json.loads(json_match.group())
            else:
                summary = {
                    "key_decisions": [],
                    "action_items": [],
                    "open_questions": [],
                }

            return self._as_json({
                "status": "success",
                "summary": summary,
                "message": "成功总结会议要点。",
            })

        except json.JSONDecodeError as e:
            return self._as_json({
                "status": "error",
                "error": f"JSON解析失败: {e}",
                "summary": {
                    "key_decisions": [],
                    "action_items": [],
                    "open_questions": [],
                },
                "message": "无法解析LLM返回的总结信息。",
            })
        except Exception as e:
            return self._as_json({
                "status": "error",
                "error": str(e),
                "summary": {
                    "key_decisions": [],
                    "action_items": [],
                    "open_questions": [],
                },
                "message": f"总结要点时发生错误: {e}",
            })

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("SummarizeKeyPointsTool does not support async execution.")

