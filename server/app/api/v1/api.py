"""
Main API router that includes all endpoint routers.
"""
from fastapi import APIRouter

from server.app.api.v1.endpoints import (
    health_api,
    helper,
    documents_api,
    email_api,
    complaint_api,
    whatsapp_api,
    whatsapp_webhook_api,
    verify_purchase_android,
    verify_purchase_ios,
    revenuecat_webhook_api,
    create_todo_api,
)


api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health_api.router, prefix="/health", tags=["health"])
api_router.include_router(complaint_api.router, prefix="/complaint", tags=["complaint"])
api_router.include_router(email_api.router, prefix="/email", tags=["email"])
api_router.include_router(helper.router, prefix="/helper", tags=["helper"])
api_router.include_router(documents_api.router, prefix="/document", tags=["document"])
api_router.include_router(whatsapp_api.router, prefix="/whatsapp", tags=["whatsapp"])
api_router.include_router(whatsapp_webhook_api.router, tags=["whatsapp-webhook"])
api_router.include_router(verify_purchase_android.router, prefix="/purchase/android", tags=["purchase"])
api_router.include_router(verify_purchase_ios.router, prefix="/purchase/ios", tags=["purchase"])
api_router.include_router(revenuecat_webhook_api.router, tags=["revenuecat-webhook"])
api_router.include_router(create_todo_api.router, prefix="/todo", tags=["todo"])
