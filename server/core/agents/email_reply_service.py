import re
import asyncio
from dataclasses import field, dataclass
from enum import Enum
from typing import List, Union

import logfire
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import UsageLimits

from server.core.ai_clients.openai_client import OpenAIClient

SMART_MODEL = "openai:gpt-5"
CHEAP_MODEL = "openai:gpt-5-mini"
CHEAPEST_MODEL = "openai:gpt-5-nano"
# for testing purposes, we can use a cheaper model

SMART_MODEL = CHEAP_MODEL

load_dotenv()


logfire.configure()
logfire.instrument_pydantic_ai()

class RemoveIds(BaseModel):
    """ This model is used to remove ids from the tasks and inputs."""
    ids: List[int]





class EmailReplyService:

    @staticmethod
    def check_if_mail_is_reply(email_from: str,subject: str, initial_sent_to: str, subject_sent: str) -> bool:
        """ Check if the email is a reply to our inital request."""

        # first we check if the mail is marked with RE, AW, Antw to our initial subject
        prefiexes = ["RE:", "AW:", "Antw:", "Re:", "Aw:", "Antw:", "re:", "aw:", "antw:"]
        subject_is_reply = any(subject.startswith(prefix) for prefix in prefiexes) and subject_sent.lower() in subject.lower()
        if subject_is_reply:
            return True

        # then we check if the email is from the same email address we sent the initial mail to
        if EmailReplyService.is_company_mail_replier(initial_sent_to, email_from):
            return True

        return False

    @staticmethod
    def is_company_mail_replier(company:str, mail_from:str) -> bool:
        """ We check if the mail is from the company domain."""
        company = company.lower().replace(" ", "")
        mail_from = mail_from.lower()

        # Extract the domain from the email address
        match = re.search(r'@([a-zA-Z0-9.-]+)', mail_from)
        if match:
            domain = match.group(1)
            # Check if the company name is part of the domain
            if company in domain:
                return True

        return False

    @staticmethod
    def confirm_reply_mail(email_sent, email_reply) -> bool:
        """ THis function uses a LLM to confirm that the mail is a reply to our initial mail."""
        client = OpenAIClient()

        PROMPT = lambda sent, reply: f"""
        Du bist ein KI Modell, welches E-Mails analysiert. Du hast eine E-Mail verfasst, um eine Reklamation bei einem Unternehmen einzureichen.
        Nun hast du eine Antwort auf diese E-Mail erhalten. Deine Aufgabe ist es zu bestätigen, ob die Antwort-E-Mail tatsächlich eine Antwort auf deine ursprüngliche E-Mail ist.
        Antworte mit "Ja" oder "Nein".
        Hier ist die ursprüngliche E-Mail, die du gesendet hast:
        {sent}
        Hier ist die Antwort-E-Mail, die du erhalten hast:
        {reply}
        Ist die Antwort-E-Mail eine Antwort auf deine ursprüngliche E-Mail?
        """

        response = client.request_text_model(
            instruction="Beantworte die Frage mit Ja oder Nein.",
            prompt=PROMPT(email_sent, email_reply),
            model="gpt-5-nano",
        )

        return "Ja" in response

    @staticmethod
    def determine_duplicated_tasks(tasks: List[Union['TodoItem', 'InputItem']]) -> RemoveIds:
        """ This function determines duplicated tasks from the task list."""
        client = OpenAIClient()

        tasks_str = "\n".join([str(task) for task in tasks])

        PROMPT = lambda task: f"""
        You are an AI model that analyzes a list of tasks and input requests. Your task is to identify any duplicate tasks or input requests in the list.
        A duplicate is when two tasks ask the same thing, even if they are worded differently. Keep the task that makes the most sense and remove the others.
        Here is the list of tasks and input requests:
        {task}
        """

        response = client.request_text_model(
            instruction="Beantworte die Frage mit Ja oder Nein.",
            prompt=PROMPT(tasks_str),
            model="gpt-5-nano",
            response_model=RemoveIds
        )

        return response


    @staticmethod
    def remove_duplicated_tasks(tasks: List[Union['TodoItem', 'InputItem']], remove_ids: RemoveIds) -> List[
        Union['TodoItem', 'InputItem']]:
        """ This function removes duplicated tasks from the task list."""
        ids_to_remove = set(remove_ids.ids)
        return [task for task in tasks if int(task.id) not in ids_to_remove]




class TodoItem(BaseModel):
    """This model represents a to_do that the user has to do."""
    id: str
    description: str

    def __str__(self):
        return f"TodoItem(id={self.id}, description={self.description})"

class RequestedType(str, Enum):
    """This enum represents the type of input that is requested."""
    TEXT = "text"
    NUMBER = "number"
    IMAGE = "image"

class InputItem(BaseModel):
    """This model represents an input that the user has to provide."""
    id: str
    requested_input: str
    requested_type: RequestedType

    def __str__(self):
        return f"InputItem(id={self.id}, requested_input={self.requested_input})"

class EmailProcessingResult(BaseModel):
    """ This model represents the result of processing the reply email."""
    tasks: list[TodoItem | InputItem] = []
    summary: str | None = None


class CheckOkay(BaseModel):
    """ This model represents that the check was okay."""
    ok: bool = True

class CheckNotOkay(BaseModel):
    """ This model represents that the check was not okay."""
    ok: bool = False
    reason: str

usage_limit = UsageLimits(
    request_limit=50,
)

