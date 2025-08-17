import asyncio
from bs4 import BeautifulSoup
import logfire
import requests

from googlesearch import search
from pydantic import BaseModel
from pydantic_ai.usage import UsageLimits
from pydantic_ai import Agent, RunContext
from dataclasses import dataclass, field

from dotenv import load_dotenv

SMART_MODEL = "openai:gpt-5"
CHEAP_MODEL = "openai:gpt-4o-mini"
# for testing purposes, we can use a cheaper model

SMART_MODEL = CHEAP_MODEL

load_dotenv()


logfire.configure()
logfire.instrument_pydantic_ai()

search_usage_limit = UsageLimits(
    request_limit=50,
)


class SearchResult(BaseModel):
    """ This model represents a search result from the search engine."""
    title: str
    link: str
    snippet: str | None = None


class EmptyPage(BaseModel):
    """ This model represents an empty page, used when no results are found."""


@dataclass
class SearchDeps:
    """
    This class is used to inject dependencies into the search agent.
    """
    max_results_per_query: int = 10
    current_search_results: list[SearchResult] = field(default_factory=list)


master_search_agent = Agent(
    SMART_MODEL,
    system_prompt="You are an expert search agent. You task is to find the customer support email address for the company that will be mentioned in the user query. To start the search use the search tool.",
    instrument=True,
    deps_type=SearchDeps,
    output_type=[SearchResult | str | EmptyPage],
)

site_agent = Agent(
    SMART_MODEL,
    system_prompt="You are an agent tasked with finding relevant information regarding the customer support email address for the company that will be mentioned in the user query. This information can be in the form of the mail address or a link to a page, where the email address is likely to be found."
    "If you found the email address that is the support email, return it directly as a string, return ONLY the email address. Only call tools if you have not found the address yet. If you found a link to a page, where the email address is likely to be found a SearchResult object with the link and a snippet of what the page is about. "
    "If you found no information, return an EmptyPage object. You should search with German keywords, as the user will likely use German keywords.",
    instrument=True,
    deps_type=SearchDeps,
    output_type=[SearchResult | str | EmptyPage],
)


def extract_email_from_text(text: str) -> str | None:
    """
    Extracts an email address from the given text.
    Returns the email address if found, otherwise None.
    """
    import re
    # Regular expression to match email addresses
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(email_pattern, text)
    return match.group(0) if match else None


@master_search_agent.tool
async def general_search(ctx: RunContext[SearchDeps], query: str) -> list[SearchResult]:
    """
    This tool performs a general search using the provided query. The Query should be max 5 keywords.
    It returns a list of SearchResult objects.
    """

    # execute the seach using an async executor to not block the event loop
    logfire.info(f"Performing search for query: {query}")
    loop = asyncio.get_event_loop()
    # if there is an async executor, we can use it to run the search in a non-blocking way
    if loop.is_running():
        results = await loop.run_in_executor(
            None, lambda: search(
                query, num_results=ctx.deps.max_results_per_query, advanced=True))

    else:
        results = search(
            query, num_results=ctx.deps.max_results_per_query, advanced=True)
    list_of_results = [SearchResult(
        title=result.title, link=result.url, snippet=result.description) for result in results]
    ctx.deps.current_search_results = list_of_results
    return list_of_results


@master_search_agent.tool
def search_for_email(ctx: RunContext[SearchDeps], title: str) -> list[SearchResult | str | EmptyPage]:
    """ This tool searches a site indicated by the title for the customer support email address. It will return the current possible sites to search in the next step or the actual email address as a string."""
    if not ctx.deps.current_search_results:
        return [EmptyPage()]
    # get the page to search indicated by the title
    page_to_search = next(
        (result for result in ctx.deps.current_search_results if result.title == title), None)
    if not page_to_search:
        # We return all other possible sites to search because the title was not found in the current search results.
        return ctx.deps.current_search_results

    # remoove the page to search from the current search results so it won't be searched again
    ctx.deps.current_search_results.remove(page_to_search)

    # If the page is found, we use the site_agent to search for the email address
    try:
        page_content = get_webpage_body(page_to_search.link)
    except requests.RequestException as e:
        logfire.error(f"Failed to fetch {page_to_search.link}: {e}")
        return ctx.deps.current_search_results

    result = site_agent.run_sync(
        page_content,
        usage=ctx.usage,

    )

    if isinstance(result.output, str):
        # If the result is a string, we assume it's the email address
        return [result.output]
    elif isinstance(result.output, SearchResult):
        # If the result is a SearchResult, we return it
        return ctx.deps.current_search_results + [result.output]
    elif isinstance(result.output, EmptyPage):
        # If the result is an EmptyPage, we return the current search results
        return ctx.deps.current_search_results
    else:
        logfire.error(f"Unexpected result type: {type(result.output)}")
        return ctx.deps.current_search_results


def get_webpage_body(url: str) -> str:
    """
    This function fetches the body of a webpage given its URL.
    It uses the requests library to make a GET request and returns the text content of the response.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error for bad responses
        soup = BeautifulSoup(response.text, 'html.parser')
        # Extract the body text from the soup object
        body = soup.body
        if body:
            return body.get_text(separator=' ', strip=True)
        else:
            logfire.warning(f"No body found in the response from {url}")
            return ""

    except requests.RequestException as e:
        logfire.error(f"Error fetching {url}: {e}")
        raise requests.RequestException(f"Failed to fetch {url}: {e}")


def hello_world():
    """
    A simple function to demonstrate the use of the Agent.
    """

    agent = Agent(
        'openai:gpt-4o',
        system_prompt='Be concise, reply with one sentence.',
        instrument=True,
    )

    result = agent.run_sync('Where does "hello world" come from?')
    print(result.output)


if __name__ == "__main__":
    async def main():
        result = await master_search_agent.run(
            "Find the customer support email address for the company 'Marschall'.",
            deps=SearchDeps(max_results_per_query=5),
            usage_limits=search_usage_limit,
        )
        return result.output

    result = asyncio.run(main())

    print(result)  # This line was missing
    print(extract_email_from_text(result))  # Extract email from the result
