from server.core.service.supabase_connectors.supabase_client import get_supabase_client

ACTION_TABLE_NAME = "ACTION_STEPS"


def add_action_to_db(jwt_token: str, action_data: dict):
    """This function adds a new action to the database."""
    # assert that all required fields are present
    required_fields = ["title", "summary", "details", "user_id", "returnable_id", "type", "order_id"]

    for field in required_fields:
        if field not in action_data:
            raise ValueError(f"Missing required field: {field}")

    supabase_client = get_supabase_client(jwt_token=jwt_token)

    response = supabase_client.table(ACTION_TABLE_NAME).insert(action_data).execute()

    response.raise_when_api_error(response)

    return response.data
