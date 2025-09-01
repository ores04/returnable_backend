import supabase
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from supabase_auth import AuthResponse
from supabase_auth.http_clients import SyncClient

from server.core.email_service.supabase_client import get_auth_client_from_username_password, get_supabase_client

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter()


class JWTRequestBody(BaseModel):
    username: str
    password: str

@router.post("/get_jwt_token")
def get_jwt_token_from_supabase(request: JWTRequestBody):
    """ This is a debug endwoint that signs a user in and returns the JWT token."""

    username = request.username
    password = request.password

    if not username or not password:
        return {
            "status": "error",
            "message": "Username and password are required"
        }

    client: AuthResponse = get_auth_client_from_username_password(username, password)

    token = client.session.access_token
    if not token:
        return {
            "status": "error",
            "message": "Authentication failed"
        }

    return {
        "status": "success",
        "jwt_token": token
    }

@router.get("/test_supabase_connection")
def test_supabase_connection(token: str = Depends(oauth2_scheme)):
    """ This is a debug endpoint that tests the connection to Supabase."""
    client = get_supabase_client()
    if client.auth.get_user(token) is None:
        return {
            "status": "error",
            "message": "Invalid token or unable to connect to Supabase"
        }
    return {
        "status": "success",
        "message": "Successfully connected to Supabase"
    }
