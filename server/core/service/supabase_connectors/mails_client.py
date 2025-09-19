from supabase import Client

from server.core.service.supabase_connectors.supabase_client import get_supabase_client

RETURN_MAILS_TABLE_NAME = "RETURN_MAILS"


def get_latest_mail_with_returnable_id(service_client: Client, returnable_id: str) -> dict:
    """This function returns all mails with the given returnable id from the database."""
    response = service_client.table(RETURN_MAILS_TABLE_NAME).select("*").eq("return_request_id", returnable_id).order(
        "created_at", desc=True
    ).limit(1).execute()
    response.raise_when_api_error(response)
    return response.data[0] if response.data and len(response.data) > 0 else {}


def add_mail_to_db(jwt_token: str | None, service_client: Client | None, mail_data: dict, returnable_id: str, send_by_me: bool = False):
    """This function adds a new mail to the database."""
    assert jwt_token or service_client, "Either jwt_token or service_client must be set"
    if jwt_token:
        service_client = get_supabase_client(jwt_token=jwt_token)
    mail_data = {
        "return_request_id": returnable_id,
        "to": mail_data.get("sender"),  # this is in fact the mail exchange partner
        "send_by_me": send_by_me,
        "body": mail_data.get("body"),
        "subject": mail_data.get("subject"),
    }

    response = service_client.table(RETURN_MAILS_TABLE_NAME).insert(mail_data).execute()
    response.raise_when_api_error(response)

    return response.data
