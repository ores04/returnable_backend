""" This file exposes a function to chunk text into pieces and return them as a list. """
from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 150) -> List[str]:
    """
    Chunks the input text into smaller pieces.

    Args:
        text (str): The text to be chunked.
        chunk_size (int): The maximum size of each chunk.
        chunk_overlap (int): The number of overlapping characters between chunks.

    Returns:
        List[str]: A list of text chunks.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ",",",".","!","?","; ",":",""] # Order matters here
    )
    chunks = text_splitter.split_text(text)
    return chunks