from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None

class User(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Session schemas
class SessionBase(BaseModel):
    title: str

class SessionCreate(SessionBase):
    pass

class Session(SessionBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    message_count: Optional[int] = 0
    
    class Config:
        from_attributes = True

# Message schemas
class MessageBase(BaseModel):
    role: str
    content: str

class MessageCreate(MessageBase):
    session_id: int

class Message(MessageBase):
    id: int
    session_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Summary schemas
class SummaryBase(BaseModel):
    content: str
    message_count: int

class SummaryCreate(SummaryBase):
    session_id: int

class Summary(SummaryBase):
    id: int
    session_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Execution step schema
class ExecutionStep(BaseModel):
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    context_info: Optional[Dict[str, Any]] = None

# Chat request/response schemas
class ChatRequest(BaseModel):
    session_id: Optional[int] = None
    message: str
    context: Optional[str] = None

class ChatResponse(BaseModel):
    session_id: int
    message: Message
    summary: Optional[Summary] = None
    execution_steps: Optional[List[ExecutionStep]] = None