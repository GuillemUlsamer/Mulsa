import json
import queue
import threading
import sys
import webbrowser

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, Response
from pathlib import Path

import bootstrap
import log
import gauth
import manager
import sheets
import webview
import gspread

api = FastAPI(title="Mulsa")
_covers = {}  # diccionario de portadas de playlists, para que no se pidan cada vez
_backs = {}   # contraportadas, rellenado al pedir la ficha de una playlist

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
WEB_DIR = BASE_DIR / 'web' / 'dist' / 'web' / 'browser'

app = FastAPI()
app.mount("/api", api)
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

window = None  # se setea desde main.py

# ---------- eventos (SSE) ----------
# Cada navegador conectado a /events tiene su propia cola. El handler de log.py mete
# cada evento en todas las colas; el endpoint /events saca de la suya y lo escribe.
_clients = []
_clients_lock = threading.Lock()

def _log_handler(kind, song_id, text, tag):
    event = {"kind": kind, "song_id": song_id, "text": text, "tag": tag}
    with _clients_lock:
        for q in _clients:
            q.put(event)

log.set_handler(_log_handler)
log.open_file(bootstrap.APP_DIR / 'mulsa.log')

@api.get("/events")
def events():
    q = queue.Queue()
    with _clients_lock:
        _clients.append(q)

    # Un generador: cada "yield" es un trozo de la respuesta. La peticion no termina
    # hasta que el cliente cierra; mientras, bloquea en q.get() esperando eventos.
    def stream():
        try:
            while True:
                try:
                    event = q.get(timeout=15)
                except queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            with _clients_lock:
                _clients.remove(q)

    return StreamingResponse(stream(), media_type="text/event-stream")

# ---------- playlists ----------
# Ejemplo completo: de aqui copias el patron para el resto.
# with_images=False porque la imagen va por su propio endpoint (abajo); asi la lista
# responde rapido y Angular pide cada portada por separado con <img src=...>.
@api.get("/playlists")
def playlists():
    result = sheets.list_playlists(with_images=False)
    _covers.update({p["title"]: p["image_url"] for p in result})
    return [{"name": p["title"], "cover_url": p["image_url"], "year": p["year"], "volumes": p["volumes"], "source": p["source"]} for p in result]

# busca la playlist por su nombre y devuelve la portada
@api.get("/playlists/{name}/cover")
def playlist_cover(name: str):
    url = _covers.get(name)
    if not url:
        raise HTTPException(404, "playlist has no cover")
    return Response(content=sheets.fetch_image(url), media_type="image/jpeg")

# Ficha de una playlist (disco seleccionado): temas, contadores y contraportada.
@api.get("/playlists/{name}/info")
def playlist_info(name: str):
    path = sheets.xlsx_path(name)
    try:
        source = sheets.XlsxSource(path) if path else sheets.GoogleSource(_client(), name)
    except gspread.exceptions.SpreadsheetNotFound:
        raise HTTPException(404, f"Playlist '{name}' not found.")
    info = sheets.playlist_info(source)
    _backs[name] = info.pop("back_cover_url")
    info["back_cover"] = bool(_backs[name])
    return info

@api.get("/playlists/{name}/back-cover")
def playlist_back_cover(name: str):
    url = _backs.get(name)
    if not url:
        raise HTTPException(404, "playlist has no back cover")
    return Response(content=sheets.fetch_image(url), media_type="image/jpeg")

def _client():
    client = sheets.setup_gspread()
    if not client:
        raise HTTPException(400, "Sign in with Google first.")
    return client

# ---------- ejecucion ----------
_run_thread = None

@api.post("/run/{name}")
def run(name: str):
    global _run_thread
    if _run_thread and _run_thread.is_alive():
        raise HTTPException(409, "already running")
    _run_thread = threading.Thread(target=manager.run_manager, args=(name,), daemon=True)
    _run_thread.start()
    return {"status": "started"}

@api.post("/stop")
def stop():
    manager.stop_manager()
    return {"status": "stopping"}

@api.get("/status")
def status():
    return {"running": bool(_run_thread and _run_thread.is_alive())}

