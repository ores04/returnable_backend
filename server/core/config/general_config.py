"""
Application configuration settings.
"""
import json
from typing import List, Union  # kept for compatibility if referenced elsewhere
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings."""

    # Pydantic v2 settings configuration
    model_config = SettingsConfigDict(
        env_file=".env.server", case_sensitive=True)

    PROJECT_NAME: str = "Effortless Server"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "backend server for Effortless app"

    API_V1_STR: str = "/api/v1"

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # CORS settings (accept both comma-separated string and JSON list from env)
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8000",
        # we need to allow users to access the API from their own origins
        "https://test-461641401152.europe-west1.run.app",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed]
                except Exception:
                    # fall back to comma-splitting if JSON fails
                    pass
            return [part.strip() for part in s.split(",") if part.strip()]
        if isinstance(v, (list, tuple, set)):
            return [str(x).strip() for x in v]
        raise TypeError("BACKEND_CORS_ORIGINS must be a list or a string")


settings = Settings()
