"""个人AI助手Agent，专注于个人效率与知识管理，通过工具调用完成日常任务。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
import re
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
    from tools import LocalMCPTool, ToolContext, ToolExecutionError
except ImportError:
    from ..tools import LocalMCPTool, ToolContext, ToolExecutionError
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
    """个人AI助手，聚焦个人效率、信息整理与知识管理等日常任务。"""

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
        self._mcp_subtools = self._get_mcp_subtools()
        self._system_message = self._build_system_message()

    def _default_tools(self) -> List[BaseTool]:
        working_dir = self.config.working_dir
        return [
            LocalMCPTool(context=ToolContext(working_dir=working_dir)),
        ]

    def _get_tool_names(self) -> str:
        return ", ".join([tool.name for tool in self.tools])

    def _get_tool_descriptions(self) -> str:
        descriptions = []
        for tool in self.tools:
            descriptions.append(f"- 工具名：{tool.name}\n  功能：{tool.description}")
        return "\n".join(descriptions)

    def _get_mcp_subtools(self) -> List[Dict[str, str]]:
        subtools: List[Dict[str, str]] = []
        for tool in self.tools:
            if hasattr(tool, "list_available_tools"):
                try:
                    subtools.extend(tool.list_available_tools())
                except Exception:  # noqa: BLE001
                    logger.debug("Failed to list MCP sub-tools from %s", tool.name, exc_info=True)
        return subtools

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
            "你是一个个人AI助手，帮助用户完成个人项目、资料整理、在线调研与沟通协作任务。\n"
            "要主动思考、善用工具，并输出结构化、可执行的结果。\n"
            "\n"
            "## 核心定位\n"
            "\n"
            "作为个人助手，你的主要职责包括：\n"
            "- 理解用户的真实需求、时间安排和完成标准\n"
            "- 熟练使用文件解析、本地检索、网络搜索、GitHub、邮件与日历等工具\n"
            "- 结合工具结果给出结论、分析和后续建议，帮助用户提升效率\n"
            "\n"
            "## 主要应用场景\n"
            "\n"
            "### 1. 信息整理与知识管理\n"
            "- 解析本地文档、提炼摘要或结构化要点\n"
            "- 在个人知识库中检索历史内容\n"
            "- 将零散信息整理成计划、行动列表或表格\n"
            "\n"
            "### 2. 调研与学习支持\n"
            "- 使用 Tavily 进行实时搜索，整合多来源信息\n"
            "- 浏览 GitHub 仓库，定位代码示例或项目状态\n"
            "- 总结学习材料、比较方案并提出建议\n"
            "\n"
            "### 3. 个人效率与沟通\n"
            "- 起草并发送邮件、日常更新或通知\n"
            "- 生成日历事件，帮助安排个人行程\n"
            "- 根据上下文提供下一步行动建议\n"
            "\n"
            "## 工作原则\n"
            "\n"
            "1. **主动理解需求**：\n"
            "   - 澄清目标、输入和输出格式\n"
            "   - 信息不足时说明缺口或建议补充方式\n"
            "\n"
            "2. **工具调用规范**：\n"
            "   - 仅调用提供的工具，且使用合法 JSON 参数\n"
            "   - 调用前说明目的，调用后结合结果继续推理\n"
            "\n"
            "3. **结果输出**：\n"
            "   - 结构化输出，突出结论、依据和下一步\n"
            "   - 使用中文，语言自然友好，可附带表格/列表\n"
            "\n"
            "4. **效率优先**：\n"
            "   - 工具调用应有明确目的，避免重复操作\n"
            "   - 收集到足够信息后及时给出答案\n"
            "\n"
            "5. **任务独立性**：\n"
            "   - 对话历史仅用于理解背景，当前回复只解决最新任务\n"
            "   - 不要重复执行旧任务，除非用户明确要求复用\n"
            "\n"
            "## 可用工具\n"
            "\n"
            "工具列表：{tool_names}\n"
            "\n"
            "{tools}\n"
            "\n"
            "{mcp_tools_section}"
            "重要提示：\n"
            "- 站在用户视角，给出真正可执行的建议\n"
            "- 如果需要额外信息，先解释缺口再提问\n"
            "- 任务完成后总结重点和后续建议\n"
        ).format(
            tool_names=self._tool_names,
            tools=self._tool_descriptions,
            mcp_tools_section=self._render_mcp_section(),
        )
        return SystemMessage(content=prompt)

    def _render_mcp_section(self) -> str:
        if not self._mcp_subtools:
            return ""
        lines = []
        for tool in self._mcp_subtools:
            description = tool.get("description") or ""
            lines.append(f"- {tool.get('name')}: {description}")
        return "### MCP 子工具\n" + "\n".join(lines) + "\n\n"

    def run(self, task: str, *, context: Optional[str] = None, conversation_history: Optional[List[Dict[str, str]]] = None) -> AgentResult:
        """
        Run the agent with a task.
        
        Args:
            task: The task description
            context: Optional additional context
            conversation_history: Optional list of previous messages in format [{"role": "user/assistant", "content": "..."}]
        """
        # 检查是否是模型/身份相关的独立问题
        if self._is_model_identity_query(task):
            result = AgentResult(task=task)
            cleaned_question = task.strip()
            result.final_answer = (
                f"您好，我是default的AI模型，是Cursor IDE内置的AI助手，致力于提升您的开发效率。你问的是：\"{cleaned_question}\""
            )
            result.steps.append(AgentStep(
                thought="检测到模型或身份相关的独立问题，返回固定介绍。",
                final_answer=result.final_answer,
            ))
            return result
        
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
                # Handle system messages (e.g., summaries)
                if role == "system":
                    messages.append(SystemMessage(content=content))
                elif role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
        
        # Add current user message with explicit instruction to avoid repeating past actions
        current_task_prompt = (
            f"{user_input}\n\n"
            "重要提示：请只处理上述当前任务，不要重复执行对话历史中已经完成的操作。"
        )
        messages.append(HumanMessage(content=current_task_prompt))

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
                # 如果模型返回空内容，记录并尝试继续，但如果连续多次空回复，则给出默认回复
                empty_count = sum(1 for step in result.steps if step.thought and "模型返回空内容" in step.thought)
                if empty_count >= 2:
                    # 连续多次空回复，给出默认回复
                    result.final_answer = "抱歉，我暂时无法生成回复。请尝试重新表述您的问题，或检查网络连接。"
                    result.steps.append(AgentStep(
                        thought="模型连续返回空内容，给出默认回复",
                        final_answer=result.final_answer,
                    ))
                    logger.warning("模型连续返回空内容，已给出默认回复")
                    return result
                else:
                    # 记录空回复但继续尝试
                    result.steps.append(AgentStep(
                        thought="模型返回空内容，继续尝试",
                    ))
                    logger.warning(f"模型返回空内容（第{empty_count + 1}次），继续尝试")
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

        # 达到最大迭代次数
        if result.steps:
            # 如果有步骤但无最终答案，尝试使用最后一步的观察结果
            last_step = result.steps[-1]
            if last_step.observation:
                result.final_answer = f"已完成相关操作，但未获得明确的文本回复。最后一步的结果：{json.dumps(last_step.observation, ensure_ascii=False)}"
            else:
                result.final_answer = "已达到最大迭代次数，但未获得最终答案。请尝试重新表述您的问题。"
        else:
            result.final_answer = "已达到最大迭代次数，但未获得最终答案。请尝试重新表述您的问题。"
        
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

    @staticmethod
    def _is_model_identity_query(task: str) -> bool:
        """Return True only when the entire输入是询问模型或身份的独立问题。"""
        if not task:
            return False

        text = task.strip()
        if not text:
            return False

        # Remove common greetings or polite prefixes
        text = re.sub(r"^(?:你好|您好|在吗|hi|hello|hey)[,，\s]*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^(?:请问|想了解一下)[,，\s]*", "", text, flags=re.IGNORECASE)

        # Normalize whitespace and trailing punctuation
        text = re.sub(r"[\r\n]+", " ", text)
        text = re.sub(r"[？?。.!]+$", "", text).strip()
        if not text:
            return False

        # If the text still contains conjunctions/commas, treat it as part of a longer任务
        if any(sep in text for sep in ["；", ";", "\n"]):
            return False

        compact = re.sub(r"[，,：:\s]", "", text).lower()
        if not compact:
            return False

        chinese_exact = {
            "你是谁", "你是谁呀", "你是谁呢",
            "你是哪个模型", "你是什么模型", "你是什么ai", "你是什么",
            "您是谁", "您是什么模型", "请介绍你自己",
        }
        english_exact = {
            "whoareyou", "whatareyou", "whatmodelareyou",
            "whatmodeldoyouuse", "whatareyoumodel", "whatai", "whatareyouai",
            "whichmodelareyou",
        }

        if compact in chinese_exact or compact in english_exact:
            return True

        english_text = text.lower()
        english_patterns = [
            r"^who are you\??$",
            r"^what model (?:are you|do you use)\??$",
            r"^what ai (?:are you)?\??$",
            r"^which model (?:are you|do you use)\??$",
        ]
        for pattern in english_patterns:
            if re.fullmatch(pattern, english_text):
                return True

        return False

