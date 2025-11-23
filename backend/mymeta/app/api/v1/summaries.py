"""Summary management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.auth import get_current_active_user
from app.models.models import User, Session as SessionModel, Summary as SummaryModel
from app.schemas.schemas import Summary
from app.services.summary_service import get_summary_service

router = APIRouter()

@router.get("/session/{session_id}", response_model=List[Summary])
def get_summaries(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all summaries for a session."""
    # Verify session belongs to user
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    summaries = db.query(SummaryModel).filter(
        SummaryModel.session_id == session_id
    ).order_by(SummaryModel.created_at.desc()).all()
    
    return summaries

@router.post("/session/{session_id}/generate", response_model=Summary)
def generate_summary(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Manually generate a summary for a session."""
    # Verify session belongs to user
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Get all messages
    from app.models.models import Message as MessageModel
    messages = db.query(MessageModel).filter(
        MessageModel.session_id == session_id
    ).order_by(MessageModel.created_at.asc()).all()
    
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No messages to summarize"
        )
    
    # Format messages for summary service
    message_list = [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]
    
    # Generate summary
    summary_service = get_summary_service()
    summary_content = summary_service.generate_summary(message_list)
    
    # Save summary
    summary_model = SummaryModel(
        session_id=session_id,
        content=summary_content,
        message_count=len(messages)
    )
    db.add(summary_model)
    db.commit()
    db.refresh(summary_model)
    
    return Summary(
        id=summary_model.id,
        session_id=summary_model.session_id,
        content=summary_model.content,
        message_count=summary_model.message_count,
        created_at=summary_model.created_at
    )

