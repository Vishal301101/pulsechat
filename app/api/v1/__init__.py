from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.workspace import router as workspace_router
from app.api.v1.channels import router as channel_router
from app.api.v1.messages import router as message_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(workspace_router)
api_router.include_router(channel_router)
api_router.include_router(message_router)
