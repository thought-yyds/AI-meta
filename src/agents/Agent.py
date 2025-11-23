"""个人AI助手Agent，专注于办公会议等场景，通过工具调用帮助用户完成日常工作任务。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain.tools import BaseTool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

try:
    from ..llm.chat_model import DoubaoChatModel
    from ..llm.client import DoubaoService, DoubaoServiceError
except ImportError:
    from llm.chat_model import DoubaoChatModel
    from llm.client import DoubaoService, DoubaoServiceError
try:
    from tools import (
        CalendarTool,
        EmailSenderTool,
        FileParserTool,
        GitHubRepoTool,
        LocalRetrievalTool,
        MeetingSummaryTool,
        TavilyWebTool,
        ToolContext,
        ToolExecutionError,
    )
except ImportError:
    from ..tools import (
        CalendarTool,
        EmailSenderTool,
        FileParserTool,
        GitHubRepoTool,
        LocalRetrievalTool,
        MeetingSummaryTool,
        TavilyWebTool,
        ToolContext,
        ToolExecutionError,
    )
logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration knobs for the agent loop."""
    max_iterations: int = 15
    llm_temperature: float = 0.2
    working_dir: Optional[str] = None
    stop_on_tool_error: bool = False


@dataclass
class AgentStep:
    """Represents a single reasoning step."""
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[Dict[str, Any]] = None
    final_answer: Optional[str] = None
    timestamp: Optional[str] = None  # ISO format timestamp
    context_info: Optional[Dict[str, Any]] = None  # Additional context like current time, etc.


@dataclass
class AgentResult:
    """Aggregate result for an agent run."""
    task: str
    steps: List[AgentStep] = field(default_factory=list)
    final_answer: Optional[str] = None
    error: Optional[str] = None


