"""
Client helper for invoking Doubao large models via Volcano Engine Ark.

The Ark platform expects HTTP requests with an Authorization bearer token.
This module wraps the REST API with a small convenience layer that can be
plugged into the project agents as their "brain".

Environment variables (place in `.env` and load with `dotenv` if desired):
    - ARK_API_KEY:      required, bearer token provided by Volcano Engine.
    - ARK_MODEL_NAME:   required, e.g. `doubao-lite-4k` or `doubao-pro-32k`.
    - ARK_API_BASE:     optional, defaults to the public Ark endpoint.
    - ARK_TIMEOUT:      optional, request timeout in seconds (float).
    - ARK_TEMPERATURE:  optional, fallback sampling temperature (float).
    - ARK_MAX_OUTPUT_TOKENS: optional, default upper bound for generation.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence

import httpx


logger = logging.getLogger(__name__)


def _load_env_from_default_file() -> None:
    """
    Load environment variables from a `.env` file located at the project root.

    Existing environment variables are left untouched so that explicitly
    provided values take precedence over the file.
    """
    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / ".env"
    if not env_path.is_file():
        return

    try:
        with env_path.open("r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key or key in os.environ:
                    continue
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                os.environ[key] = value
    except OSError:
        # Silently ignore IO errors – the service will raise a clearer error if
        # required keys remain missing.
        return


_load_env_from_default_file()


class DoubaoServiceError(RuntimeError):
    """Raised when the Ark Doubao backend responds with an error."""


@dataclass(frozen=True)
class DoubaoConfig:
    """Typed configuration bundle for the Ark Doubao client."""

    api_key: str
    model: str
    api_base: str = "https://ark.cn-beijing.volces.com/api/v3"
    timeout: float = 30.0
    temperature: float = 0.7
    max_output_tokens: Optional[int] = None

    @classmethod
    def from_env(cls) -> "DoubaoConfig":
        """
        Construct a config from environment variables.

        Raises:
            ValueError: when required fields are missing.
        """
        api_key = os.getenv("ARK_API_KEY")
        model = os.getenv("ARK_MODEL_NAME")

        if not api_key:
            raise ValueError("Missing required env var `ARK_API_KEY` for Doubao.")
        if not model:
            raise ValueError("Missing required env var `ARK_MODEL_NAME` for Doubao.")

        api_base = os.getenv("ARK_API_BASE", cls.api_base)
        timeout = float(os.getenv("ARK_TIMEOUT", cls.timeout))
        temperature = float(os.getenv("ARK_TEMPERATURE", cls.temperature))

        max_tokens_raw = os.getenv("ARK_MAX_OUTPUT_TOKENS")
        max_tokens = int(max_tokens_raw) if max_tokens_raw else None

        return cls(
            api_key=api_key,
            model=model,
            api_base=api_base,
            timeout=timeout,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )


class DoubaoService:
    """
    Lightweight wrapper around the Ark chat completions API.

    Usage:
        service = DoubaoService()  # loads config from env by default
        reply = service.complete("你好，请帮我总结会议纪要。")
    """

    _CHAT_PATH = "/chat/completions"

    def __init__(
        self,
        config: Optional[DoubaoConfig] = None,
        *,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.config = config or DoubaoConfig.from_env()
        self._client = client or httpx.Client(
            base_url=self.config.api_base,
            timeout=self.config.timeout,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )
        self._owns_client = client is None

    def __enter__(self) -> "DoubaoService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client if we created it."""
        if self._owns_client and self._client is not None:
            self._client.close()

    def complete(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Dict[str, object]:
        """
        Convenience helper for single-turn prompts.

        Returns the parsed Ark response; for streaming, yields incremental text
        chunks via the `"stream"` key on the returned dict.
        """
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(
            messages,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            stream=stream,
        )

    def chat(
        self,
        messages: Sequence[Dict[str, object]],
        *,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        stream: bool = False,
        tools: Optional[List[Dict[str, object]]] = None,
        tool_choice: Optional[str] = None,
        extra_body: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        """
        Send a multi-turn chat completion request.

        Args:
            messages: list of {"role": "...", "content": "..."} pairs.
            temperature: optional override for sampling temperature.
            max_output_tokens: optional override for output length.
            stream: when True, returns a generator yielding text deltas.
            tools: optional list of tool definitions for function calling.
            tool_choice: optional tool choice mode ("auto", "none", or specific tool name).
            extra_body: advanced Ark parameters to merge into payload.

        Returns:
            Dict with keys:
                - "message": assistant message text (non-streaming)
                - "raw": original response payload (non-streaming)
                - "stream": generator yielding text (streaming mode only)
                - "tool_calls": list of tool calls if any (non-streaming)
        """
        ark_messages = [self._as_ark_message(m) for m in messages]
        payload: Dict[str, object] = {
            "model": self.config.model,
            "messages": ark_messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
        }

        if not any(m["role"] == "assistant" for m in reversed(ark_messages)):
            logger.warning("No assistant role found in payload messages; Doubao may reject the request.")

        if "thinking" not in payload:
            payload["thinking"] = {"type": "disabled"}

        # Add tools support for function calling
        if tools:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        logger.info(
            "Doubao payload prepared: last_role=%s, thinking=%s, messages=%d",
            ark_messages[-1]["role"] if ark_messages else "n/a",
            json.dumps(payload["thinking"]),
            len(ark_messages),
        )

        max_tokens = max_output_tokens if max_output_tokens is not None else self.config.max_output_tokens
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens

        if extra_body:
            payload.update(extra_body)

        if stream:
            generator = self._stream_request(payload)
            return {"stream": generator}

        response = self._client.post(self._CHAT_PATH, json=payload)
        if response.status_code >= 400:
            raise DoubaoServiceError(
                f"Doubao request failed with status {response.status_code}: {response.text}"
            )

        data = response.json()
        choice = self._extract_choice(data)
        message_obj = choice.get("message", {})
        message_text = message_obj.get("content", "")
        if isinstance(message_text, list):
            message_text = "".join(
                fragment.get("text", "") for fragment in message_text if isinstance(fragment, dict)
            )
        elif not isinstance(message_text, str):
            message_text = str(message_text)
        
        # Extract tool calls if present
        tool_calls = message_obj.get("tool_calls")
        result = {"message": message_text, "raw": data}
        if tool_calls:
            result["tool_calls"] = tool_calls
        return result

    def _stream_request(self, payload: Dict[str, object]) -> Iterator[str]:
        """Perform a streaming request and yield text deltas."""
        with self._client.stream(
            "POST", self._CHAT_PATH, json={**payload, "stream": True, "messages": payload["messages"]}
        ) as response:
            if response.status_code >= 400:
                body = response.read().decode("utf-8", errors="ignore")
                raise DoubaoServiceError(
                    f"Doubao stream failed with status {response.status_code}: {body}"
                )
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith(b"data:"):
                    content = line[len(b"data:") :].strip()
                    if content == b"[DONE]":
                        break
                    try:
                        event = json.loads(content)
                    except json.JSONDecodeError:
                        continue
                    choice = self._extract_choice(event)
                    delta = choice.get("delta") or choice.get("message") or {}
                    text_fragment = self._normalize_content(delta)
                    if text_fragment:
                        yield text_fragment

    @staticmethod
    def _as_ark_message(message: Dict[str, object]) -> Dict[str, object]:
        """Convert internal message schema -> Ark format."""
        role = message.get("role") or "user"
        content = message.get("content") or ""
        
        # Handle tool_calls if present (for assistant messages with function calling)
        tool_calls = message.get("tool_calls")
        if tool_calls and role == "assistant":
            # For assistant messages with tool calls, include tool_calls in the message
            result = {
                "role": role,
                "content": [
                    {
                        "type": "text",
                        "text": content if isinstance(content, str) else str(content),
                    }
                ] if content else [],
                "tool_calls": tool_calls,
            }
            return result
        
        # Handle tool role (for tool responses)
        if role == "tool":
            tool_call_id = message.get("tool_call_id")
            tool_name = message.get("name", "")
            return {
                "role": "tool",
                "content": [
                    {
                        "type": "text",
                        "text": content if isinstance(content, str) else str(content),
                    }
                ],
                "tool_call_id": tool_call_id,
                "name": tool_name,
            }
        
        # Standard message format
        # Ark expects a list of typed content fragments
        return {
            "role": role,
            "content": [
                {
                    "type": "text",
                    "text": content if isinstance(content, str) else str(content),
                }
            ],
        }

    @staticmethod
    def _extract_choice(payload: Dict[str, object]) -> Dict[str, object]:
        choices = payload.get("choices") or []
        if not isinstance(choices, list) or not choices:
            raise DoubaoServiceError(f"Unexpected Doubao response shape: {payload}")
        first = choices[0]
        if not isinstance(first, dict):
            raise DoubaoServiceError(f"Unexpected choice payload: {first!r}")
        return first

    @staticmethod
    def _normalize_content(delta: object) -> str:
        if isinstance(delta, dict):
            if "content" in delta and isinstance(delta["content"], list):
                return "".join(
                    fragment.get("text", "")
                    for fragment in delta["content"]
                    if isinstance(fragment, dict)
                )
            if "text" in delta and isinstance(delta["text"], str):
                return delta["text"]
        if isinstance(delta, str):
            return delta
        return ""


def stream_to_text(chunks: Iterable[str]) -> str:
    """Utility to concatenate streaming text fragments into a full string."""
    return "".join(chunks)


def main() -> None:
    """Basic CLI for manually exercising the Doubao service."""
    parser = argparse.ArgumentParser(description="Send a test prompt to Doubao via Ark.")
    parser.add_argument(
        "prompt",
        nargs="?",
        help="User prompt to send. When omitted, read from stdin.",
    )
    parser.add_argument(
        "--system",
        dest="system_prompt",
        help="Optional system prompt to prepend.",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Enable streaming mode and print incremental deltas.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        help="Override temperature for this request.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        help="Override maximum output tokens for this request.",
    )
    args = parser.parse_args()

    prompt_text = args.prompt
    if prompt_text is None:
        prompt_text = input("Enter prompt: ").strip()

    try:
        with DoubaoService() as client:
            if args.stream:
                result = client.complete(
                    prompt_text,
                    system_prompt=args.system_prompt,
                    temperature=args.temperature,
                    max_output_tokens=args.max_output_tokens,
                    stream=True,
                )
                stream = result["stream"]
                print("=== streaming response ===")
                for chunk in stream:
                    print(chunk, end="", flush=True)
                print()
            else:
                result = client.complete(
                    prompt_text,
                    system_prompt=args.system_prompt,
                    temperature=args.temperature,
                    max_output_tokens=args.max_output_tokens,
                )
                print("=== assistant response ===")
                print(result["message"])
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Doubao call failed: {exc}") from exc


if __name__ == "__main__":
    main()

