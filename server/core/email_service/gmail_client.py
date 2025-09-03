import os
import base64
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from cryptography.fernet import Fernet
from supabase import Client


from .supabase_client import get_supabase_client, TOKEN_TABLE_NAME

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.send']

class GmailClient:

    def __init__(self, path_to_credentials: str):
        pwd = os.path.dirname(os.path.abspath(__file__))
        path_to_credentials = os.path.join(pwd, path_to_credentials)
        self.credentials_path = path_to_credentials
        self.service = None
        # Lade Verschlüsselungsschlüssel aus Umgebungsvariablen
        encryption_key = os.getenv('GMAIL_TOKEN_ENCRYPTION_KEY')
        if not encryption_key:
            raise ValueError("GMAIL_TOKEN_ENCRYPTION_KEY Umgebungsvariable nicht gesetzt")
        self.cipher_suite = Fernet(encryption_key.encode())

    def _encrypt_token(self, token: str) -> str:
        """Verschlüsselt den Token"""
        return self.cipher_suite.encrypt(token.encode()).decode()

    def _decrypt_token(self, encrypted_token: str) -> str:
        """Entschlüsselt den Token"""
        return self.cipher_suite.decrypt(encrypted_token.encode()).decode()

    def authenticate(self, jwt_token: str | None, service_client: Client | None, uuid: str | None) -> bool or None:
        """Authentifizierung mit Google API und Supabase. If the user wants to authenticate, returns the OAuth flow to be handled externally."""
        creds = None

        # Versuche Refresh Token aus Supabase zu laden
        refresh_token = self.get_refresh_token_from_supabase(jwt_token, service_client, uuid)

        if refresh_token:
            # Erstelle Credentials aus Refresh Token
            with open(self.credentials_path, 'r') as f:
                client_config = json.load(f)

            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id= os.getenv("GMAIL_CLIENT_ID"),
                client_secret=os.getenv("GMAIL_CLIENT_SECRET"),
                scopes=SCOPES,

            )
            print("Erstellte Credentials aus gespeichertem Refresh Token")

        try:
            print("Attempting to refresh the access token...")
            creds.refresh(Request())
            print("Access token refreshed successfully.")
            self.service = build('gmail', 'v1', credentials=creds)
            print("Google API service created successfully.")
            return None
        except Exception as e:
            print(f"Error: The refresh token may be invalid or revoked. {e}")
            # This is where you would typically trigger a re-authentication flow
            # for the user.
            return False

    def save_refresh_token_to_supabase(self, jwt_token: str, refresh_token: str) -> int or None:
        """Speichert verschlüsselten Refresh Token in Supabase"""
        try:
            encrypted_token = self._encrypt_token(refresh_token)
            # Upsert: Update falls vorhanden, sonst Insert

            supabase = get_supabase_client(jwt_token)

            uid = supabase.auth.get_user(jwt_token).user.id
            print(f"Speichere Refresh Token für User ID: {uid}")

            # update the refresh token or insert if not exists
            result = supabase.from_(TOKEN_TABLE_NAME).upsert({
                'user_id': uid,
                'provider': 'google',
                'token': encrypted_token
            }, on_conflict='user_id').execute()

            result.raise_when_api_error(result)


            print("Refresh Token erfolgreich gespeichert")
            return 200

        except Exception as e:
            print(f"Fehler beim Speichern des Refresh Tokens: {e}")
            return 503

    def get_refresh_token_from_supabase(self, jwt_token: str | None, service_client: Client | None, uuid: str | None) -> str:
        """Lädt und entschlüsselt Refresh Token aus Supabase"""
        assert jwt_token or (service_client and uuid), "Entweder jwt_token oder service_client und uuid müssen gesetzt sein"
        try:
            if jwt_token:
                supabase = get_supabase_client(jwt_token)
                uid = supabase.auth.get_user(jwt_token).user.id
            else:
                supabase = service_client
                uid = uuid

            result = supabase.from_(TOKEN_TABLE_NAME).select('token').eq('user_id', uid).eq('provider', 'google').execute()

            if result.data and len(result.data) > 0:
                encrypted_token = result.data[0]['token']
                print("Refresh Token erfolgreich geladen für User ID:", uid)
                return self._decrypt_token(encrypted_token)
        except Exception as e:
            print(f"Fehler beim Laden des Refresh Tokens: {e}")
        return None

    def read_new_mails(self, jwt_token: str | None, service_client: Client | None, uuid: str | None, max_results: int = 10) -> list[dict]:
        """Liest neue E-Mails"""
        if not self.service:
            self.authenticate(jwt_token, service_client, uuid)

        try:
            # Hole ungelesene E-Mails
            results = self.service.users().messages().list(
                userId='me',
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            emails = []

            for message in messages:
                msg = self.service.users().messages().get(
                    userId='me',
                    id=message['id']
                ).execute()

                # Parse E-Mail Details
                payload = msg['payload']
                headers = payload.get('headers', [])

                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), '')

                # E-Mail Body extrahieren
                body = self._extract_body(payload)

                emails.append({
                    'id': message['id'],
                    'subject': subject,
                    'sender': sender,
                    'date': date,
                    'body': body
                })

            return emails

        except Exception as e:
            print(f"Fehler beim Lesen der E-Mails: {e}")
            return []


    def _extract_body(self, payload):
        """
        Extrahiert den E-Mail-Body aus der Payload.
        Durchsucht rekursiv alle Teile der Nachricht, um den Text- oder HTML-Inhalt zu finden.
        Bevorzugt 'text/plain', greift aber auf 'text/html' zurück, falls ersteres nicht vorhanden ist.

        (EN: Extracts the email body from the payload.
         Recursively searches all parts of the message to find the text or HTML content.
         Prefers 'text/plain' but falls back to 'text/html' if the former is not available.)
        """
        text_body = ""
        html_body = ""

        # Use a queue for a breadth-first search of the payload parts
        parts_to_process = [payload]

        while parts_to_process:
            part = parts_to_process.pop(0)
            mime_type = part.get('mimeType')

            # --- Case 1: The part contains the actual body data ---
            # Check for 'data' in the 'body' object
            if 'data' in part.get('body', {}):
                body_data = part['body']['data']

                if mime_type == 'text/plain':
                    # We found a plain text part. Decode it and we can consider our job done
                    # because we prefer plain text.
                    decoded_data = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    text_body = decoded_data
                    # We can break here because plain text is our first priority.
                    break

                elif mime_type == 'text/html':
                    # We found an HTML part. Decode it and store it.
                    # We'll continue searching in case a plain text part exists.
                    decoded_data = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    html_body = decoded_data

            # --- Case 2: The part is a container for more parts ---
            # If the part has sub-parts, add them to our queue to be processed.
            if 'parts' in part:
                parts_to_process.extend(part['parts'])

        # Return the plain text body if we found it, otherwise return the HTML body.
        return text_body if text_body else html_body

    def send_mail(self, jwt_token: str, service_client: Client| None, uuid: str | None, to: str, subject: str, body: str):
        """Sendet eine E-Mail"""
        if not self.service:
            self.authenticate(jwt_token, service_client, uuid)

        try:
            message = MIMEMultipart()
            message['to'] = to
            message['subject'] = subject

            message.attach(MIMEText(body, 'plain'))

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            send_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()

            return send_message['id']

        except Exception as e:
            print(f"Fehler beim Senden der E-Mail: {e}")
            return None