class Agent:
    """个人AI助手，专注于办公会议等场景，通过工具调用帮助用户完成日常工作任务。"""

    def __init__(
        self,
        *,
        tools: Optional[List[BaseTool]] = None,
        config: Optional[AgentConfig] = None,
        llm_service: Optional[DoubaoService] = None,
    ) -> None:
        self.config = config or AgentConfig()
        self._llm_service = llm_service

        self.tools: List[BaseTool] = tools or self._default_tools()
        self._chat_model = DoubaoChatModel(
            service=self.llm_service,
            temperature=self.config.llm_temperature,
        )
        # Bind tools to model for function calling support
        self._chat_model_with_tools = self._chat_model.bind_tools(self.tools)
        self._tool_names = self._get_tool_names()
        self._tool_descriptions = self._get_tool_descriptions()
        self._system_message = self._build_system_message()

    def _default_tools(self) -> List[BaseTool]:
        working_dir = self.config.working_dir
        return [
            FileParserTool(context=ToolContext(working_dir=working_dir)),
            MeetingSummaryTool(context=ToolContext(working_dir=working_dir)),
            LocalRetrievalTool(context=ToolContext(working_dir=working_dir)),
            TavilyWebTool(context=ToolContext(working_dir=working_dir)),
            GitHubRepoTool(context=ToolContext(working_dir=working_dir)),
            EmailSenderTool(context=ToolContext(working_dir=working_dir)),
            CalendarTool(context=ToolContext(working_dir=working_dir)),
        ]

    def _get_tool_names(self) -> str:
        return ", ".join([tool.name for tool in self.tools])

    def _get_tool_descriptions(self) -> str:
        descriptions = []
        for tool in self.tools:
            descriptions.append(f"- 工具名：{tool.name}\n  功能：{tool.description}")
        return "\n".join(descriptions)

    @property
    def llm_service(self) -> DoubaoService:
        if self._llm_service is None:
            try:
                self._llm_service = DoubaoService()
            except Exception as exc:
                raise RuntimeError(f"Failed to initialize DoubaoService: {exc}") from exc
        return self._llm_service

    def _build_system_message(self) -> SystemMessage:
        prompt = (
            "你是一个个人AI助手，专门帮助用户处理日常工作，特别是会议相关的场景。\n"
            "你是用户的贴心工作伙伴，能够理解用户的需求，主动使用各种工具来完成任务，提供有价值的帮助。\n"
            "\n"
            "## 核心定位\n"
            "\n"
            "作为个人AI助手，你的主要职责包括：\n"
            "- 理解用户的办公和会议需求\n"
            "- 主动使用工具收集信息、处理文件、发送邮件等\n"
            "- 提供清晰、有用的结果和建议\n"
            "- 帮助用户提高工作效率\n"
            "\n"
            "## 主要应用场景\n"
            "\n"
            "### 1. 会议相关\n"
            "- 会议纪要总结和整理\n"
            "- 会议文件解析和提取关键信息\n"
            "- 会议资料检索和准备\n"
            "- 会议邮件发送和通知\n"
            "\n"
            "### 2. 信息收集与处理\n"
            "- 使用网络搜索获取实时信息\n"
            "- 解析和处理各种办公文件（PDF、Word、Excel等）\n"
            "- 从代码仓库中查找相关代码和文档\n"
            "- 从本地知识库中检索历史资料\n"
            "\n"
            "### 3. 日常工作支持\n"
            "- 文件内容提取和分析\n"
            "- 邮件发送和管理\n"
            "- 信息整理和格式化\n"
            "- 快速查找和检索\n"
            "\n"
            "## 工作原则\n"
            "\n"
            "1. **主动理解需求**：\n"
            "   - 仔细理解用户的任务和需求\n"
            "   - 根据上下文判断最合适的处理方式\n"
            "   - 如果信息不足，主动收集相关信息\n"
            "\n"
            "2. **工具调用规范**：\n"
            "   - 必须通过函数调用触发工具，不要自行编造工具名称\n"
            "   - 每次调用工具时，确保提供完整且合法的JSON参数\n"
            "   - 根据任务需求，合理选择和组合使用工具\n"
            "\n"
            "3. **结果输出**：\n"
            "   - 将工具执行结果整理成清晰、结构化的格式\n"
            "   - 使用中文输出，语言自然友好\n"
            "   - 提供有价值的见解和建议，而不仅仅是原始数据\n"
            "   - 针对会议等场景，提供便于理解和使用的总结\n"
            "\n"
            "4. **效率优先**：\n"
            "   - 可以多次调用工具，但要有明确目的\n"
            "   - 当收集到足够信息时，及时停止并给出结果\n"
            "   - 避免不必要的重复操作\n"
            "\n"
            "## 可用工具\n"
            "\n"
            "工具列表：{tool_names}\n"
            "\n"
            "{tools}\n"
            "\n"
            "重要提示：\n"
            "- 你是用户的个人助手，要站在用户的角度思考问题\n"
            "- 主动帮助用户完成工作，提供有价值的输出\n"
            "- 对于会议场景，要特别关注信息的准确性和可读性\n"
            "- 当任务完成时，及时给出清晰的结果，不要过度调用工具\n"
        ).format(
            tool_names=self._tool_names,
            tools=self._tool_descriptions,
        )
        return SystemMessage(content=prompt)

    def run(self, task: str, *, context: Optional[str] = None, conversation_history: Optional[List[Dict[str, str]]] = None) -> AgentResult:
        """
        Run the agent with a task.
        
        Args:
            task: The task description
            context: Optional additional context
            conversation_history: Optional list of previous messages in format [{"role": "user/assistant", "content": "..."}]
        """
        user_input = f"任务：\n{task.strip()}"
        if context:
            user_input += f"\n\n附加上下文信息：\n{context.strip()}"

        result = AgentResult(task=task)

        messages: List[Any] = [self._system_message]
        
        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
        
        # Add current user message
        messages.append(HumanMessage(content=user_input))

        reminder_added = False
        for iteration in range(self.config.max_iterations):
            # 在接近最大迭代次数时提醒 LLM 应该给出最终答案
            remaining_iterations = self.config.max_iterations - iteration
            if remaining_iterations <= 3 and remaining_iterations > 0 and result.steps and not reminder_added:
                reminder = HumanMessage(
                    content=f"注意：你还有 {remaining_iterations} 次迭代机会。如果已经收集到足够信息，请立即停止调用工具并给出最终答案。"
                )
                messages.append(reminder)
                reminder_added = True
            try:
                self._chat_model_with_tools.temperature = self.config.llm_temperature
                ai_message = self._chat_model_with_tools.invoke(messages)
            except DoubaoServiceError as exc:
                result.error = f"豆包LLM服务调用失败：{str(exc)}"
                logger.error(result.error)
                return result
            except Exception as exc:  # noqa: BLE001
                result.error = f"Agent执行失败：{str(exc)}"
                logger.exception(result.error)
                return result

            messages.append(ai_message)

            tool_calls = getattr(ai_message, "tool_calls", None) or []
            if tool_calls:
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name")
                    tool_args = tool_call.get("args", {}) or {}
                    tool_call_id = tool_call.get("id") or ""
                    
                    # Get current time and context info
                    current_time = datetime.now()
                    context_info = {
                        "current_time": current_time.isoformat(),
                        "current_time_readable": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "working_dir": self.config.working_dir,
                    }
                    
                    step = AgentStep(
                        thought=ai_message.content or "模型选择调用工具",
                        action=tool_name,
                        action_input=tool_args if isinstance(tool_args, dict) else {"text": str(tool_args)},
                        timestamp=current_time.isoformat(),
                        context_info=context_info,
                    )

                    tool = self._get_tool_by_name(tool_name)
                    if tool is None:
                        error_message = f"未找到名为 {tool_name} 的工具"
                        step.observation = {"error": error_message}
                        result.steps.append(step)
                        result.error = error_message
                        logger.error(error_message)
                        return result

                    try:
                        observation = tool.invoke(tool_args)
                    except ToolExecutionError as exc:
                        observation_payload = {"error": str(exc)}
                        step.observation = observation_payload
                        result.steps.append(step)
                        logger.error("工具执行失败：%s", exc)
                        if self.config.stop_on_tool_error:
                            result.error = f"工具执行失败：{str(exc)}"
                            return result
                        tool_message_content = json.dumps(observation_payload, ensure_ascii=False)
                        messages.append(ToolMessage(content=tool_message_content, tool_call_id=tool_call_id, name=tool_name))
                        continue
                    except Exception as exc:  # noqa: BLE001
                        observation_payload = {"error": str(exc)}
                        step.observation = observation_payload
                        result.steps.append(step)
                        logger.exception("工具执行异常")
                        if self.config.stop_on_tool_error:
                            result.error = f"工具执行异常：{str(exc)}"
                            return result
                        tool_message_content = json.dumps(observation_payload, ensure_ascii=False)
                        messages.append(ToolMessage(content=tool_message_content, tool_call_id=tool_call_id, name=tool_name))
                        continue

                    observation_payload = self._coerce_observation_payload(observation)
                    step.observation = observation_payload
                    result.steps.append(step)

                    tool_message_content = (
                        json.dumps(observation_payload, ensure_ascii=False)
                        if isinstance(observation_payload, dict)
                        else str(observation_payload)
                    )
                    messages.append(ToolMessage(content=tool_message_content, tool_call_id=tool_call_id, name=tool_name))

                continue

            # 无工具调用，直接输出最终答案
            output_text = (ai_message.content or "").strip()
            if not output_text:
                continue

            result.final_answer = output_text
            if result.steps:
                result.steps[-1].final_answer = result.final_answer
            else:
                result.steps.append(AgentStep(
                    thought="无需调用工具，直接基于任务生成答案",
                    final_answer=result.final_answer,
                ))
            return result

        result.error = "达到最大迭代次数但未获得最终答案"
        logger.error(result.error)
        return result

    def _get_tool_by_name(self, tool_name: Optional[str]) -> Optional[BaseTool]:
        if not tool_name:
            return None
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        return None

    @staticmethod
    def _coerce_observation_payload(observation: Any) -> Any:
        if isinstance(observation, (str, dict)):
            return observation
        if isinstance(observation, list):
            try:
                return json.loads(json.dumps(observation, ensure_ascii=False))
            except Exception:  # noqa: BLE001
                return {"text": str(observation)}
        return {"text": str(observation)}

    @staticmethod
    def _maybe_parse_json(observation: Any) -> Optional[Dict[str, Any]]:
        if isinstance(observation, dict):
            return observation
        if not isinstance(observation, str):
            return {"text": str(observation)}

        clean_obs = observation.strip()
        if clean_obs.startswith("```json") and clean_obs.endswith("```"):
            clean_obs = clean_obs[7:-3].strip()
        try:
            return json.loads(clean_obs)
        except json.JSONDecodeError:
            return {"text": clean_obs}

    @staticmethod
    def _parse_action_input(action_input: Any) -> Optional[Dict[str, Any]]:
        if isinstance(action_input, dict):
            return action_input
        if not isinstance(action_input, str):
            return {"text": str(action_input)}

        clean_input = action_input.strip()
        if clean_input.startswith("```json") and clean_input.endswith("```"):
            clean_input = clean_input[7:-3].strip()
        try:
            return json.loads(clean_input)
        except json.JSONDecodeError:
            return {"text": clean_input}

