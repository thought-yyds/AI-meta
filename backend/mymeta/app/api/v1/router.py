from fastapi import APIRouter
from .health import router as health_router
from .auth_router import router as auth_router
from .sessions import router as sessions_router
from .messages import router as messages_router
from .chat import router as chat_router
from .summaries import router as summaries_router
from .uploads import router as uploads_router

api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, tags=["authentication"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
api_router.include_router(messages_router, prefix="/messages", tags=["messages"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(summaries_router, prefix="/summaries", tags=["summaries"])
api_router.include_router(uploads_router, prefix="/uploads", tags=["uploads"])