from storage3.types import UploadResponse
from supabase import Client

from server.core.service.supabase_connectors.supabase_client import get_supabase_client, \
    get_supabase_service_role_client, get_uuid_from_phone_number


class SupabaseBucketClient:

    def __init__(self, supabase_client: Client, uuid: str):
        self.supabase_client = supabase_client
        if uuid is None:
            # Here a client is expected that was created using a jwt token
            self.uuid = self.supabase_client.auth.get_user().user.id
        else:
            self.uuid = uuid


    def add_document_to_bucket(self, file, name, bucket_name: str) -> UploadResponse:
        return self.supabase_client.storage.from_(bucket_name).upload(f"{self.uuid}/{name}", file)

    #def retrieve_document_from_bucket(self, bucket_name: str, name: str) -> :




class SupabaseBucketClientFactory:

    @staticmethod
    def create_from_jwt_token(jwt_token: str):
        client = get_supabase_client(jwt_token)
        return SupabaseBucketClient(client)

    @staticmethod
    def create_from_service_level_client(phone_number: str):
        client = get_supabase_service_role_client()
        uuid  = get_uuid_from_phone_number(phone_number)
        return SupabaseBucketClient(client, uuid)


