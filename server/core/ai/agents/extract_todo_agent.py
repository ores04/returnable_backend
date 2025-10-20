import datetime
from dataclasses import dataclass

import dateparser
import logfire
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import UsageLimits

load_dotenv()

from server.core.ai.agents.agent_consts import CHEAPEST_MODEL, CHEAP_MODEL


class TodoModel(BaseModel):
    event_time: str | None = None  # ISO 8601 format - when the task is due
    todo_text: str  # Text of the to_do/task
    todo_tags: list[str] | None = None  # optional list of tags/categories associated with the todo


SYSTEM_PROMPT = """Es wird eine Whatsapp Nachricht übergeben, welche eine Aufgabe enthält.
Ziel ist es die Aufgabe und optional die Zeit wann die Aufgabe erledigt werden soll zu extrahieren.
Das Tool parse_date_from_natural_language soll genutzt werden um temporale Phrasen wie 'morgen um 11' in ISO Strings zu parsen.
Das Tool erwartet eine Englische Eingabe.

Es kann sein, dass der Nutzer dem Todo eine oder mehrere Tags hinzufügt. Falls das so ist, extrahiere die
Tags oder Kategorien und weise sie dem Todo zu. Wähle die Tags aus der Liste possible_tags. Wichtig:
der Nutzer muss diese Tags explizit nennen, du darfst keine Tags hinzufügen, die der Nutzer nicht erwähnt hat.
Tags sind optional.

Der Output ist ein TodoModel mit der Struktur {
event_time - die Zeit wann die Aufgabe fällig ist (optional, kann None sein) - falls keine Zeit angegeben wurde, wann das Todo erledigt werden soll, dann None
todo_text - die Aufgabe/das was gemerkt werden soll,
todo_tags - liste der tags/kategorien, welchen das Todo laut Nutzer zugeordnet werden soll (optional)}"""


todo_usage_limit = UsageLimits(
    request_limit=5,
)

@dataclass
class TodoDeps:
    """
    This class is used to inject dependencies into the todo extraction agent.
    """
    tzinfo: str = "Europe/Berlin"  # default timezone
    possible_tags: list[str] = None  # possible tags for the todo

master_extract_todo_agent = Agent(
    CHEAP_MODEL,
    system_prompt=SYSTEM_PROMPT,
    instrument=True,
    deps_type=TodoDeps,
    output_type=TodoModel,)

@master_extract_todo_agent.tool
async def parse_date_from_natural_language(ctx: RunContext[TodoDeps], text: str) -> str | None:
    """
    Parses a date from natural language text. The text can be in one of the following formats:
    - "in 2 hours"
    - "tomorrow at 3pm"
    - "next Monday"
    - "on 25th December"
    - "on 2023-12-25"
    and the function should return the date in ISO 8601 format (YYYY-MM-DDTHH:MM:SS).

    Args:
        text (str): The text to parse the date from.
        ctx (RunContext[TodoDeps]): The run context containing dependencies.

    Returns:
        str | None: The parsed date in ISO 8601 format, or None if no date is found.
    """
    date = dateparser.parse(text, languages=["de", "en"], settings={'TIMEZONE': ctx.deps.tzinfo, 'RETURN_AS_TIMEZONE_AWARE': True})
    if date is not None:
        logfire.info(f"Parsed date {date} has timezone {date.tzinfo}'")
        date = date.isoformat()
    return date



if __name__ == "__main__":
    load_dotenv()
    logfire.configure()
    async def main():
        test_text = "Merk dir: Milch kaufen bis morgen 15 Uhr, dass soll in die Kategorie Einkauf"
        res = await master_extract_todo_agent.run(test_text, deps=TodoDeps(tzinfo="Europe/Berlin", possible_tags=["Einkauf", "Arbeit", "Privat"]),)
        return res.output


    import asyncio
    result = asyncio.run(main())
    print(result)
