import os
import base64
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from cryptography.fernet import Fernet
from .supabase_client import get_supabase_client, TOKEN_TABLE_NAME

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.send']

class GmailClient:

    def __init__(self, path_to_credentials: str):
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

    def _authenticate(self, jwt_token: str) -> InstalledAppFlow or None:
        """Authentifizierung mit Google API und Supabase. If the user wants to authenticate, returns the OAuth flow to be handled externally."""
        creds = None

        # Versuche Refresh Token aus Supabase zu laden
        refresh_token = self.get_refresh_token_from_supabase(jwt_token)

        if refresh_token:
            # Erstelle Credentials aus Refresh Token
            with open(self.credentials_path, 'r') as f:
                client_config = json.load(f)

            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri=client_config['installed']['token_uri'],
                client_id=client_config['installed']['client_id'],
                client_secret=client_config['installed']['client_secret']
            )

        # Wenn keine gültigen Credentials, führe OAuth Flow durch
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Speichere neuen Refresh Token
                if creds.refresh_token:
                    self.save_refresh_token_to_supabase(jwt_token, creds.refresh_token)

                self.service = build('gmail', 'v1', credentials=creds)
                return None


            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)

                return flow
        return None

    def save_refresh_token_to_supabase(self, jwt_token: str, refresh_token: str) -> int or None:
        """Speichert verschlüsselten Refresh Token in Supabase"""
        try:
            encrypted_token = self._encrypt_token(refresh_token)
            # Upsert: Update falls vorhanden, sonst Insert

            supabase = get_supabase_client(jwt_token)

            uid = supabase.auth.get_user().user.id

            # update the refresh token or insert if not exists
            result = supabase.from_(TOKEN_TABLE_NAME).upsert({
                'user_id': uid,
                'provider': 'google',
                'token': encrypted_token
            }, on_conflict='user_id').execute()

            if result.error:
                print(f"Fehler beim Speichern des Refresh Tokens: {result.error.message}")
                return None
            else:
                print("Refresh Token erfolgreich gespeichert")
                return 200

        except Exception as e:
            print(f"Fehler beim Speichern des Refresh Tokens: {e}")
            return 503

    def get_refresh_token_from_supabase(self, jwt_token: str) -> str:
        """Lädt und entschlüsselt Refresh Token aus Supabase"""
        try:
            supabase = get_supabase_client(jwt_token)

            uid = supabase.auth.get_user().user.id

            result = supabase.from_(TOKEN_TABLE_NAME).select('token').eq('user_id', uid).eq('provider', 'google').execute()

            if result.data and len(result.data) > 0:
                encrypted_token = result.data[0]['token']
                return self._decrypt_token(encrypted_token)
        except Exception as e:
            print(f"Fehler beim Laden des Refresh Tokens: {e}")
        return None

    def read_new_mails(self, jwt_token: str, max_results: int = 10):
        """Liest neue E-Mails"""
        if not self.service:
            self._authenticate(jwt_token)

        try:
            # Hole ungelesene E-Mails
            results = self.service.users().messages().list(
                userId='me',
                q='is:unread',
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
        """Extrahiert E-Mail Body aus Payload"""
        body = ""

        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body']['data']
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                    break
        elif payload['mimeType'] == 'text/plain':
            data = payload['body']['data']
            body = base64.urlsafe_b64decode(data).decode('utf-8')

        return body

    def send_mail(self, jwt_token: str, to: str, subject: str, body: str):
        """Sendet eine E-Mail"""
        if not self.service:
            self._authenticate(jwt_token)

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
