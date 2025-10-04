from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from supabase_auth import AuthResponse
import datetime

from server.core.service.supabase_connectors.supabase_client import get_supabase_client, \
    get_auth_client_from_username_password
from server.core.service.whatsapp_service.whatsapp_reminder_service import remind_users

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter()

last_reminder_pulse = None

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

@router.get("/reminder/pulse")
def pluse_reminder(background_tasks: BackgroundTasks):
    """This is an endpoint that will be periodically called to check if a new reminder needs to be sent."""
    global last_reminder_pulse
    current_time = datetime.datetime.now()
    # todo add logic to avaoid getting ddosed
    if last_reminder_pulse is None:
        last_reminder_pulse = current_time - datetime.timedelta(minutes=1)  # Assume the last pulse was 15 minutes ago
    background_tasks.add_task(remind_users, last_reminder_pulse, current_time)
    last_reminder_pulse = current_time

    return {
        "status": "success",
        "message": "Remember to take your pluse!"
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
