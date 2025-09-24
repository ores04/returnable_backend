"""
Health check endpoints.
"""
from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter()


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "message": "Service is running",
        "service": "returnable-api"
    }


@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health check endpoint.
    """
    return {
        "status": "healthy",
        "message": "Service is running",
        "service": "returnable-api",
        "version": "1.0.0",
        "environment": "development"
    }
