from server.core.service.supabase_connectors.supabase_client import get_supabase_service_role_client


def add_phone_number_to_supabase():
    # get the priviled client
    client = get_supabase_service_role_client()
    phone_number = input("Enter the phone number (in format +1234567890): ")
    # remove the +
    phone_number = phone_number.replace("+", "")
    uuid = input("Enter the uuid: ")
    response = client.from_("USER_META_INFORMATION").upsert({"phone_number": f"{phone_number}", "uuid": f"{uuid}"}).execute()
    print(response)
    response.raise_when_api_error(response)
    print("Phone number added successfully")


if __name__ == "__main__":
    # ask for an input to select one of the functions
    print("Select a function to run:")
    print("(1) add_phone_number_to_supabase")
    choice = input("Enter the number of the function to run: ")
    match choice:
        case "1":
            add_phone_number_to_supabase()

        case _:
            print("Invalid choice")
