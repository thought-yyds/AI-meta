"""Session management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.auth import get_current_active_user
from app.models.models import User, Session as SessionModel
from app.schemas.schemas import Session, SessionCreate
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=Session, status_code=status.HTTP_201_CREATED)
def create_session(
    session: SessionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new chat session."""
    db_session = SessionModel(
        user_id=current_user.id,
        title=session.title
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

@router.get("/", response_model=List[Session])
def get_sessions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all sessions for the current user."""
    sessions = db.query(SessionModel).filter(
        SessionModel.user_id == current_user.id
    ).order_by(SessionModel.updated_at.desc()).all()
    
    # Add message count to each session
    result = []
    for session in sessions:
        session_dict = {
            "id": session.id,
            "user_id": session.user_id,
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "message_count": len(session.messages)
        }
        result.append(Session(**session_dict))
    
    return result

@router.get("/{session_id}", response_model=Session)
def get_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific session."""
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    session_dict = {
        "id": session.id,
        "user_id": session.user_id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "message_count": len(session.messages)
    }
    return Session(**session_dict)

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a session."""
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    db.delete(session)
    db.commit()
    return None

@router.patch("/{session_id}", response_model=Session)
def update_session(
    session_id: int,
    title: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a session's title."""
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    session.title = title
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    
    session_dict = {
        "id": session.id,
        "user_id": session.user_id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "message_count": len(session.messages)
    }
    return Session(**session_dict)

