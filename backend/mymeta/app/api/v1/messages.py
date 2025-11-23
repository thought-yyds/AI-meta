"""Message management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.auth import get_current_active_user
from app.models.models import User, Session as SessionModel, Message as MessageModel
from app.schemas.schemas import Message, MessageCreate

router = APIRouter()

@router.get("/session/{session_id}", response_model=List[Message])
def get_messages(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all messages for a session."""
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
    
    messages = db.query(MessageModel).filter(
        MessageModel.session_id == session_id
    ).order_by(MessageModel.created_at.asc()).all()
    
    return messages

@router.get("/{message_id}", response_model=Message)
def get_message(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific message."""
    message = db.query(MessageModel).filter(
        MessageModel.id == message_id
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Verify session belongs to user
    session = db.query(SessionModel).filter(
        SessionModel.id == message.session_id,
        SessionModel.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return message

