"""API endpoints for document operations."""
import logfire
from fastapi import APIRouter, Depends, UploadFile
from fastapi.security import OAuth2PasswordBearer

from server.core.service.whatsapp_service.whatsapp_webhook_service import process_document

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@router.post("/add-document/{doc_title}")
async def add_document(
    file: UploadFile,
    doc_title: str,
    token: str = Depends(oauth2_scheme)
):
    """
    Endpoint to add a document to the database.

    Args:
        file: The uploaded file
        doc_title: Title for the document
        token: OAuth2 authentication token

    Returns:
        Document ID if successful, error message otherwise
    """
    try:
        contents = await file.read()
    except Exception as e:
        logfire.error(f"Failed to read file: {str(e)}")
        return {
            "status": "error",
            "message": "Failed to read file at endpoint /add-document"
        }

    doc_id = await process_document(contents, doc_title, token, uuid=None)
    return doc_id
