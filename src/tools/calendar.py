"""Calendar event creation tool for adding reminders to calendar applications."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar, Optional, Type
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator

from .base import ContextAwareTool, ToolExecutionError


class CalendarEventInput(BaseModel):
    """Schema describing the expected arguments for the calendar event tool."""

    title: str = Field(..., description="Event title or reminder subject.")
    description: Optional[str] = Field(None, description="Optional event description or notes.")
    start_time: str = Field(
        ...,
        description=(
            "Event start time in ISO format (YYYY-MM-DDTHH:MM:SS) or "
            "relative format like 'tomorrow 14:00', 'next Monday 9:00', 'in 2 hours'."
        ),
    )
    duration_minutes: int = Field(
        60,
        description="Event duration in minutes. Default is 60 minutes.",
    )
    reminder_minutes: Optional[int] = Field(
        15,
        description=(
            "Reminder time in minutes before the event. "
            "Set to None to disable reminder. Default is 15 minutes."
        ),
    )
    location: Optional[str] = Field(None, description="Optional event location.")
    output_dir: Optional[str] = Field(
        None,
        description="Directory to save the calendar file. Defaults to ./calendar.",
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


class CalendarTool(ContextAwareTool):
    """Create calendar event files (iCal format) that can be imported into calendar applications."""

    name: str = "add_calendar_event"
    description: str = (
        "Create a calendar event file (.ics) that can be imported into calendar applications "
        "(Google Calendar, Outlook, Apple Calendar, etc.). Supports reminders and event details."
    )
    args_schema: ClassVar[Type[CalendarEventInput]] = CalendarEventInput

    def _parse_time(self, time_str: str) -> datetime:
        """Parse time string into datetime object."""
        time_str = time_str.strip()

        # Try ISO format first
        try:
            if "T" in time_str:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
                return dt
        except ValueError:
            pass

        # Try relative formats
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        time_lower = time_str.lower()

        # Handle "in X hours/minutes"
        if time_lower.startswith("in "):
            parts = time_lower[3:].split()
            if len(parts) >= 2:
                try:
                    amount = int(parts[0])
                    unit = parts[1]
                    if unit.startswith("hour"):
                        return now + timedelta(hours=amount)
                    elif unit.startswith("minute"):
                        return now + timedelta(minutes=amount)
                    elif unit.startswith("day"):
                        return now + timedelta(days=amount)
                except (ValueError, IndexError):
                    pass

        # Handle "tomorrow HH:MM" or "next Monday HH:MM"
        if time_lower.startswith("tomorrow"):
            target_date = now.date() + timedelta(days=1)
            time_part = time_str[8:].strip()
            if time_part:
                try:
                    hour, minute = map(int, time_part.split(":"))
                    return datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute)).replace(
                        tzinfo=ZoneInfo("Asia/Shanghai")
                    )
                except (ValueError, IndexError):
                    pass
            return datetime.combine(target_date, datetime.min.time()).replace(tzinfo=ZoneInfo("Asia/Shanghai"))

        # Handle "next [weekday] HH:MM"
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if time_lower.startswith("next "):
            for i, day in enumerate(weekdays):
                if time_lower.startswith(f"next {day}"):
                    days_ahead = (i - now.weekday()) % 7
                    if days_ahead == 0:
                        days_ahead = 7  # Next week
                    target_date = now.date() + timedelta(days=days_ahead)
                    time_part = time_str[len(f"next {day}"):].strip()
                    if time_part:
                        try:
                            hour, minute = map(int, time_part.split(":"))
                            return datetime.combine(
                                target_date, datetime.min.time().replace(hour=hour, minute=minute)
                            ).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
                        except (ValueError, IndexError):
                            pass
                    return datetime.combine(target_date, datetime.min.time()).replace(
                        tzinfo=ZoneInfo("Asia/Shanghai")
                    )

        # Try simple date format YYYY-MM-DD or YYYY-MM-DD HH:MM
        try:
            if " " in time_str:
                date_part, time_part = time_str.split(" ", 1)
                date_obj = datetime.strptime(date_part, "%Y-%m-%d").date()
                time_obj = datetime.strptime(time_part, "%H:%M").time()
                return datetime.combine(date_obj, time_obj).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
            else:
                date_obj = datetime.strptime(time_str, "%Y-%m-%d").date()
                return datetime.combine(date_obj, datetime.min.time()).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        except ValueError:
            pass

        raise ToolExecutionError(
            f"Unable to parse time string: '{time_str}'. "
            "Supported formats: ISO (YYYY-MM-DDTHH:MM:SS), 'tomorrow HH:MM', "
            "'next Monday HH:MM', 'in X hours', or 'YYYY-MM-DD HH:MM'."
        )

    def _generate_ics_content(
        self,
        title: str,
        description: Optional[str],
        start_dt: datetime,
        end_dt: datetime,
        reminder_minutes: Optional[int],
        location: Optional[str],
    ) -> str:
        """Generate iCal file content."""
        # Format datetime for iCal (UTC format)
        def format_ical_datetime(dt: datetime) -> str:
            return dt.strftime("%Y%m%dT%H%M%S")

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//AI Agent//Calendar Tool//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:{start_dt.strftime('%Y%m%d%H%M%S')}@ai-agent",
            f"DTSTART:{format_ical_datetime(start_dt)}",
            f"DTEND:{format_ical_datetime(end_dt)}",
            f"DTSTAMP:{format_ical_datetime(datetime.now(ZoneInfo('Asia/Shanghai')))}",
            f"SUMMARY:{self._escape_ical_text(title)}",
        ]

        if description:
            lines.append(f"DESCRIPTION:{self._escape_ical_text(description)}")

        if location:
            lines.append(f"LOCATION:{self._escape_ical_text(location)}")

        if reminder_minutes is not None and reminder_minutes >= 0:
            lines.extend(
                [
                    "BEGIN:VALARM",
                    "TRIGGER:-PT{}M".format(reminder_minutes),
                    "ACTION:DISPLAY",
                    f"DESCRIPTION:Reminder: {self._escape_ical_text(title)}",
                    "END:VALARM",
                ]
            )

        lines.extend(["END:VEVENT", "END:VCALENDAR"])

        return "\r\n".join(lines)

    @staticmethod
    def _escape_ical_text(text: str) -> str:
        """Escape special characters for iCal format."""
        return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")

    def _run(
        self,
        title: str,
        start_time: str,
        description: Optional[str] = None,
        duration_minutes: int = 60,
        reminder_minutes: Optional[int] = 15,
        location: Optional[str] = None,
        output_dir: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> str:
        start_dt = self._parse_time(start_time)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        working_dir = Path(self.context.working_dir or Path.cwd())
        resolved_output_dir = (
            (working_dir / output_dir).resolve() if output_dir else (working_dir / "calendar").resolve()
        )
        resolved_output_dir.mkdir(parents=True, exist_ok=True)

        if filename:
            resolved_filename = filename if filename.endswith(".ics") else f"{filename}.ics"
        else:
            # Generate filename from title
            slug = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in title.lower())[:32]
            if not slug:
                slug = "event"
            timestamp = start_dt.strftime("%Y%m%d-%H%M")
            resolved_filename = f"{timestamp}-{slug}.ics"

        file_path = resolved_output_dir / resolved_filename

        ics_content = self._generate_ics_content(
            title=title,
            description=description,
            start_dt=start_dt,
            end_dt=end_dt,
            reminder_minutes=reminder_minutes,
            location=location,
        )

        try:
            file_path.write_text(ics_content, encoding="utf-8")
        except OSError as exc:  # noqa: BLE001
            raise ToolExecutionError(f"Failed to write calendar file: {exc}") from exc

        return self._as_json(
            {
                "status": "created",
                "path": str(file_path),
                "title": title,
                "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "duration_minutes": duration_minutes,
                "reminder_minutes": reminder_minutes,
                "location": location,
                "instructions": (
                    f"Calendar event file created at: {file_path}\n"
                    "To add to your calendar:\n"
                    "- Google Calendar: Go to Settings > Import & Export > Import, select the .ics file\n"
                    "- Outlook: File > Open & Export > Import/Export > Import an iCalendar (.ics) file\n"
                    "- Apple Calendar: Double-click the .ics file or File > Import\n"
                    "- Mobile: Email the file to yourself and open it on your device"
                ),
            }
        )

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("CalendarTool does not support async execution.")

