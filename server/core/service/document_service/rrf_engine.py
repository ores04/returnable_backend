from supabase import Client

from server.core.ai.ai_clients.openai_client import OpenAIClient


class RAGQuery:
    query: str

class RRFEngine:

    def __init__(self, supabase_client: Client, table_name: str, keyword_table_name: str, temporal_constraint):
        self.supabase_client = supabase_client
        self.table_name = table_name
        self.keyword_table_name = keyword_table_name

    def enhance_query(self, query: str) -> str:
        """Enhances the query using a language model to improve search results."""
        client = OpenAIClient()
        response  = client.request_text_model(
            instruction="Die folgende Anfrage ist von einem Benutzer, welcher ein Dokument in einer Vector-Datenbank sucht. Verbessere die Anfrage so, dass die Suche in der Datenbank bessere Ergebnisse liefert. Antworte nur mit der verbesserten Anfrage.",
            prompt=query,
            model="gpt-5-nano",
            response_model=RAGQuery
        )
        if isinstance(response, RAGQuery):
            return response.query
        else:
            raise ValueError(
                "Unexpected response format from OpenAI API. Expected a RAGQuery instance.")


    def search_with_semantic_similarity(self):
        """ Searches the table for documents similar to the query using semantic similarity. """
        pass



    def search_with_keyword_similarity(self):
        pass





