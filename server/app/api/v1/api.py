"""
Main API router that includes all endpoint routers.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.api.v1.endpoints import complaint

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(
    complaint.router, prefix="/complaint", tags=["complaint"]
)