@api.get("/log")
def full_log():
    detailed = (bootstrap.APP_DIR / 'mulsa.log').read_text(encoding='utf-8')
    return Response(content=log.summary_text() + "\n\n----- detailed -----\n" + detailed, media_type="text/plain")

# ---------- settings ----------
# get de los settings
@api.get("/settings")
def get_settings():
    configured = bootstrap.is_configured()
    if bootstrap.CONFIG_FILE.exists():
        config = bootstrap.load_config() 
    else:
        config = {}
        
    soulseek_username = config.get("soulseek_username", "")
    music_dir = config.get("music_dir", str(bootstrap.DEFAULT_MUSIC_DIR))
    share_dir = config.get("share_dir", "")
    listen_port = config.get("listen_port", bootstrap.LISTEN_PORT)
    # discogs_token = config.get("discogs_token", "")
    credentials_file = str(bootstrap.CREDENTIALS_FILE)
    drive_folder = config.get("drive_folder_name", "")
    return {
        "configured": configured,
        "soulseek_username": soulseek_username,
        "music_dir": music_dir,
        "share_dir": share_dir,
        "listen_port": listen_port,
        "credentials_file": credentials_file,
        "drive_folder": drive_folder
        # "discogs_token": discogs_token
    }

@api.get("/auth/google")
def google_status():
    return {"connected": gauth.load_credentials() is not None}

@api.get("/auth/google/picker")
def google_picker():
    creds = gauth.load_credentials()
    return {"token": creds.token if creds else None, "api_key": gauth.PICKER_API_KEY, "app_id": gauth.PROJECT_NUMBER}

# El selector de Google se abre en el navegador del sistema (ver web/public/picker.html).
@api.post("/picker/open")
def picker_open(body: dict):
    webbrowser.open(body["origin"] + "/picker.html")
    return {"status": "opened"}

# Un enlace normal navegaria la ventana de Mulsa fuera de la app: las hojas se abren en el navegador.
@api.post("/open-url")
def open_url(body: dict):
    url = body.get("url", "")
    if not url.startswith("https://docs.google.com/"):
        raise HTTPException(400, "only Google Docs links")
    webbrowser.open(url)
    return {"status": "opened"}

