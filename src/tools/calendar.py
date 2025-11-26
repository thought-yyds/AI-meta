"""FastMCP service that creates calendar events (iCal files)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError, field_validator

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv(override=False)

BASE_WORKDIR = Path(os.getenv("PERSONAL_AGENT_WORKDIR", ".")).resolve()

app = FastMCP("calendar-tool")


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


class CalendarEventSchema(BaseModel):
    title: str = Field(..., description="Event title or reminder subject.")
    start_time: str = Field(
        ...,
        description=(
            "Event start time in ISO format (YYYY-MM-DDTHH:MM:SS) or relative format "
            "like 'tomorrow 14:00', 'next Monday 9:00', 'in 2 hours'."
        ),
    )
    description: Optional[str] = Field(None, description="Optional event description or notes.")
    duration_minutes: int = Field(60, description="Event duration in minutes. Default is 60 minutes.")
    reminder_minutes: Optional[int] = Field(
        15,
        description="Reminder time in minutes before the event. Set to None to disable reminder.",
    )
    location: Optional[str] = Field(None, description="Optional event location.")
    output_dir: Optional[str] = Field(
        None,
        description="Directory to save the calendar file. Defaults to ./calendar relative to working dir.",
    )
    filename: Optional[str] = Field(
        None,
        description="Filename for the calendar file (without extension). Defaults to event title slug.",
    )

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("duration_minutes must be a positive integer.")
        return v

    @field_validator("reminder_minutes")
    @classmethod
    def validate_reminder(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("reminder_minutes must be non-negative or None.")
        return v


@app.tool(name="add_calendar_event")
def add_calendar_event(
    title: str,
    start_time: str,
    description: Optional[str] = None,
    duration_minutes: int = 60,
    reminder_minutes: Optional[int] = 15,
    location: Optional[str] = None,
    output_dir: Optional[str] = None,
    filename: Optional[str] = None,
) -> Dict[str, object]:
    """Create an .ics file that can be imported into calendar applications."""
    try:
        params = CalendarEventSchema(
            title=title,
            start_time=start_time,
            description=description,
            duration_minutes=duration_minutes,
            reminder_minutes=reminder_minutes,
            location=location,
            output_dir=output_dir,
            filename=filename,
        )

        start_dt = _parse_time(params.start_time)
        end_dt = start_dt + timedelta(minutes=params.duration_minutes)

        output_dir = (
            (BASE_WORKDIR / params.output_dir).resolve()
            if params.output_dir
            else (BASE_WORKDIR / "calendar").resolve()
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        if params.filename:
            filename = params.filename if params.filename.endswith(".ics") else f"{params.filename}.ics"
        else:
            slug = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in params.title.lower())[:32] or "event"
            filename = f"{start_dt.strftime('%Y%m%d-%H%M')}-{slug}.ics"

        file_path = output_dir / filename
        ics_content = _generate_ics(
            title=params.title,
            description=params.description,
            start_dt=start_dt,
            end_dt=end_dt,
            reminder_minutes=params.reminder_minutes,
            location=params.location,
        )
        file_path.write_text(ics_content, encoding="utf-8")

        data = {
            "status": "created",
            "path": str(file_path),
            "title": params.title,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "duration_minutes": params.duration_minutes,
            "reminder_minutes": params.reminder_minutes,
            "location": params.location,
        }
        return MCPResponse(ok=True, data=data).to_dict()
    except ValidationError as exc:
        return MCPResponse(ok=False, error=str(exc)).to_dict()
    except Exception as exc:  # noqa: BLE001
        return MCPResponse(ok=False, error=str(exc)).to_dict()


def _parse_time(time_str: str) -> datetime:
    """Parse human-friendly time strings into timezone-aware datetime."""
    time_str = time_str.strip()

    # ISO format
    try:
        if "T" in time_str:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
            return dt
    except ValueError:
        pass

    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    lower = time_str.lower()

    if lower.startswith("in "):
        parts = lower[3:].split()
        if len(parts) >= 2:
            amount = int(parts[0])
            unit = parts[1]
            if unit.startswith("hour"):
                return now + timedelta(hours=amount)
            if unit.startswith("minute"):
                return now + timedelta(minutes=amount)
            if unit.startswith("day"):
                return now + timedelta(days=amount)

    if lower.startswith("tomorrow"):
        target_date = now.date() + timedelta(days=1)
        time_part = time_str[8:].strip()
        if time_part:
            hour, minute = map(int, time_part.split(":"))
            return datetime.combine(
                target_date, datetime.min.time().replace(hour=hour, minute=minute)
            ).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        return datetime.combine(target_date, datetime.min.time()).replace(tzinfo=ZoneInfo("Asia/Shanghai"))

    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if lower.startswith("next "):
        for i, day in enumerate(weekdays):
            name = f"next {day}"
            if lower.startswith(name):
                days_ahead = (i - now.weekday()) % 7 or 7
                target_date = now.date() + timedelta(days=days_ahead)
                time_part = time_str[len(name):].strip()
                if time_part:
                    hour, minute = map(int, time_part.split(":"))
                    return datetime.combine(
                        target_date, datetime.min.time().replace(hour=hour, minute=minute)
                    ).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
                return datetime.combine(target_date, datetime.min.time()).replace(tzinfo=ZoneInfo("Asia/Shanghai"))

    try:
        if " " in time_str:
            date_part, time_part = time_str.split(" ", 1)
            date_obj = datetime.strptime(date_part, "%Y-%m-%d").date()
            time_obj = datetime.strptime(time_part, "%H:%M").time()
            return datetime.combine(date_obj, time_obj).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        date_obj = datetime.strptime(time_str, "%Y-%m-%d").date()
        return datetime.combine(date_obj, datetime.min.time()).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    except ValueError as exc:
        raise RuntimeError(
            "Unable to parse time string. Supported formats: ISO, 'tomorrow HH:MM', "
            "'next Monday HH:MM', 'in X hours', or 'YYYY-MM-DD HH:MM'."
        ) from exc


def _generate_ics(
    title: str,
    description: Optional[str],
    start_dt: datetime,
    end_dt: datetime,
    reminder_minutes: Optional[int],
    location: Optional[str],
) -> str:
    def fmt(dt: datetime) -> str:
        return dt.strftime("%Y%m%dT%H%M%S")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Personal Agent//Calendar Tool//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{start_dt.strftime('%Y%m%d%H%M%S')}@personal-agent",
        f"DTSTART:{fmt(start_dt)}",
        f"DTEND:{fmt(end_dt)}",
        f"DTSTAMP:{fmt(datetime.now(ZoneInfo('Asia/Shanghai')))}",
        f"SUMMARY:{_escape_ical_text(title)}",
    ]

    if description:
        lines.append(f"DESCRIPTION:{_escape_ical_text(description)}")
    if location:
        lines.append(f"LOCATION:{_escape_ical_text(location)}")
    if reminder_minutes is not None and reminder_minutes >= 0:
        lines.extend(
            [
                "BEGIN:VALARM",
                f"TRIGGER:-PT{reminder_minutes}M",
                "ACTION:DISPLAY",
                f"DESCRIPTION:Reminder: {_escape_ical_text(title)}",
                "END:VALARM",
            ]
        )

    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    return "\r\n".join(lines)


def _escape_ical_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


if __name__ == "__main__":
    app.run()

