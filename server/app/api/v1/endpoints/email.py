import os
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional, List
from server.core.email_service.gmail_client import GmailClient

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter(prefix="/gmail", tags=["gmail"])

# Gmail Client initialisieren
CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
gmail_client = GmailClient(CREDENTIALS_PATH)

# Pydantic Models
class SendMailRequest(BaseModel):
    to: str
    subject: str
    body: str

class EmailResponse(BaseModel):
    id: str
    subject: str
    sender: str
    date: str
    body: str

# Temporary storage for OAuth state (in production use Redis/database)
oauth_flows = {}

@router.get("/authenticate")
async def authenticate(token: str = Depends(oauth2_scheme)):
    """Startet Gmail OAuth-Authentifizierung"""
    try:
        flow = gmail_client._authenticate(token)

        if flow is None:
            return {"message": "Already authenticated", "status": "success"}

        # Konfiguriere Redirect URI
        flow.redirect_uri = os.getenv("GMAIL_REDIRECT_URI", "http://localhost:8000/api/v1/gmail/authenticate/redirect")

        # Generiere Authorization URL
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )

        # Speichere Flow für späteren Abruf
        oauth_flows[state] = {'flow': flow, 'jwt_token': token}

        return {
            "auth_url": auth_url,
            "state": state,
            "message": "Please complete authorization at the provided URL"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")

@router.get("/authenticate/redirect")
async def authenticate_redirect(request: Request, state: str = Query(...), code: str = Query(...)):
    """Behandelt OAuth-Redirect von Google"""
    try:
        if state not in oauth_flows:
            raise HTTPException(status_code=400, detail="Invalid state parameter")

        flow_data = oauth_flows[state]
        flow = flow_data['flow']
        jwt_token = flow_data['jwt_token']

        # Tausche Authorization Code gegen Tokens
        flow.fetch_token(code=code)

        # Speichere Refresh Token
        if flow.credentials.refresh_token:
            result = gmail_client.save_refresh_token_to_supabase(jwt_token, flow.credentials.refresh_token)
            if result != 200:
                raise HTTPException(status_code=500, detail="Failed to save refresh token")

        # Setze Service für zukünftige Requests
        gmail_client.service = gmail_client.service or flow.credentials

        # Cleanup
        del oauth_flows[state]

        return {
            "message": "Gmail authentication successful",
            "status": "success"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redirect error: {str(e)}")

@router.post("/send-mail")
async def send_mail(mail_request: SendMailRequest, token: str = Depends(oauth2_scheme)):
    """Sendet eine E-Mail über Gmail"""
    try:
        # Authentifizierung prüfen
        flow = gmail_client._authenticate(token)
        if flow is not None:
            raise HTTPException(
                status_code=401,
                detail="Gmail not authenticated. Please authenticate first."
            )

        message_id = gmail_client.send_mail(
            jwt_token=token,
            to=mail_request.to,
            subject=mail_request.subject,
            body=mail_request.body
        )

        if message_id:
            return {
                "message": "Email sent successfully",
                "message_id": message_id,
                "status": "success"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send email")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Send mail error: {str(e)}")

@router.get("/get-newest-mails", response_model=List[EmailResponse])
async def get_newest_mails(
    token: str = Depends(oauth2_scheme),
    max_results: int = Query(10, ge=1, le=50, description="Maximum number of emails to retrieve")
):
    """Ruft die neuesten ungelesenen E-Mails ab"""
    try:
        # Authentifizierung prüfen
        flow = gmail_client._authenticate(token)
        if flow is not None:
            raise HTTPException(
                status_code=401,
                detail="Gmail not authenticated. Please authenticate first."
            )

        emails = gmail_client.read_new_mails(
            jwt_token=token,
            max_results=max_results
        )

        return [EmailResponse(**email) for email in emails]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Get mails error: {str(e)}")
