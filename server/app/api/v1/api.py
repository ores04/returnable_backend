"""
Main API router that includes all endpoint routers.
"""
from fastapi import APIRouter

from server.app.api.v1.endpoints import (
    health_api,
    helper,
    whatsapp_api,
    whatsapp_webhook_api,
    verify_purchase_android,
    verify_purchase_ios,
    revenuecat_webhook_api,
    create_todo_api,
    # New reminder/tag/task endpoints
    reminders_api,
    tags_api,
    tag_connections_api,
    tag_sharing_api,
    tag_filters_api,
    tasks_api,
)


api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health_api.router, prefix="/health", tags=["health"])
api_router.include_router(helper.router, prefix="/helper", tags=["helper"])
api_router.include_router(whatsapp_api.router, prefix="/whatsapp", tags=["whatsapp"])
api_router.include_router(whatsapp_webhook_api.router, tags=["whatsapp-webhook"])
api_router.include_router(verify_purchase_android.router, prefix="/purchase/android", tags=["purchase"])
api_router.include_router(verify_purchase_ios.router, prefix="/purchase/ios", tags=["purchase"])
api_router.include_router(revenuecat_webhook_api.router, tags=["revenuecat-webhook"])
api_router.include_router(create_todo_api.router, prefix="/todo", tags=["todo"])

# Reminder, Tag, and Task endpoints
api_router.include_router(reminders_api.router, prefix="/reminders", tags=["reminders"])
api_router.include_router(tags_api.router, prefix="/tags", tags=["tags"])
api_router.include_router(tag_connections_api.router, prefix="/tag-connections", tags=["tag-connections"])
api_router.include_router(tag_sharing_api.router, prefix="/tag-sharing", tags=["tag-sharing"])
api_router.include_router(tag_filters_api.router, prefix="/tag-filters", tags=["tag-filters"])
api_router.include_router(tasks_api.router, prefix="/tasks", tags=["tasks"])
