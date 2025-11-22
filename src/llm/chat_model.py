"""LangChain chat model wrapper for the Doubao client."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from .client import DoubaoService, DoubaoServiceError


class DoubaoChatModel(BaseChatModel):
    """LangChain-compatible chat model wrapper around `DoubaoService`."""

    service: DoubaoService
    temperature: float = 0.2
    bound_tools: Optional[List[BaseTool]] = None

    def __init__(
        self,
        *,
        service: DoubaoService,
        temperature: float = 0.2,
        bound_tools: Optional[List[BaseTool]] = None,
    ) -> None:
        super().__init__(service=service, temperature=temperature, bound_tools=bound_tools)

    @property
    def _llm_type(self) -> str:
        return "doubao-chat"

    def bind_tools(
        self,
        tools: Sequence[BaseTool],
        **kwargs: Any,  # noqa: ANN401
    ) -> Runnable:
        """
        Bind tools to the model for function calling support.

        Returns a new model instance with tools bound.
        """
        return DoubaoChatModel(
            service=self.service,
            temperature=self.temperature,
            bound_tools=list(tools),
        )

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,  # noqa: ANN401
        **kwargs: Any,
    ) -> ChatResult:
        payload = [self._convert_message(m) for m in messages]

        extra_body = {}
        if stop:
            extra_body["stop_sequences"] = stop

        # Convert tools to API format if bound_tools is set
        tools = None
        if self.bound_tools:
            tools = [self._tool_to_api_format(tool) for tool in self.bound_tools]

        try:
            response = self.service.chat(
                payload,
                temperature=self.temperature,
                tools=tools,
                extra_body=extra_body or None,
            )
        except DoubaoServiceError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DoubaoServiceError(f"Doubao chat request failed: {exc}") from exc

        text = response.get("message", "")
        tool_calls = response.get("tool_calls")

        # Create AIMessage with tool calls if present
        if tool_calls:
            # Convert API tool_calls format to LangChain format
            langchain_tool_calls = []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    langchain_tool_calls.append(
                        {
                            "name": tc.get("function", {}).get("name", ""),
                            "args": self._parse_tool_args(tc.get("function", {}).get("arguments", "{}")),
                            "id": tc.get("id", ""),
                        }
                    )
            ai_message = AIMessage(content=text or "", tool_calls=langchain_tool_calls)
        else:
            ai_message = AIMessage(content=text if isinstance(text, str) else str(text))

        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    @staticmethod
    def _tool_to_api_format(tool: BaseTool) -> Dict[str, Any]:
        """Convert LangChain BaseTool to API tool format."""
        # Get the tool's input schema
        args_schema = tool.args_schema
        if args_schema:
            schema = args_schema.model_json_schema() if hasattr(args_schema, "model_json_schema") else {}
        else:
            schema = {"type": "object", "properties": {}}

        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": schema,
            },
        }

    @staticmethod
    def _parse_tool_args(args_str: str) -> Dict[str, Any]:
        """Parse tool arguments from JSON string."""
        if isinstance(args_str, dict):
            return args_str
        try:
            return json.loads(args_str) if args_str else {}
        except json.JSONDecodeError:
            return {"raw": args_str}

    def _convert_message(self, message: BaseMessage) -> dict:
        if isinstance(message, SystemMessage):
            role = "system"
        elif isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage):
            role = "assistant"
        elif isinstance(message, ToolMessage):
            role = "tool"
        else:
            role = "user"
        
        content = message.content
        if isinstance(content, list):
            text_parts = []
            for fragment in content:
                if isinstance(fragment, dict) and "text" in fragment:
                    text_parts.append(str(fragment["text"]))
                else:
                    text_parts.append(str(fragment))
            content = "".join(text_parts)
        elif not isinstance(content, str):
            content = str(content)
        
        result = {"role": role, "content": content}
        
        # Handle tool_calls for AIMessage
        if isinstance(message, AIMessage) and hasattr(message, "tool_calls") and message.tool_calls:
            # Convert LangChain tool_calls format to API format
            api_tool_calls = []
            for tc in message.tool_calls:
                if isinstance(tc, dict):
                    api_tool_calls.append({
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tc.get("name", ""),
                            "arguments": json.dumps(tc.get("args", {}), ensure_ascii=False),
                        },
                    })
            if api_tool_calls:
                result["tool_calls"] = api_tool_calls
        
        # Handle ToolMessage
        if isinstance(message, ToolMessage):
            result["tool_call_id"] = getattr(message, "tool_call_id", "")
            result["name"] = getattr(message, "name", "")
        
        return result