# Recibe lo elegido en el selector. Las hojas quedan autorizadas en Google al elegirlas.
# Una carpeta no da acceso a su contenido (limite de drive.file): solo se guarda como destino
# donde Mulsa creara las playlists nuevas.
@api.post("/playlists/google")
def add_google_playlists(body: dict):
    files = body.get("files", [])
    folders = body.get("folders", [])
    parts = []
    if files:
        parts.append(f"{len(files)} sheets added")
    if folders:
        if bootstrap.CONFIG_FILE.exists():
            config = bootstrap.load_config()
            config["drive_folder_id"] = folders[0]["id"]
            config["drive_folder_name"] = folders[0]["name"]
            with open(bootstrap.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        parts.append("folder saved for new playlists")
    message = "Google playlists: " + (", ".join(parts) or "nothing selected") + "."
    log.line(message, "done")
    return {"message": message}

@api.post("/auth/google")
def google_login():
    def work():
        try:
            gauth.login()
            log.line("Google account connected.", "done")
        except Exception as e:
            log.line(f"Google login failed: {e}", "error")
    threading.Thread(target=work, daemon=True).start()
    return {"status": "started"}

@api.delete("/auth/google")
def google_logout():
    gauth.logout()
    return {"status": "ok"}

# post de los settings
@api.post("/settings")
def save_settings(body: dict):
    # saco los datos del body
    user = body.get("soulseek_username", "").strip()
    pwd = body.get("soulseek_password", "")
    music = body.get("music_dir", "").strip()
    share = body.get("share_dir", "").strip() or None
    port = str(body.get("listen_port", bootstrap.LISTEN_PORT)).strip()
    creds = body.get("credentials_file", str(bootstrap.CREDENTIALS_FILE)).strip()
    # discogs_token = body.get("discogs_token", "").strip()

    if not pwd:
        pwd = bootstrap.read_soulseek_password() or ""
    if not user or not pwd:
        raise HTTPException(400, "Soulseek username and password are required.")
    if not music:
        raise HTTPException(400, "Choose a music folder.")
    try:
        port_num = int(port)
        if not port.isdigit() or port_num < 1 or port_num > 65535:
            raise ValueError()
    except ValueError:
        raise HTTPException(400, "The listen port must be a number between 1 and 65535")
    def work():
        try: 
            bootstrap.run_setup(
                username=user,
                password=pwd,
                music_dir=music,
                share_dir=share,
                credentials_file=creds or None,
                progress=log.line,
                listen_port=port_num,
                # discogs_token=discogs_token,
            )
        except Exception as e:
            log.line(f"Error during setup: {e}", "error")

    threading.Thread(target=work, daemon=True).start()
    return {"status": "started"}

@api.post("/pick-folder")
def pick_folder():
    if window is None:
        raise HTTPException(501, "no native window")
    result = window.create_file_dialog(webview.FOLDER_DIALOG)
    return {"path": result[0] if result else None}

@api.post("/pick-file")
def pick_file(types: str = "JSON (*.json)"):
    if window is None:
        raise HTTPException(501, "no native window")
    result = window.create_file_dialog(webview.OPEN_DIALOG, file_types=(types,))
    return {"path": result[0] if result else None}

@api.post("/playlists/import")
def import_playlist():
    if window is None:
        raise HTTPException(501, "no native window")
    result = window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Excel (*.xlsx)",))
    if not result:
        return {"name": None}
    return {"name": sheets.import_xlsx(result[0])}

# ---------- crear y rellenar playlists de Google ----------
def _config():
    return bootstrap.load_config() if bootstrap.CONFIG_FILE.exists() else {}

def _open_playlist(name):
    client = sheets.setup_gspread()
    if not client:
        raise HTTPException(400, "Sign in with Google first.")
    try:
        return client.open(name)
    except gspread.exceptions.SpreadsheetNotFound:
        raise HTTPException(404, f"Playlist '{name}' not found in Google.")

# Los imports hablan con Discogs y Google durante un rato: van en hilo y avisan por el log.
def _background(fn, done_msg):
    def work():
        try:
            fn()
            log.line(done_msg, "done")
        except Exception as e:
            log.line(f"Import failed: {e}", "error")
    threading.Thread(target=work, daemon=True).start()
    return {"status": "started"}

@api.delete("/playlists/{name}")
def delete_playlist(name: str):
    path = sheets.xlsx_path(name)
    if path:
        path.unlink()
        return {"status": "deleted"}
    client = sheets.setup_gspread()
    if not client or not sheets.trash_sheet(client, name):
        raise HTTPException(404, f"Playlist '{name}' not found.")
    return {"status": "trashed"}

@api.get("/playlists/{name}/volumes")
def playlist_volumes(name: str):
    spreadsheet = _open_playlist(name)
    return {"url": spreadsheet.url,
            "volumes": [ws.title for ws in spreadsheet.worksheets() if ws.title != sheets.RELEASES_SHEET]}

@api.post("/playlists/new")
def new_playlist(body: dict):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Name is required.")
    client = sheets.setup_gspread()
    if not client:
        raise HTTPException(400, "Sign in with Google first.")
    spreadsheet = sheets.create_playlist(client, name, _config().get("drive_folder_id"))
    sheets.setup_sheet(spreadsheet, int(body.get("volumes", 1)))
    return {"name": name}

@api.post("/playlists/{name}/setup")
def setup_playlist(name: str, body: dict):
    sheets.setup_sheet(_open_playlist(name), int(body.get("volumes", 1)))
    return {"status": "ok"}

@api.post("/playlists/{name}/import-list")
def import_list(name: str, body: dict):
    spreadsheet = _open_playlist(name)
    token = _config().get("discogs_token", "")
    return _background(lambda: sheets.import_list(spreadsheet, body["list_id"], token), "Import finished.")

@api.post("/playlists/{name}/import-release")
def import_release(name: str, body: dict):
    spreadsheet = _open_playlist(name)
    token = _config().get("discogs_token", "")
    return _background(lambda: sheets.import_release(spreadsheet, body["volume"], body["release_id"], token), "Import finished.")
