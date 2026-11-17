import json
import sys
from pathlib import Path

import requests

API = 'https://api.discogs.com'
# Discogs rechaza peticiones sin User-Agent identificable.
USER_AGENT = 'Mulsa/3.0 +https://github.com/GuillemUlsamer/Mulsa'
# Claves de Mulsa como aplicacion (Consumer Key/Secret). Fuera de git; el build de la release
# las crea a partir de un secreto de GitHub.
CLIENT_FILE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'assets' / 'discogs_client.json'

def _app_auth():
    if not CLIENT_FILE.exists():
        return None
    c = json.loads(CLIENT_FILE.read_text(encoding='utf-8'))
    return f"Discogs key={c['key']}, secret={c['secret']}"

# Con token del usuario se usa su limite de peticiones; con las claves de la app, el de Mulsa
# (60/min compartido); sin nada, la API responde igual pero no devuelve imagenes (portadas).
def _get(path, token=''):
    headers = {'User-Agent': USER_AGENT}
    auth = f'Discogs token={token}' if token else _app_auth()
    if auth:
        headers['Authorization'] = auth
    r = requests.get(API + path, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()

def release(release_id, token=''):
    return _get(f'/releases/{release_id}', token)

def list_items(list_id, token=''):
    return _get(f'/lists/{list_id}', token)
