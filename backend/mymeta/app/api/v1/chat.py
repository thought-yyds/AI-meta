"""Chat endpoint for interacting with the AI agent."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from pathlib import Path
from app.core.database import get_db
from app.core.auth import get_current_active_user
from app.models.models import User, Session as SessionModel, Message as MessageModel
from app.schemas.schemas import ChatRequest, ChatResponse, Message, Summary, ExecutionStep
from app.services.agent_service import get_agent_service
from app.services.summary_service import get_summary_service
from app.api.v1.uploads import get_user_uploads_dir

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Send a message to the AI agent and get a response."""
    
    # Get or create session
    if request.session_id:
        session = db.query(SessionModel).filter(
            SessionModel.id == request.session_id,
            SessionModel.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
    else:
        # Create new session with first message as title
        title = request.message[:50] + "..." if len(request.message) > 50 else request.message
        session = SessionModel(
            user_id=current_user.id,
            title=title
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    
    # Save user message
    user_message = MessageModel(
        session_id=session.id,
        role="user",
        content=request.message
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)
    
    # Get conversation history for context
    previous_messages = db.query(MessageModel).filter(
        MessageModel.session_id == session.id
    ).order_by(MessageModel.created_at.asc()).all()
    
    # Get the latest summary if exists (to compress old history)
    from app.models.models import Summary as SummaryModel
    latest_summary = db.query(SummaryModel).filter(
        SummaryModel.session_id == session.id
    ).order_by(SummaryModel.created_at.desc()).first()
    
    # Format conversation history for agent
    # Strategy: Use summary for old messages, keep recent messages (last 5 exchanges = 10 messages)
    conversation_history = []
    
    if latest_summary:
        conversation_history.append({
            "role": "system",
            "content": f"之前的对话总结：{latest_summary.content}"
        })
        summary_cutoff = latest_summary.created_at
        if summary_cutoff:
            filtered_messages = [
                msg for msg in previous_messages
                if msg.created_at and msg.created_at > summary_cutoff
            ]
        else:
            filtered_messages = previous_messages
        recent_messages = filtered_messages[-10:]
    else:
        recent_messages = previous_messages[-10:]
    
    # Add recent messages
    for msg in recent_messages:
        conversation_history.append({
            "role": msg.role,
            "content": msg.content
        })
    
    # Set working directory to user's uploads directory
    # This allows file_parser tool to find uploaded files
    # Use the same path calculation as uploads.py
    user_uploads_dir = get_user_uploads_dir(current_user.id)
    working_dir = str(user_uploads_dir) if user_uploads_dir.exists() else None
    
    # Log for debugging
    if working_dir:
        logger.info(f"Using working directory for user {current_user.id}: {working_dir}")
    
    # Process message with agent
    try:
        agent_service = get_agent_service()
        agent_result = agent_service.process_message(
            message=request.message,
            context=request.context,
            conversation_history=conversation_history,
            working_dir=working_dir
        )
        assistant_response = agent_result["response"]
        execution_steps = agent_result.get("steps", [])
    except RuntimeError as e:
        # Handle initialization errors gracefully
        error_msg = str(e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_msg
        )
    
    # Save assistant message
    assistant_message = MessageModel(
        session_id=session.id,
        role="assistant",
        content=assistant_response
    )
    db.add(assistant_message)
    
    # Update session timestamp
    session.updated_at = datetime.utcnow()
    
    # Generate summary if there are enough messages (e.g., every 10 messages)
    summary = None
    message_count = len(previous_messages) + 2  # +2 for the new user and assistant messages
    if message_count > 0 and message_count % 10 == 0:
        summary_service = get_summary_service()
        all_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in previous_messages + [user_message, assistant_message]
        ]
        summary_content = summary_service.generate_summary(all_messages)
        
        # Save summary
        from app.models.models import Summary as SummaryModel
        summary_model = SummaryModel(
            session_id=session.id,
            content=summary_content,
            message_count=message_count
        )
        db.add(summary_model)
        db.commit()
        db.refresh(summary_model)
        
        summary = Summary(
            id=summary_model.id,
            session_id=summary_model.session_id,
            content=summary_model.content,
            message_count=summary_model.message_count,
            created_at=summary_model.created_at
        )
    else:
        db.commit()
    
    db.refresh(assistant_message)
    
    # Format execution steps for response
    formatted_steps = None
    if execution_steps:
        formatted_steps = [
            ExecutionStep(
                thought=step.get("thought", ""),
                action=step.get("action"),
                action_input=step.get("action_input"),
                observation=step.get("observation"),
                timestamp=step.get("timestamp"),
                context_info=step.get("context_info"),
            )
            for step in execution_steps
        ]
    
    return ChatResponse(
        session_id=session.id,
        message=Message(
            id=assistant_message.id,
            session_id=assistant_message.session_id,
            role=assistant_message.role,
            content=assistant_message.content,
            created_at=assistant_message.created_at
        ),
        summary=summary,
        execution_steps=formatted_steps
    )

