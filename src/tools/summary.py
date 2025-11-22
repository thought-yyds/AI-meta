"""Meeting summary generation tool implemented for LangChain."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, List, Optional, Sequence, Type

from pydantic import BaseModel, Field, model_validator

from .base import ContextAwareTool, ToolExecutionError


class MeetingSummaryInput(BaseModel):
    """Schema describing the expected arguments for the meeting summary tool."""

    title: Optional[str] = Field(None, description="Optional meeting title.")
    key_points: Optional[Sequence[str]] = Field(
        None, description="Key discussion points as a list or newline-separated string."
    )
    decisions: Optional[Sequence[str]] = Field(
        None, description="Decisions made, provided as list or newline-separated string."
    )
    action_items: Optional[Sequence[str]] = Field(
        None, description="Action items with owners / due dates."
    )
    output_dir: Optional[str] = Field(
        None, description="Directory for the summary file. Defaults to ./summaries."
    )
    filename: Optional[str] = Field(
        None, description="Filename (without directory). Defaults to timestamped slug."
    )

    @model_validator(mode="before")
    def normalize_strings(cls, values: Any) -> Any:  # noqa: D401
        if not isinstance(values, dict):
            return values

        def ensure_list(value: object, field: str) -> List[str]:
            if value is None:
                return []
            if isinstance(value, str):
                stripped = value.strip()
                if not stripped:
                    return []
                return [line.strip() for line in stripped.splitlines() if line.strip()]
            if isinstance(value, (list, tuple, set)):
                return [str(item).strip() for item in value if str(item).strip()]
            raise ToolExecutionError(f"Parameter '{field}' must be a string or list of strings.")

        for key in ("key_points", "decisions", "action_items"):
            if key in values:
                values[key] = ensure_list(values[key], field=key)
        return values


class MeetingSummaryTool(ContextAwareTool):
    """Create a markdown summary document capturing meeting highlights."""

    name: str = "meeting_summary"
    description: str = (
        "Persist meeting summaries to a Markdown file. Accepts key points, decisions, and action items."
    )
    args_schema: ClassVar[Type[MeetingSummaryInput]] = MeetingSummaryInput

    def _run(
        self,
        title: Optional[str] = None,
        key_points: Optional[Sequence[str]] = None,
        decisions: Optional[Sequence[str]] = None,
        action_items: Optional[Sequence[str]] = None,
        output_dir: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> str:
        safe_title = title or "Meeting Summary"
        key_points_list = list(key_points or [])
        decisions_list = list(decisions or [])
        action_items_list = list(action_items or [])

        working_dir = Path(self.context.working_dir or Path.cwd())
        resolved_output_dir = (
            (working_dir / output_dir).resolve() if output_dir else (working_dir / "summaries").resolve()
        )
        resolved_output_dir.mkdir(parents=True, exist_ok=True)

        if filename:
            resolved_filename = filename if filename.endswith(".md") else f"{filename}.md"
        else:
            slug = safe_title.lower().strip().replace(" ", "-")[:32] or "meeting"
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            resolved_filename = f"{timestamp}-{slug}.md"

        file_path = resolved_output_dir / resolved_filename

        lines: List[str] = [f"# {safe_title}", ""]
        if key_points_list:
            lines.append("## Key Points")
            lines.extend(f"- {item}" for item in key_points_list)
            lines.append("")
        if decisions_list:
            lines.append("## Decisions")
            lines.extend(f"- {item}" for item in decisions_list)
            lines.append("")
        if action_items_list:
            lines.append("## Action Items")
            lines.extend(f"- {item}" for item in action_items_list)
            lines.append("")

        content = "\n".join(lines).strip() + "\n"

        try:
            file_path.write_text(content, encoding="utf-8")
        except OSError as exc:  # noqa: BLE001
            raise ToolExecutionError(f"Failed to write summary file: {exc}") from exc

        return self._as_json(
            {
                "path": str(file_path),
                "title": safe_title,
                "key_points_count": len(key_points_list),
                "decisions_count": len(decisions_list),
                "action_items_count": len(action_items_list),
                "preview": content[:500],
            }
        )

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("MeetingSummaryTool does not support async execution.")

