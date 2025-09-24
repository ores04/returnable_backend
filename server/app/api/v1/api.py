"""
Main API router that includes all endpoint routers.
"""
from fastapi import APIRouter

from server.app.api.v1.endpoints import health_api, helper, documents_api, email_api, complaint_api


api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health_api.router, prefix="/health", tags=["health"])
api_router.include_router(complaint_api.router, prefix="/complaint", tags=["complaint"])
api_router.include_router(email_api.router, prefix="/email", tags=["email"])
api_router.include_router(helper.router, prefix="/helper", tags=["helper"])
api_router.include_router(documents_api.router, prefix="/document", tags=["document"])

