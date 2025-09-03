import asyncio
import datetime
import os

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.security import OAuth2PasswordBearer
from google.auth.exceptions import OAuthError
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel
from typing import Optional, List
from server.core.email_service.gmail_client import GmailClient
from server.core.email_service.supabase_client import add_returnable_request_to_db, add_action_to_db, add_mail_to_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter()

# Gmail Client initialisieren
CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "oauth_client_id.json")
gmail_client = GmailClient(CREDENTIALS_PATH)




# Pydantic Models
class SendMailRequest(BaseModel):
    to: str
    subject: str
    body: str
    is_return_request: Optional[bool] = False
    returnable_request_data : Optional[dict] = None

class EmailResponse(BaseModel):
    id: str
    subject: str
    sender: str
    date: str
    body: str

# Use a strong, unique secret key stored securely as an environment variable.
# This secret is ONLY for signing the temporary state token, not your main user JWTs.
STATE_SECRET_KEY = os.getenv("STATE_SECRET_KEY", "a_secure_random_string_for_development_only")
ALGORITHM = "HS256"
STATE_TOKEN_EXPIRE_MINUTES = 15  # The state token should be short-lived.

def create_state_token(jwt_token: str) -> str:
    """
    Creates a short-lived JWT to be used as the OAuth state parameter.
    This token securely encodes the user's primary JWT.
    """
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=STATE_TOKEN_EXPIRE_MINUTES)
    data_to_encode = {
        "user_jwt": jwt_token,
        "exp": expire
    }
    return jwt.encode(data_to_encode, STATE_SECRET_KEY, algorithm=ALGORITHM)

