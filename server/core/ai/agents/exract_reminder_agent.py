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


class ReminderModel(BaseModel):
    event_time: str # ISO 8601 format
    reminder_text: str # Text of the reminder
    reminder_time: list[str] # ISO 8601 format


SYSTEN_PROMPT = """Es wird eine Whatsapp Nachricht übergeben, welche eine Aufgabe und Zeitangaben enthäält. 
Ziel ist es die Aufgabe, die Zeit wann die Aufgabe erledigt werden soll und die Zeiten wann der Nutzer daran erinnert werden möchte zu extrahieren.
Das Tool parse_date_from_natural_langugage soll genutzt werden um temporale phrasen wie 'morgen um 11' in ISO Strings zu parsen 
Das Tool erwartet eine Englische eingabe.
Der Output ist ein ReminderModel mit der Struktur {
event_time - die Zeit wann die Aufgabe fällig ist. Kann gleich sein wie die letzte reminder_time,
reminder_time - die Zeiten wann erinnert werden soll. Kann auch leer sein,
reminder_text - an was erinnert werden soll}"""#


reminder_usage_limit = UsageLimits(
    request_limit=5,
)

@dataclass
class ReminderDeps:
    """
    This class is used to inject dependencies into the reminder extraction agent.
    """
    tzinfo: str = "Europe/Berlin"  # default timezone

master_extract_reminder_agent = Agent(
    CHEAP_MODEL,
    system_prompt=SYSTEN_PROMPT,
    instrument=True,
    deps_type=ReminderDeps,
    output_type=ReminderModel,)

@master_extract_reminder_agent.tool
async def parse_date_from_natural_langugage(ctx: RunContext[ReminderDeps], text: str) -> str | None:
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
        ctx (RunContext[ReminderDeps]): The run context containing dependencies.

    Returns:
        str | None: The parsed date in ISO 8601 format, or None if no date is found.
    """
    date = dateparser.parse(text, languages=["de", "en"], settings={'TIMEZONE': ctx.deps.tzinfo, 'RETURN_AS_TIMEZONE_AWARE': True})
    if date is not None:
        # get the machines timezone
        logfire.info(f"Parsed date {date} has timezone {date.tzinfo}'")
        date = date.isoformat()
    return date



if __name__ == "__main__":
    load_dotenv()
    logfire.configure()
    async def main():
        test_text = "Hausaufgaben bis morgen 15 Uhr erledigen, erinnere mich 2 Stunden vorher"
        res = await master_extract_reminder_agent.run(test_text)
        return res.output


    import asyncio
    result = asyncio.run(main())
    print(result)