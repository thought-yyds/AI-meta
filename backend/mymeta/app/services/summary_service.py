"""Service for generating conversation summaries."""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

# Add src directory to path
project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    from llm import DoubaoService
except ImportError:
    try:
        from src.llm import DoubaoService
    except ImportError:
        raise ImportError("Could not import DoubaoService")

logger = logging.getLogger(__name__)

class SummaryService:
    """Service for generating conversation summaries."""
    
    def __init__(self):
        """Initialize the summary service with LLM."""
        try:
            self.llm_service = DoubaoService()
            logger.info("Initialized DoubaoService for Summary")
        except Exception as e:
            logger.error(f"Failed to initialize DoubaoService: {e}")
            raise
    
    def generate_summary(
        self,
        messages: List[Dict[str, str]],
        max_length: int = 500
    ) -> str:
        """
        Generate a summary of the conversation.
        
        Args:
            messages: List of messages in format [{"role": "user/assistant", "content": "..."}]
            max_length: Maximum length of the summary
        
        Returns:
            A summary of the conversation
        """
        if not messages:
            return "No messages to summarize."
        
        try:
            # Format conversation for summary
            conversation_text = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in messages
            ])
            
            # Create a prompt for summarization
            prompt = f"""请总结以下对话的主要内容，用中文回答，控制在{max_length}字以内：

{conversation_text}

总结："""
            
            # Use the LLM service to generate summary
            response = self.llm_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            summary = response.get("message", "无法生成总结")
            
            # Truncate if too long
            if len(summary) > max_length:
                summary = summary[:max_length] + "..."
            
            return summary
            
        except Exception as e:
            logger.exception(f"Error generating summary: {e}")
            return f"生成总结时出错: {str(e)}"

# Global instance
_summary_service: Optional[SummaryService] = None

def get_summary_service() -> SummaryService:
    """Get the global SummaryService instance."""
    global _summary_service
    if _summary_service is None:
        _summary_service = SummaryService()
    return _summary_service