@dataclass
class ReplyDeps:
    """
    This class is used to inject dependencies into the reply agent. THe inital mail is sent by the user to the company.
    The reply mail is set by the company to the user.
    """
    email_sent_initial: str
    email_reply: str
    tasks: List[TodoItem | InputItem] = field(default_factory=list)

master_reply_agent = Agent(
    CHEAP_MODEL,
    system_prompt="You are tasked with finding out what actions the user needs to take to respond to a reply email from a company. "
                  " Your task is to analyze the reply email and determine if any further actions are required from the user. If any actions are "
                  "required to fulfill the mails intend, create a to-do item for each action using the create_todo tool."
                  "ONLY ADD TODOS THAT ARE REQUESTED BY THE COMPANY IN THE REPLY EMAIL. Do not add any other tasks."
                  " If you need more information from the user to answer the email create an input item using the request_input tool. After creating the "
                  "to-do and input items use the check tool to check if you have everything you need to answer the email."
                  "If the check is CheckOk return the todos and a summary, if not refine accordingly and check again. ",

    instrument=True,
    deps_type=ReplyDeps,
    output_type=EmailProcessingResult,
)

check_agent = Agent(
    CHEAP_MODEL,
    system_prompt="You are a superviser to check if the mail from the company can be answerd if the todos are fulfilled."
                  "Check if in the mail are tasks mentioned that are no yet the task list."
                  "Only return not okay if something is missing. Do not return not okay if everything is fine."
                  " If everything is okay, use the CheckOkay tool to confirm. If something is missing, use the CheckNotOkay tool to explain what is missing.",
    deps_type=ReplyDeps,
    output_type=[CheckOkay | CheckNotOkay],
    instrument=True,
)

@master_reply_agent.tool
async def check(ctx: RunContext[ReplyDeps]) -> CheckOkay | CheckNotOkay:
    """ This tool checks if the reply agent has everything it needs to answer the email."""

    tasks_str = "\n".join([str(task) for task in ctx.deps.tasks])

    result = await check_agent.run(
        "Check if you have everything you need to answer the email this is the mail text" + ctx.deps.email_reply +
        "This is the task list" + tasks_str,
        deps=ctx.deps,
        usage_limits=usage_limit,
    )
    return result.output


@master_reply_agent.tool
def create_todo(ctx: RunContext[ReplyDeps], description: str) -> TodoItem:
    """ This tool creates a to do item for the user. Create exactly one to-do item per call."""
    new_todo = TodoItem(id=str(len(ctx.deps.tasks) + 1), description=description)
    ctx.deps.tasks.append(new_todo)
    return new_todo

@master_reply_agent.tool
def request_input(ctx: RunContext[ReplyDeps], requested_input: str) -> InputItem:
    """ This toolcreate a requests an input from the user. Request exactly one input per call."""
    new_input = InputItem(id=str(len(ctx.deps.tasks) + 1), requested_input=requested_input)
    ctx.deps.tasks.append(new_input)
    return new_input

def process_mail_reply(email_sent: str, email_reply: str) -> EmailProcessingResult:

    deps = ReplyDeps(
        email_sent_initial=email_sent,
        email_reply=email_reply,
    )

    async def process(deps: ReplyDeps):
        result = await master_reply_agent.run(
            "Analyze the reply email and determine what actions the user needs to take to respond to the email."
            "MAIL: (mail sent by the company --> analyze)" + deps.email_reply + " INITAL MAIL: (The mail sent by the user) " + deps.email_sent_initial,
            deps=deps,
            usage_limits=usage_limit,
        )
        return result.output

    result = asyncio.run(process(deps))

    # Remove duplicated tasks
    async def remove_duplicates(result: EmailProcessingResult) -> EmailProcessingResult:
        remove_ids = EmailReplyService.determine_duplicated_tasks(result.tasks)
        result.tasks = EmailReplyService.remove_duplicated_tasks(result.tasks, remove_ids)
        return result

    result = asyncio.run(remove_duplicates(result))

    return result


if __name__ == "__main__":
    # Example usage
    email_sent = """Sehr geehrte Damen und Herren,

    ich möchte eine Reklamation bezüglich meiner letzten Bestellung einreichen. Die bestellte Ware ist beschädigt angekommen.

    Mit freundlichen Grüßen,
    Max Mustermann"""

    email_reply = """Sehr geehrter Herr Mustermann,

    vielen Dank für Ihre Nachricht. Es tut uns leid zu hören, dass Ihre Bestellung beschädigt angekommen ist. 
    Könnten Sie uns bitte Fotos der beschädigten Ware zusenden, damit wir den Vorfall weiter untersuchen können?

    Mit freundlichen Grüßen,
    Kundenservice"""

    company_name = "Beispiel GmbH"
    subject_sent = "Reklamation meiner letzten Bestellung"

    deps = ReplyDeps(
        email_sent_initial=email_sent,
        email_reply=email_reply,
    )

    async def main(deps: ReplyDeps):
        result = await master_reply_agent.run(
            "Analyze the reply email and determine what actions the user needs to take to respond to the email."
            "MAIL: (mail sent by the company --> analyze)" + deps.email_reply + " INITAL MAIL: (The mail sent by the user) " + deps.email_sent_initial,
            deps=deps,
            usage_limits=usage_limit,
        )
        return result.output

    import asyncio
    result = asyncio.run(main(deps))

     # Print the results

    print("Tasks to do:")
    for task in result.tasks:
        print(task)

    print("\nSummary:")
    print(result.summary)





