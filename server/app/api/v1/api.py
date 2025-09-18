"""
Main API router that includes all endpoint routers.
"""
from fastapi import APIRouter

from server.app.api.v1.endpoints import health, helper, documents, email, complaint


api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(complaint.router, prefix="/complaint", tags=["complaint"])
api_router.include_router(email.router, prefix="/email", tags=["email"])
api_router.include_router(helper.router, prefix="/helper", tags=["helper"])
api_router.include_router(documents.router, prefix="/document", tags=["document"])

