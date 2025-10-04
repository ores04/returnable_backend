import datetime

import datefinder
from pydantic import BaseModel

from supabase import Client

from server.core.ai.ai_clients.openai_client import OpenAIClient
from server.core.service.document_service.chunking import chunk_text
from server.core.service.supabase_connectors.supabase_documents_client import add_keywords_to_db, add_document_to_db


class DocumentKeyword(BaseModel):
    keyword: str

class DocumentKeywords(BaseModel):
    keywords: list[DocumentKeyword]



def process_text_input(text: str, title: str, jwt_token: str|None, supabase_client:Client = None, uuid:str=None) -> str:
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

    search_keywords = extract_search_keywords(text)

    summary = generate_summary(text)

    chunks.append(summary)

    openai_client = OpenAIClient()
    get_embedding = lambda x: openai_client.get_embedding(x)
    embeddings = [embedded for embedded in map(get_embedding, chunks)]

    date = extract_date_from_doc(text) # TODO: if non date found, use current date
    if date is None:
        date = datetime.date.today().isoformat()

    # build embedding dict
    document_dict = {"name": title,
                     "gültig_von": date,
                     "document_segments": [{"embedding": emb} for emb in embeddings]}

    doc_id = add_document_to_db(jwt_token=jwt_token, document_data=document_dict, supabase_client=supabase_client, uuid=uuid)

    # add keywords to db
    for kw in keywords:
        kw_dict = {"name": kw, "embedding": openai_client.get_embedding(kw), "document_id": doc_id}
        add_keywords_to_db(jwt_token=jwt_token, document_data=kw_dict, supabase_client=supabase_client)

    # add search keywords to db
    for skw in search_keywords:
        skw_dict = {"keyword": skw, "embedding": openai_client.get_embedding(skw), "document_id": doc_id}
        add_keywords_to_db(jwt_token=jwt_token, document_data=skw_dict, supabase_client=supabase_client)



    return doc_id

def extract_date_from_doc(text: str) -> str | None:
    """ This function extract all dates from the document"""
    dates = list(datefinder.find_dates(text, first="day"))
    if len(dates) == 0:
        return None
    # return the first date as iso format
    return dates[0].date().isoformat()

def extract_search_keywords(text: str) -> list[str]:
    """
    Thiss function extracts keywords which will be used to search for the document in a RAG system.
    The keywords should be descriptive and specific, so that they can be used as filters in a database.
    Args:
        text (str): The text to extract keywords from.
    """
    openai_client = OpenAIClient()
    instruction = """Absolut! Hier ist ein Prompt, der darauf ausgelegt ist, ein GPT-Modell zur Extrahierung von fünf beschreibenden Keywords aus einem Dokument anzuleiten. Diese Keywords sind speziell dafür gedacht, ein RAG-System (Retrieval-Augmented Generation) zu ergänzen und zu optimieren.
Prompt für die Keyword-Extraktion zur RAG-Optimierung
Rolle: Du bist ein Experte für die Verarbeitung natürlicher Sprache (NLP) und Wissensmanagement. Deine Aufgabe ist es, die zentralen Konzepte und Entitäten aus einem gegebenen Text zu identifizieren, um die Effizienz eines Retrieval-Augmented Generation (RAG) Systems zu verbessern.
Aufgabe: Analysiere das untenstehende Dokument und extrahiere die fünf (5) aussagekräftigsten und deskriptivsten Keywords. Diese Keywords sollten die Hauptthemen, wichtigsten Entitäten und den Kerninhalt des Dokuments prägnant zusammenfassen.
Kontext für die Keyword-Auswahl: Die generierten Keywords dienen dazu, das Dokument in einer Vektordatenbank zu indizieren und die Auffindbarkeit für relevante Benutzeranfragen in einem RAG-System zu erhöhen. Sie sollten daher:
Deskriptiv und spezifisch sein: Allgemeine Füllwörter sind zu vermeiden.
Die Kernkonzepte abdecken: Was sind die zentralen Ideen oder Objekte des Textes?
Potenzielle Suchanfragen antizipieren: Welche Begriffe würden Benutzer wahrscheinlich verwenden, um nach diesem Dokument zu suchen?
Wichtige Entitäten hervorheben: Namen von Personen, Organisationen, Orten oder spezifische Fachbegriffe einschließen. Beispiel:
Dokument:
Die Entdeckung der CRISPR-Cas9-Genschere durch Emmanuelle Charpentier und Jennifer Doudna im Jahr 2012 revolutionierte die Gentechnik. Diese Technologie ermöglicht präzise Veränderungen an der DNA von Organismen und hat weitreichende Anwendungen in der Medizin, beispielsweise bei der Behandlung von Erbkrankheiten wie Sichelzellanämie, sowie in der Landwirtschaft zur Entwicklung resistenterer Nutzpflanzen. Die ethischen Implikationen dieser mächtigen Technologie, insbesondere im Hinblick auf Keimbahneingriffe, werden jedoch kontrovers diskutiert.
Erwartete Ausgabe:
CRISPR-Cas9, Gentechnik, Emmanuelle Charpentier, Jennifer Doudna, ethische Implikationen"""
    response = openai_client.request_text_model(
        instruction=instruction,
        prompt=text,
        model="gpt-5-mini",
        response_model=DocumentKeywords
    )
    if isinstance(response, DocumentKeywords):
        return [kw.keyword for kw in response.keywords]
    else:
        raise ValueError(
            "Unexpected response format from OpenAI API. Expected a DocumentKeywords instance.")


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




