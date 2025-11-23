"""Service for integrating Agent with the chat system."""

import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Add src directory to path to import Agent
# File is at: backend/mymeta/app/services/agent_service.py
# Need to go up 4 levels to reach project root: AI-meta/
project_root = Path(__file__).resolve().parents[4]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Also add project root to path for alternative import style
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    # Try importing from src directory (when src is in path)
    from agents.Agent import Agent, AgentConfig
    from llm import DoubaoService
except ImportError:
    # Fallback: import from project root (when project root is in path)
    try:
        from src.agents.Agent import Agent, AgentConfig
        from src.llm import DoubaoService
    except ImportError as e:
        logger.error(f"Failed to import Agent or DoubaoService. Project root: {project_root}, src_path: {src_path}, sys.path: {sys.path[:3]}")
        raise ImportError(f"Could not import Agent or DoubaoService: {e}") from e

class AgentService:
    """Service for managing Agent instances and processing chat messages."""
    
    def __init__(self):
        """Initialize the Agent service with LLM."""
        self.llm_service = None
        self._initialization_error = None
        self._try_initialize()
    
    def _try_initialize(self):
        """Try to initialize the LLM service, storing any errors."""
        try:
            self.llm_service = DoubaoService()
            logger.info("Initialized DoubaoService for Agent")
        except ValueError as e:
            # Missing environment variables
            error_msg = str(e)
            if "ARK_API_KEY" in error_msg:
                self._initialization_error = "ARK_API_KEY environment variable is not set. Please configure it in your .env file."
            elif "ARK_MODEL_NAME" in error_msg:
                self._initialization_error = "ARK_MODEL_NAME environment variable is not set. Please configure it in your .env file."
            else:
                self._initialization_error = f"Configuration error: {error_msg}"
            logger.error(f"Failed to initialize DoubaoService: {self._initialization_error}")
        except Exception as e:
            self._initialization_error = f"Failed to initialize LLM service: {str(e)}"
            logger.error(f"Failed to initialize DoubaoService: {e}")
    
    def get_agent(self, config: Optional[AgentConfig] = None, working_dir: Optional[str] = None) -> Agent:
        """Get an Agent instance with the given config."""
        if self._initialization_error:
            raise RuntimeError(self._initialization_error)
        
        if config is None:
            # Set working_dir to uploads directory if provided
            config = AgentConfig(
                max_iterations=15,
                llm_temperature=0.2,
                working_dir=working_dir,
            )
        elif working_dir is not None:
            # Override working_dir if provided
            config.working_dir = working_dir
        
        return Agent(config=config, llm_service=self.llm_service)
    
    def process_message(
        self,
        message: str,
        context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        working_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a user message and return the assistant's response with execution steps.
        
        Args:
            message: The user's message
            context: Optional additional context
            conversation_history: Optional list of previous messages in format [{"role": "user/assistant", "content": "..."}]
            working_dir: Optional working directory for tools (e.g., user's uploads directory)
        
        Returns:
            Dict with 'response' (str) and 'steps' (list of execution steps)
        """
        # Check if initialization failed
        if self._initialization_error:
            error_msg = f"⚠️ 服务配置错误：{self._initialization_error}\n\n请检查后端环境变量配置，确保设置了 ARK_API_KEY 和 ARK_MODEL_NAME。"
            return {
                "response": error_msg,
                "steps": []
            }
        
        try:
            agent = self.get_agent(working_dir=working_dir)
            
            # Use the agent's run method with conversation history support
            # The agent will use all available tools (FileParserTool, MeetingSummaryTool, etc.)
            # and can access files in the working_dir
            result = agent.run(
                task=message,
                context=context,
                conversation_history=conversation_history
            )
            
            if result.error:
                logger.error(f"Agent error: {result.error}")
                error_msg = f"⚠️ 处理过程中遇到错误：{result.error}"
                return {
                    "response": error_msg,
                    "steps": self._format_steps(result.steps)
                }
            
            # Format steps for frontend
            formatted_steps = self._format_steps(result.steps)
            
            return {
                "response": result.final_answer or "抱歉，我无法生成回复。",
                "steps": formatted_steps
            }
            
        except RuntimeError as e:
            # Re-raise initialization errors
            raise
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            error_msg = f"抱歉，处理您的消息时遇到错误：{str(e)}"
            return {
                "response": error_msg,
                "steps": []
            }
    
    def _format_steps(self, steps: List[Any]) -> List[Dict[str, Any]]:
        """Format agent steps for frontend display."""
        formatted = []
        for step in steps:
            # Handle observation: convert string to dict if needed
            observation = step.observation
            if observation is None:
                observation = {}
            elif isinstance(observation, str):
                # Try to parse JSON string
                try:
                    observation = json.loads(observation)
                except (json.JSONDecodeError, TypeError):
                    # If not valid JSON, wrap in dict
                    observation = {"text": observation}
            elif not isinstance(observation, dict):
                # Convert other types to dict
                observation = {"text": str(observation)}
            
            # Handle action_input: ensure it's a dict
            action_input = step.action_input
            if action_input is None:
                action_input = {}
            elif isinstance(action_input, str):
                # Try to parse JSON string
                try:
                    action_input = json.loads(action_input)
                except (json.JSONDecodeError, TypeError):
                    # If not valid JSON, wrap in dict
                    action_input = {"input": action_input}
            elif not isinstance(action_input, dict):
                # Convert other types to dict
                action_input = {"input": str(action_input)}
            
            formatted_step = {
                "thought": step.thought or "",
                "action": step.action or "",
                "action_input": action_input,
                "observation": observation,
                "timestamp": getattr(step, "timestamp", None),
                "context_info": getattr(step, "context_info", None),
            }
            formatted.append(formatted_step)
        return formatted

# Global instance
_agent_service: Optional[AgentService] = None

def get_agent_service() -> AgentService:
    """Get the global AgentService instance."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service