def validate_state_token(token: str) -> str:
    """
    Validates the state JWT and extracts the original user JWT from its payload.
    Raises HTTPException if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, STATE_SECRET_KEY, algorithms=[ALGORITHM])
        return payload["user_jwt"]
    except KeyError:
        raise HTTPException(status_code=400, detail="Malformed state token.")

def create_google_oauth_flow() -> Flow:
    """
    Creates and configures a new Google OAuth Flow instance from environment variables.
    This ensures each request gets a fresh, identical flow configuration.
    """
    # This configuration must match your credentials in Google Cloud Console.
    # Storing these as environment variables is highly recommended.
    client_config = {
        "web": {
            "client_id": os.getenv("GMAIL_CLIENT_ID"),
            "project_id": os.getenv("GMAIL_PROJECT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": os.getenv("GMAIL_CLIENT_SECRET"),
        }
    }
    scopes = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.send']
    flow = Flow.from_client_config(client_config, scopes=scopes)
    flow.redirect_uri = os.getenv("GMAIL_REDIRECT_URI", "http://localhost:8000/api/v1/email/authenticate/redirect")
    return flow


# ==============================================================================
#  REFACTORED API ENDPOINTS
# ==============================================================================

@router.post("/authenticate")
async def authenticate_start(token: str = Depends(oauth2_scheme)):
    """
    Starts the Google OAuth flow by generating a secure authorization URL.
    The user's identity is encoded into the 'state' parameter as a short-lived JWT.
    """
    # First, check if the user already has a valid refresh token.
    # This check should be implemented in your gmail_client.
    # if await gmail_client.is_user_authenticated(token):
    #     return {"message": "User is already authenticated", "status": "success"}

    try:
        # 1. Create a fresh flow object for this request.
        flow = create_google_oauth_flow()

        # 2. Create a secure, short-lived JWT to use as the state parameter.
        # This token contains the user's primary JWT, linking the callback to this user.
        state_jwt = create_state_token(jwt_token=token)

        # 3. Generate the authorization URL with the JWT as the state.
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            prompt='consent',  # Force prompt for refresh token every time
            state=state_jwt,
        )

        # 4. Return the URL to the frontend. No server-side state is stored.
        return {
            "auth_url": auth_url,
            "message": "Please complete authorization at the provided URL."
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Could not initiate authentication flow.")


@router.get("/authenticate/redirect")
async def authenticate_redirect(request: Request, state: str = Query(...), code: str = Query(...)):
    """
    Handles the OAuth redirect from Google in a stateless and secure manner.
    It validates the state token, exchanges the code for credentials, and saves the refresh token.
    """
    print("Callback received with state:", state)
    try:
        # 1. Validate the incoming 'state' parameter. If valid, it returns the user's
        #    original JWT, securely identifying who this callback belongs to.
        user_jwt = validate_state_token(state)
        print("User JWT from state token:", user_jwt)
        # 2. Create a fresh flow object, identical to the one in the start endpoint.
        flow = create_google_oauth_flow()
        print("Flow created with redirect URI:", flow.redirect_uri)
        # 3. Exchange the authorization code for tokens. This is a blocking network
        #    request, so we run it in a separate thread to avoid freezing the server.
        await asyncio.to_thread(flow.fetch_token, code=code)

        credentials = flow.credentials
        if not credentials or not credentials.refresh_token:
            raise HTTPException(status_code=400, detail="No refresh token received. Please ensure you are granting offline access.")

        # 4. Securely save the refresh token to your database, associated with the user.
        #    The `gmail_client` should handle the database logic. This call is now safe
        #    because `user_jwt` was securely retrieved from the validated state token.
        print("Saving to supabase")
        result = await asyncio.to_thread(gmail_client.save_refresh_token_to_supabase, jwt_token=user_jwt, refresh_token=credentials.refresh_token)
        if result != 200:
             raise HTTPException(status_code=500, detail="Failed to save authorization credentials.")

        return {
            "message": "Gmail authentication successful",
            "status": "success"
        }
    except OAuthError as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {e}")
    except HTTPException as e:
        # Re-raise known HTTP exceptions from our validation logic
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal server error occurred during authentication. {e} ")


@router.post("/send-mail")
async def send_mail(mail_request: SendMailRequest, token: str = Depends(oauth2_scheme)):
    """Sendet eine E-Mail über Gmail"""
    try:
        # Authentifizierung prüfen
        flow = gmail_client.authenticate(token)
        if flow is not None:
            raise HTTPException(
                status_code=401,
                detail="Gmail not authenticated. Please authenticate first."
            )

        if os.getenv("DEBUG", "false").lower() == "true":
            # set the to a test adress
            mail_request.to = os.getenv("TEST_EMAIL_ADDRESS", "Not set :/")
            print("DEBUG mode is on. Overriding recipient to:", mail_request.to)

        message_id = gmail_client.send_mail(
            jwt_token=token,
            service_client=None,
            uuid=None,
            to=mail_request.to,
            subject=mail_request.subject,
            body=mail_request.body
        )


        # if is_return_request is True then we add a returnable request to the database
        if mail_request.is_return_request and not mail_request.returnable_request_data:
            raise HTTPException(status_code=400, detail="Returnable request data is required when is_return_request is True")

        if mail_request.is_return_request and mail_request.returnable_request_data:
            try:
                data, action = add_returnable_request_to_db(
                    jwt_token=token,
                    request_data=mail_request.returnable_request_data
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to add returnable request to database: {str(e)}")

            try:
                add_action_to_db(token, action)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to add action request to database: {str(e)}")
                # we don't raise an error here because the main action (sending the mail and adding the request) was successful

            try:
                mail_data = {
                    "subject": mail_request.subject,
                    "sender": mail_request.to,
                    "body": mail_request.body,
                }
                add_mail_to_db(jwt_token=token, service_client=None, mail_data=mail_data, returnable_id=data.get("id"), send_by_me =True)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to add mail to database: {str(e)}")
                # we don't raise an error here because the main action (sending the mail and adding the request) was successful

        if message_id:
            return {
                "message": "Email sent successfully",
                "message_id": message_id,
                "status": "success"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send email")

    except HTTPException as e:
        print(e)
        raise HTTPException(status_code=500, detail="Failed to send email")
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
        flow = gmail_client.authenticate(token, None,None)
        if flow is not None:
            raise HTTPException(
                status_code=401,
                detail="Gmail not authenticated. Please authenticate first."
            )
        print("Fetching emails with max_results =", max_results)

        emails = gmail_client.read_new_mails(
            jwt_token=token,
            max_results=max_results
        )
        print("Got emails:", len(emails))

        return [EmailResponse(**email) for email in emails]

    except HTTPException as e:
        raise HTTPException(status_code=401, detail="Gmail not authenticated. Please authenticate first. Got HTTPException " + str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Get mails error: {str(e)}")
