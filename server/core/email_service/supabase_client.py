
from dotenv import load_dotenv
import os
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions

load_dotenv()


TOKEN_TABLE_NAME = "REFRESH_TOKEN"


url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

def get_supabase_client(jwt_token:str) -> Client:
    return  create_client(url, key, options=SyncClientOptions(
        headers={
            "Authorization": f"Bearer {jwt_token}"
        }
    ))