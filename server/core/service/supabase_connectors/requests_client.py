from pydantic import BaseModel
from supabase import Client

from server.core.service.supabase_connectors.supabase_client import get_supabase_client

RETURNABLE_REQUEST_TABLE_NAME = "RETURN_REQUEST"


class ReturnableRequest(BaseModel):
    """Pydantic model for a returnable request."""
    user_id: str
    reclamation_reason: str
    product_from_company: str
    customer_id: str
    invoice_id: str
    invoice_date: str


def add_returnable_request_to_db(jwt_token: str, request_data: dict):
    """This function adds a new returnable request to the database."""
    # assert that all required fields are present
    required_fields = ["user_id", "reclamation_reason", "product_from_company", "customer_id", "invoice_id", "invoice_date"]

    for field in required_fields:
        if field not in request_data:
            raise ValueError(f"Missing required field: {field}")

    supabase_client = get_supabase_client(jwt_token=jwt_token)

    # set the user id from the token to ensure the user cannot create requests for other users
    user = supabase_client.auth.get_user(jwt_token).user
    request_data["user_id"] = user.id

    # remove id so that is set automatically by supabase
    if "id" in request_data:
        del request_data["id"]

    # set the request to active by default
    request_data["active"] = True

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


def get_all_active_returnable_requests(service_client: Client):
    """This function returns all active returnable requests from the database."""
    response = service_client.table(RETURNABLE_REQUEST_TABLE_NAME).select("*").eq("active", "true").execute()
    response.raise_when_api_error(response)
    return response.data
