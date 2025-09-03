from dotenv import load_dotenv
import os

from pydantic import BaseModel
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from supabase_auth import SignInWithPasswordCredentials, SignInWithEmailAndPasswordCredentials, AuthResponse

from server.core.agents.email_reply_service import TodoItem, InputItem

load_dotenv()

TOKEN_TABLE_NAME = "REFRESH_TOKEN"
RETURNABLE_REQUEST_TABLE_NAME = "RETURN_REQUEST"
ACTION_TABLE_NAME = "ACTION_STEPS"
RETURN_TASKS_TABLE_NAME = "RETURN_TASKS"
RETURN_MAILS_TABLE_NAME = "RETURN_MAILS"

url: str = os.environ.get("SUPABASE_URL", None)
key: str = os.environ.get("SUPABASE_KEY", None)

assert url is not None, "SUPABASE_URL environment variable is not set"
assert key is not None, "SUPABASE_KEY environment variable is not set"

class ReturnableRequest(BaseModel):
    """Pydantic model for a returnable request."""
    user_id: str
    reclamation_reason: str
    product_from_company: str
    customer_id: str
    invoice_id: str
    invoice_date: str


def get_supabase_client(acsess_token:str) -> Client:
    return create_client(supabase_url=url, supabase_key=key, options=SyncClientOptions(
        headers={
            "Authorization": f"Bearer {acsess_token}"
        }
    ))

def get_supabase_service_role_client() -> Client:
    """This function returns a supabase client with the service role key. Use only if absolutely necessary."""
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", None)
    if key is None:
        raise Exception("Supabase service role key is not set")
    return create_client(supabase_url=url, supabase_key=key)


def get_auth_client_from_username_password(username: str, password: str) -> AuthResponse:
    client = create_client(supabase_url=url, supabase_key=key)
    credentials = SignInWithEmailAndPasswordCredentials(email=username, password=password)
    auth_response = client.auth.sign_in_with_password(credentials)
    if not auth_response and not auth_response.user:
        raise ValueError(f"Authentication failed for user {username}")
    return auth_response


def add_returnable_request_to_db(jwt_token: str, request_data: dict):
    """This function adds a new returnable request to the database."""
    # assert that all required fields are present
    required_fields = ["user_id", "reclamation_reason", "product_from_company", "customer_id", "invoice_id", "invoice_date"]

    for field in required_fields:
        if field not in request_data:
            raise ValueError(f"Missing required field: {field}")

    supabase_client = get_supabase_client(acsess_token=jwt_token)

    # set the user id from the token to ensure the user cannot create requests for other users
    user = supabase_client.auth.get_user(jwt_token).user
    request_data["user_id"] = user.id

    # remove id so that is set automatically by supabase
    if "id" in request_data:
        del request_data["id"]

    # assert that the user is authenticated##
    response = supabase_client.table(RETURNABLE_REQUEST_TABLE_NAME).insert(request_data).execute()

    response.raise_when_api_error(response)


    # we also add the action request send to the action table
    action = {
        "title": "Mail Gesendet",
        "summary": f"Rücksendeanfrage erstellt",
        "details": f"Wir haben eine Rücksendeanfrage erstellt und dem Kundenservice weitergeleitet.",
        "user_id": request_data["user_id"],
        "returnable_id": response.data[0]["id"],
        "type": "returnable_request",
        "order_id": None
    }



    return response.data, action

def add_action_to_db(jwt_token: str, action_data: dict):
    """This function adds a new action to the database."""
    # assert that all required fields are present
    required_fields = ["title", "summary", "details", "user_id", "returnable_id", "type", "order_id"]

    for field in required_fields:
        if field not in action_data:
            raise ValueError(f"Missing required field: {field}")

    supabase_client = get_supabase_client(acsess_token=jwt_token)

    response = supabase_client.table(ACTION_TABLE_NAME).insert(action_data).execute()

    response.raise_when_api_error(response)

    return response.data

def get_all_active_returnable_requests(service_client: Client):
    """This function returns all active returnable requests from the database."""
    response = service_client.table(RETURNABLE_REQUEST_TABLE_NAME).select("*").eq("active", "true").execute()
    response.raise_when_api_error(response)
    return response.data

def get_latest_mail_with_returnable_id(service_client: Client, returnable_id: str) -> dict:
    """This function returns all mails with the given returnable id from the database."""
    response = service_client.table(RETURN_MAILS_TABLE_NAME).select("*").eq("return_request_id", returnable_id).order(
        "created_at", desc=True
    ).limit(1).execute()
    response.raise_when_api_error(response)
    return response.data[0] if response.data and len(response.data) > 0 else {}

def add_task_to_db(service_client: Client, task: TodoItem| InputItem, returnable_id: str):
    """This function adds a new task to the database."""
    task_data = {
        "type": task.requested_type,
        "return_request_id": returnable_id,
        "text": task.text,
    }

    response = service_client.table(RETURN_TASKS_TABLE_NAME).insert(task_data).execute()
    response.raise_when_api_error(response)

    return response.data

def add_mail_to_db(jwt_token: str | None, service_client: Client | None, mail_data: dict, returnable_id: str, send_by_me: bool = False):
    """This function adds a new mail to the database."""
    assert jwt_token or service_client, "Either jwt_token or service_client must be set"
    if jwt_token:
        service_client = get_supabase_client(acsess_token=jwt_token)
    mail_data = {
        "return_request_id": returnable_id,
        "to" : mail_data.get("sender"), # this is in fact the mail exchange partner
        "send_by_me": send_by_me,
        "body": mail_data.get("body"),
        "subject": mail_data.get("subject"),
    }

    response = service_client.table(RETURN_MAILS_TABLE_NAME).insert(mail_data).execute()
    response.raise_when_api_error(response)

    return response.data

