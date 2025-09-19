from pydantic import BaseModel

from supabase import Client

from server.core.ai.ai_clients.openai_client import OpenAIClient
from server.core.service.document_service.chunking import chunk_text
from server.core.service.supabase_connectors.supabase_client import add_document_to_db, add_keywords_to_db


class DocumentKeyword(BaseModel):
    keyword: str

class DocumentKeywords(BaseModel):
    keywords: list[DocumentKeyword]



def process_text_input(text: str, title: str, jwt_token: str|None, supabase_client:Client = None) -> str:
    """
    Processes the input text and returns True if successful.

    Args:d
        text (str): The text to be processed.
        title (str): The title of the document.
        jwt_token (str): The JWT token for authentication.

    Returns:
        str: the id of the created document
    """
    chunks = chunk_text(text)

    keywords = extract_keywords(text)

    summary = generate_summary(text)

    chunks.append(summary)

    openai_client = OpenAIClient()
    get_embedding = lambda x: openai_client.get_embedding(x)
    embeddings = [embedded for embedded in map(get_embedding, chunks)]

    # build embedding dict
    document_dict = {"name": title,
                     "document_segments": [{"embedding": emb} for emb in embeddings]}

    doc_id = add_document_to_db(jwt_token=jwt_token, document_data=document_dict, supabase_client=supabase_client)

    # add keywords to db
    for kw in keywords:
        kw_dict = {"name": kw, "embedding": openai_client.get_embedding(kw), "document_id": doc_id}
        add_keywords_to_db(jwt_token=jwt_token, document_data=kw_dict, supabase_client=supabase_client)

    return doc_id


def generate_summary(text: str) -> str:
    """
    Generates a summary for the given text using OpenAI.

    Args:
        text (str): The text to be summarized.

    Returns:
        str: The generated summary.
    """
    openai_client = OpenAIClient()
    instruction = "Erstelle eine prägnante, 2- bis 3-sätzige Zusammenfassung des folgenden Dokuments. Die Sätze sollen die wichtigsten Fakten und Haupterkenntnisse so kurz wie möglich darstellen, um in einem RAG-System als nützliche Antwort auf eine Nutzeranfrage zu dienen."
    response = openai_client.request_text_model(
        instruction=instruction,
        prompt=text,
        model="gpt-5-mini",
    )
    if isinstance(response, str):
        return response.strip()
    else:
        raise ValueError(
            "Unexpected response format from OpenAI API. Expected a string.")

def extract_keywords(text: str) -> list[str]:
    """
    Extracts keywords from the given text using OpenAI.

    Args:
        text (str): The text to extract keywords from.

    Returns:
        list[str]: A list of extracted keywords.
    """
    openai_client = OpenAIClient()
    instruction = "Finde bis zu 5 relevante Keywords, die den Hauptinhalt des folgenden Dokuments widerspiegeln. Schließe bei den Keywords relevante spezifische Informationen ein, die als Filter in einer Datenbank dienen könnten (z.B. 'Bestellnummer: 4711', 'Projekt: Alpha', 'Datum: 01.01.2024')."
    response = openai_client.request_text_model(
        instruction=instruction,
        prompt=text,
        model="gpt-5-mini",
        response_model=DocumentKeywords,
    )
    if isinstance(response, DocumentKeywords):
        return [kw.keyword for kw in response.keywords]
    else:
        raise ValueError(
            "Unexpected response format from OpenAI API. Expected a DocumentKeywords instance.")




