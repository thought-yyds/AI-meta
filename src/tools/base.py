"""Base classes and helpers for LangChain-compatible agent tools."""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field
from langchain.tools import BaseTool
from langchain_core.tools import ToolException


class ToolExecutionError(ToolException):
    """Raised when a tool cannot complete its requested action."""


class ToolContext(BaseModel):
    """Container for contextual information passed to tools."""

    working_dir: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ContextAwareTool(BaseTool):
    """LangChain `BaseTool` with shared helpers and working directory support."""

    context: ToolContext = Field(default_factory=ToolContext)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, *, context: Optional[ToolContext] = None, **kwargs: Any) -> None:
        super().__init__(context=context or ToolContext(), **kwargs)

    @staticmethod
    def _as_json(payload: Mapping[str, Any]) -> str:
        try:
            return json.dumps(payload, ensure_ascii=False)
        except TypeError as exc:  # noqa: BLE001
            raise ToolExecutionError(f"Tool result is not JSON serializable: {exc}") from exc

