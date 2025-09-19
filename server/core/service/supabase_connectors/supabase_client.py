from dotenv import load_dotenv
import os

from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from supabase_auth import SignInWithEmailAndPasswordCredentials, AuthResponse

load_dotenv()

USER_META_INFORMATION_TABLE_NAME = "USER_META_INFORMATION"

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
    service_level_client = get_supabase_service_role_client()

    uuid = service_level_client.from_(USER_META_INFORMATION_TABLE_NAME).select("uuid").eq("phone_number", phone_number).execute().data[0]["uuid"]
    return uuid
