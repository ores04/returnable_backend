import asyncio
import os

from server.core.agents.email_reply_service import EmailReplyService, process_mail_reply
from server.core.email_service.gmail_client import GmailClient
from server.core.email_service.supabase_client import get_supabase_service_role_client, \
    get_all_active_returnable_requests, get_latest_mail_with_returnable_id, add_mail_to_db, add_task_to_db
from supabase import Client

CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "oauth_client_id.json")
gmail_client = GmailClient(CREDENTIALS_PATH)

async def refresh_mails_and_check_if_reply():
    service_client = get_supabase_service_role_client()

    returnable_requests = get_mail_ids_to_check(service_client)
    if returnable_requests is None or len(returnable_requests) == 0:
        print("No returnable requests found.")
        return

    returnable_request_processing_tasks = []

    for returnable_request in returnable_requests:
        async def handle_request_wrapper(_returnable_request, _service_client):
            """
            This wrapper can now properly handle async or sync code.
            """
            print(f"Starting processing for request: {_returnable_request.get("id")}")

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,  # Use the default thread pool executor
                process_request,  # The function to run
                _returnable_request,  # First argument to process_request
                _service_client  # Second argument to process_request
            )
            print(f"Finished processing for request: {_returnable_request.get("id")}")


        returnable_request_processing_tasks.append(handle_request_wrapper(returnable_request, service_client))

    # wait for all tasks to complete
    await asyncio.gather(*returnable_request_processing_tasks)
    print("All returnable requests processed.")


def process_request(returnable_request: dict, service_client: Client):
    # Hier würde die Logik stehen, um die E-Mails zu verarbeiten und ggf. Antworten zu senden
    return_request_id = returnable_request.get("id")
    assert return_request_id is not None, "Returnable request must have an ID"

    latest_mail_for_request = get_latest_mail_with_returnable_id(service_client, return_request_id)
    if latest_mail_for_request.get("send_by_me") != "True":
        print("Skipping because company already replied or no mail was sent at all. We must now take an action")
        return

    uuid = returnable_request.get("user_id")
    gmail_client = GmailClient(CREDENTIALS_PATH)

    gmail_client.authenticate(None, service_client, uuid)
    newest_mails = gmail_client.read_new_mails(None, service_client, uuid, max_results=5)

    reply_mail = None

    for mail in newest_mails:
        if EmailReplyService.check_if_mail_is_reply(mail.get("sender"), mail.get("subject"), latest_mail_for_request.get("to"), latest_mail_for_request.get("subject")):
            reply_mail = mail
            break

    if reply_mail is None:
        print("No reply mail found for returnable request ID:", return_request_id)
        return

    add_mail_to_db(None, service_client, reply_mail, return_request_id, send_by_me=False)

    confirm_reply = EmailReplyService.confirm_reply_mail(latest_mail_for_request.get("body"), reply_mail.get("body"))
    if not confirm_reply:
        print("Reply mail not confirmed by AI for returnable request ID:", return_request_id)
        return

    # generate possible tasks
    processing_result = process_mail_reply(latest_mail_for_request.get("body"), reply_mail.get("body"))
    print("Generated tasks:", processing_result.tasks)

    if processing_result.tasks is None:
        # todo propose reply
        print("No tasks generated for returnable request ID:", return_request_id)
        print("Proposing reply...")
        return
    else:
        # add tasks to db
        for task in processing_result.tasks:
            print("Adding:", task)
            add_task_to_db(service_client, task, return_request_id)
        print("All tasks added for returnable request ID:", return_request_id)
        return

def get_mail_ids_to_check(service_client: Client) -> list[dict]:
    try:
        returnable_requests = get_all_active_returnable_requests(service_client)
        return returnable_requests
    except Exception as e:
        print("Error getting returnable requests from database:", e)
        return []

if __name__ == "__main__":
    res = asyncio.run(refresh_mails_and_check_if_reply())



