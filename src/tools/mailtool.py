"""SMTP email sending tool for meeting agents."""

from __future__ import annotations

import mimetypes
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import ClassVar, List, Optional, Sequence, Type

from pydantic import BaseModel, Field, model_validator

from .base import ContextAwareTool, ToolContext, ToolExecutionError

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


def _normalize_addresses(addresses: Sequence[str]) -> List[str]:
    normalized = []
    for address in addresses:
        addr = address.strip()
        if addr:
            normalized.append(addr)
    return normalized


class EmailAttachment(BaseModel):
    """Attachment metadata for outgoing emails."""

    path: str = Field(..., description="Path to the file relative to the working directory.")
    filename: Optional[str] = Field(
        None,
        description="Optional filename override. Defaults to the actual filename.",
    )


class SendEmailInput(BaseModel):
    """Input schema for sending emails via SMTP."""

    to: List[str] = Field(..., description="List of recipient email addresses.")
    subject: str = Field(..., description="Subject line of the email.")
    body: str = Field(..., description="Email body content, plain text or HTML.")
    cc: List[str] = Field(default_factory=list, description="Optional CC recipients.")
    bcc: List[str] = Field(default_factory=list, description="Optional BCC recipients.")
    body_type: str = Field(
        "plain",
        description="Email body format: 'plain' for text or 'html' for HTML content.",
    )
    attachments: List[EmailAttachment] = Field(
        default_factory=list,
        description="Optional list of attachments referenced by relative paths.",
    )

    @model_validator(mode="after")
    def _validate_recipients(self) -> "SendEmailInput":
        if not _normalize_addresses(self.to):
            msg = "Parameter 'to' must include at least one valid email address."
            raise ValueError(msg)
        body_type = self.body_type.lower().strip()
        if body_type not in {"plain", "html"}:
            msg = "Parameter 'body_type' must be either 'plain' or 'html'."
            raise ValueError(msg)
        self.body_type = body_type
        return self


class EmailSenderTool(ContextAwareTool):
    """Send meeting notes or updates via SMTP email."""

    name: str = "send_email"
    description: str = (
        "Send an email with optional CC/BCC recipients and attachments using the configured SMTP server."
    )
    args_schema: ClassVar[Type[SendEmailInput]] = SendEmailInput

    def __init__(
        self,
        *,
        context: Optional[ToolContext] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        sender_address: Optional[str] = None,
        use_ssl: Optional[bool] = None,
        use_tls: Optional[bool] = None,
        **kwargs,
    ) -> None:
        super().__init__(context=context, **kwargs)
        self._load_env()
        self._smtp_host = smtp_host or os.getenv("SMTP_HOST")
        self._smtp_port = smtp_port or self._parse_int(os.getenv("SMTP_PORT"))
        self._smtp_user = smtp_user or os.getenv("SMTP_USERNAME")
        self._smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self._sender_address = sender_address or os.getenv("SMTP_SENDER") or self._smtp_user
        self._use_ssl = use_ssl if use_ssl is not None else self._parse_bool(os.getenv("SMTP_USE_SSL", "false"))
        self._use_tls = use_tls if use_tls is not None else self._parse_bool(os.getenv("SMTP_USE_TLS", "true"))

    @staticmethod
    def _load_env() -> None:
        if load_dotenv is not None:
            load_dotenv(override=False)

    @staticmethod
    def _parse_int(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError as exc:  # pragma: no cover - simple validation helper
            raise ToolExecutionError(f"Invalid SMTP_PORT value: {value}") from exc

    @staticmethod
    def _parse_bool(value: str) -> bool:
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def _ensure_config(self) -> None:
        missing = []
        if not self._smtp_host:
            missing.append("SMTP_HOST")
        if not self._smtp_port:
            missing.append("SMTP_PORT")
        if not self._sender_address:
            missing.append("SMTP_SENDER or SMTP_USERNAME")
        if missing:
            readable = ", ".join(missing)
            raise ToolExecutionError(
                f"SMTP configuration incomplete. Please set environment variables: {readable}."
            )

    def _run(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        body_type: str = "plain",
        attachments: Optional[List[EmailAttachment]] = None,
    ) -> str:
        self._ensure_config()

        to_addresses = _normalize_addresses(to)
        cc_addresses = _normalize_addresses(cc or [])
        bcc_addresses = _normalize_addresses(bcc or [])

        if not to_addresses:
            raise ToolExecutionError("Parameter 'to' must include at least one valid email address.")

        message = EmailMessage()
        message["Subject"] = subject.strip()
        message["From"] = self._sender_address
        message["To"] = ", ".join(to_addresses)
        if cc_addresses:
            message["Cc"] = ", ".join(cc_addresses)

        body_content = body.strip()
        if not body_content:
            raise ToolExecutionError("Parameter 'body' must be a non-empty string.")

        message.set_content(body_content, subtype=body_type)

        attached_files = self._attach_files(message, attachments or [])

        self._send_via_smtp(message, to_addresses + cc_addresses + bcc_addresses)

        payload = {
            "status": "sent",
            "recipients": {"to": to_addresses, "cc": cc_addresses, "bcc": len(bcc_addresses)},
            "attachments": attached_files,
        }
        return self._as_json(payload)

    def _attach_files(self, message: EmailMessage, attachments: Sequence[EmailAttachment]) -> List[str]:
        attached: List[str] = []
        if not attachments:
            return attached

        working_dir = Path(self.context.working_dir or Path.cwd())
        for attachment in attachments:
            file_path = (working_dir / attachment.path).resolve()
            if not file_path.exists():
                raise ToolExecutionError(f"Attachment not found: {file_path}")
            if not file_path.is_file():
                raise ToolExecutionError(f"Attachment must be a file: {file_path}")

            filename = attachment.filename or file_path.name
            mime_type, _ = mimetypes.guess_type(filename)
            maintype, subtype = (mime_type.split("/", 1) if mime_type else ("application", "octet-stream"))

            try:
                with file_path.open("rb") as fh:
                    data = fh.read()
            except Exception as exc:  # noqa: BLE001
                raise ToolExecutionError(f"Failed to read attachment '{file_path}': {exc}") from exc

            message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
            attached.append(filename)

        return attached

    def _send_via_smtp(self, message: EmailMessage, recipients: Sequence[str]) -> None:
        try:
            if self._use_ssl:
                server: smtplib.SMTP = smtplib.SMTP_SSL(self._smtp_host, self._smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=30)
        except Exception as exc:  # noqa: BLE001
            raise ToolExecutionError(f"Failed to connect to SMTP server: {exc}") from exc

        try:
            server.ehlo()
            if not self._use_ssl and self._use_tls:
                server.starttls()
                server.ehlo()
            if self._smtp_user and self._smtp_password:
                server.login(self._smtp_user, self._smtp_password)
            server.send_message(message, to_addrs=list(recipients))
        except Exception as exc:  # noqa: BLE001
            raise ToolExecutionError(f"Failed to send email: {exc}") from exc
        finally:
            try:
                server.quit()
            except Exception:  # noqa: BLE001
                server.close()

    async def _arun(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise NotImplementedError("EmailSenderTool does not support async execution.")


