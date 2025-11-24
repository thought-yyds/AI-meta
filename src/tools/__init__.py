"""Tool implementations available to agents."""

from .base import ContextAwareTool, ToolContext, ToolExecutionError
from .calendar import CalendarTool
from .github import GitHubRepoTool
from .mailtool import EmailSenderTool
from .meeting import (
    AutoCaptureImportantRegionsTool,
    CaptureSlideContentTool,
    CaptureSpecificRegionTool,
    CreateMeetingTool,
    ExtractDecisionsTool,
    ExtractStructuredAgendaTool,
    IdentifyActionItemsTool,
    JoinMeetingTool,
    MonitorScreenChangesTool,
    SummarizeKeyPointsTool,
)
from .parser import FileParserTool
from .retrieval import LocalRetrievalTool
from .web import TavilyWebTool
__all__ = [
    "ContextAwareTool",
    "ToolContext",
    "ToolExecutionError",
    "FileParserTool",
    "LocalRetrievalTool",
    "TavilyWebTool",
    "GitHubRepoTool",
    "EmailSenderTool",
    "CalendarTool",
    "CreateMeetingTool",
    "JoinMeetingTool",
    # Meeting capture tools
    "CaptureSlideContentTool",
    "CaptureSpecificRegionTool",
    "AutoCaptureImportantRegionsTool",
    "MonitorScreenChangesTool",
    # Content parser tools
    "ExtractStructuredAgendaTool",
    "IdentifyActionItemsTool",
    "ExtractDecisionsTool",
    "SummarizeKeyPointsTool",
]

