import logfire
from dotenv import load_dotenv
import os

from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from supabase_auth import SignInWithEmailAndPasswordCredentials, AuthResponse

load_dotenv()

USER_META_INFORMATION_TABLE_NAME = "USER_META_INFORMATION"
TOKEN_TABLE_NAME = "REFRESH_TOKEN"

url: str = os.environ.get("SUPABASE_URL", None)
key: str = os.environ.get("SUPABASE_KEY", None)

assert url is not None, "SUPABASE_URL environment variable is not set"
assert key is not None, "SUPABASE_KEY environment variable is not set"


def get_supabase_client(jwt_token: str) -> Client:
    return create_client(supabase_url=url, supabase_key=key, options=SyncClientOptions(
        headers={
            "Authorization": f"Bearer {jwt_token}"
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


def get_uuid_from_phone_number(phone_number: str) -> str:
    """This function gets the uuid from a user based on a phone numner. The phonenumber is expected to be +()..."""
    # clean the phone number
    phone_number = phone_number.replace(" ", "").replace("-", "").replace("+", "")
    service_level_client = get_supabase_service_role_client()
    logfire.info(f"Getting uuid for phone number {phone_number}")
    data = service_level_client.from_(USER_META_INFORMATION_TABLE_NAME).select("uuid").eq("phone_number", phone_number).execute().data
    if not data or len(data) == 0:
        raise ValueError(f"No user found for phone number {phone_number}")

    uuid = data[0]["uuid"]
    return uuid

def is_premium_user_from_uuid(uuid: str) -> bool:
    """This function checks if a user is a premium user based on their uuid."""
    return True ## temporary bypass
    service_level_client = get_supabase_service_role_client()
    logfire.debug(f"Checking if user {uuid} is a premium user")
    data = service_level_client.from_(USER_META_INFORMATION_TABLE_NAME).select("user_status").eq("uuid", uuid).execute().data
    if not data or len(data) == 0:
        raise ValueError(f"No user found for uuid {uuid}")
    is_premium = data[0]["user_status"] == "premium"
    return is_premium

def get_phone_number_from_uuid(uuid: str) -> str:
    """This function gets the phone number from a user based on a uuid."""
    service_level_client = get_supabase_service_role_client()
    logfire.debug(f"Getting phone number for uuid {uuid}")
    phone_number = service_level_client.from_(USER_META_INFORMATION_TABLE_NAME).select("phone_number").eq("uuid", uuid).execute().data[0]["phone_number"]
    return phone_number
