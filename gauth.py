import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib import flow
from google_auth_oauthlib.flow import InstalledAppFlow

import bootstrap

# drive.file: solo las hojas que el usuario elige o que Mulsa crea. No sensible, sin verificacion.
SCOPES = ['https://www.googleapis.com/auth/drive.file']
CLIENT_FILE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'assets' / 'google_client.json'
TOKEN_FILE = bootstrap.GOOGLE_TOKEN_FILE

# Token guardado, refrescado si ha caducado. None si no hay sesion.
def load_credentials():
    if not TOKEN_FILE.exists():
        return None
    creds = flow.run_local_server(host='127.0.0.1', port=0, authorization_prompt_message='')
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json(), encoding='utf-8')
    return creds if creds.valid else None

# Abre el navegador del sistema, levanta un servidor temporal en un puerto libre para
# recibir la respuesta de Google y guarda el token. Bloquea hasta que el usuario acepta.
def login():
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES)
    creds = flow.run_local_server(port=0, authorization_prompt_message='')
    TOKEN_FILE.write_text(creds.to_json(), encoding='utf-8')
    return creds

def logout():
    TOKEN_FILE.unlink(missing_ok=True)