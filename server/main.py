"""
Main FastAPI application entry point.
"""
import os

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from server.app.api.v1.api import api_router
from server.core.config.general_config import settings

from dotenv import load_dotenv

load_dotenv()

LOGFIRE_TOKEN = os.getenv("LOGFIRE_TOKEN")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logfire.configure(
        token=LOGFIRE_TOKEN,
    )
    logfire.instrument_pydantic_ai()
    logfire.instrument_fastapi(app)
    logfire.info("Starting up FastAPI application...")
    yield
    # Shutdown
    logfire.info("Shutting down FastAPI application...")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan,
    )

    # Set all CORS enabled origins
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin)
                           for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )

    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app


app = create_application()
@app.get("/")
def read_root():
    return {"message": "Welcome to the API. Visit /docs for API documentation."}
