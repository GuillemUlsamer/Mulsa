import os
import re
import hashlib
import shutil
import warnings
import datetime
import threading
import openpyxl
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings('ignore', message='.*Python version.*past its end of life.*')

import gspread
from gspread.urls import DRIVE_FILES_API_V3_URL, SPREADSHEET_URL
from google.oauth2.service_account import Credentials
import requests

import bootstrap
import log
import gauth
import discogs
from stop import check_stop
from tagging import sanitize_filename, clean_artist, clean_title, tag_file
from downloader import download_track

CREDENTIALS_FILE = bootstrap.CREDENTIALS_FILE

THREADS = 5

# Columns (0-indexed)
COL_ARTIST = 1
COL_TITLE = 2
COL_DURATION = 3
COL_CHECKBOX = 5  # Column F
COL_STATUS = 6    # Column G
COL_NOTES = 7     # Column H
COL_ALBUM = 8     # Column I
COL_YEAR = 9      # Column J
COL_COVER = 10    # Column K
COL_BACK = 11     # Column L (contraportada, solo en hojas importadas desde la app)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Origen de una playlist: de donde salen las filas y donde se escribe el estado.
# El pipeline solo usa volumes() y set_status(); cualquier origen con esos dos metodos vale.
class GoogleSource:
    def __init__(self, client, name):
        self.name = name
        self.sheet = client.open(name)
        self._ws = {}

    # Devuelve [(titulo_volumen, filas)], filas como listas de strings (lo que da get_all_values).
    # Una sola peticion (batchGet) para todos los volumenes en vez de una por pestana.
    def volumes(self):
        self._ws = {ws.title: ws for ws in self.sheet.worksheets()}
        titles = list(self._ws)
        res = self.sheet.values_batch_get([f"'{t}'" for t in titles])
        ranges = res.get('valueRanges', [])
        return [(t, (ranges[i].get('values', []) if i < len(ranges) else [])) for i, t in enumerate(titles)]

    def set_status(self, volume, row_num, text):
        self._ws[volume].update_cell(row_num, COL_STATUS + 1, text)

# Mismo contrato que GoogleSource, sobre una copia local en PLAYLISTS_DIR.
class XlsxSource:
    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.stem
        self.wb = openpyxl.load_workbook(self.path)
        self._lock = threading.Lock()

    def volumes(self):
        return [(ws.title, [[_cell_text(c) for c in row] for row in ws.iter_rows(values_only=True)])
                for ws in self.wb.worksheets]

    # openpyxl no escribe celdas sueltas: se cambia en memoria y se guarda el libro entero.
    def set_status(self, volume, row_num, text):
        with self._lock:
            self.wb[volume].cell(row_num, COL_STATUS + 1).value = text
            self.wb.save(self.path)

# Deja cada celda como la daria get_all_values(): texto, booleanos en mayusculas, horas como m:ss.
def _cell_text(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, datetime.time):
        return f"{value.hour * 60 + value.minute}:{value.second:02d}"
    if isinstance(value, datetime.timedelta):
        total = int(value.total_seconds())
        return f"{total // 60}:{total % 60:02d}"
    return str(value)

def import_xlsx(src_path):
    src_path = Path(src_path)
    bootstrap.PLAYLISTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = bootstrap.PLAYLISTS_DIR / src_path.name
    old_status = {}
    if dest.exists():
        old = openpyxl.load_workbook(dest, read_only=True)
        for ws in old.worksheets:
            for i, row in enumerate(ws.iter_rows(min_col=COL_STATUS + 1, max_col=COL_STATUS + 1, values_only=True), start=1):
                if row[0]:
                    old_status[(ws.title, i)] = row[0]
        old.close()
    shutil.copyfile(src_path, dest)
    if old_status:
        wb = openpyxl.load_workbook(dest)
        for (title, i), text in old_status.items():
            if title in wb.sheetnames:
                wb[title].cell(i, COL_STATUS + 1).value = text
        wb.save(dest)
    return dest.stem

def xlsx_path(name):
    p = bootstrap.PLAYLISTS_DIR / f"{name}.xlsx"
    return p if p.exists() else None

def list_xlsx_playlists():
    result = []
    for p in sorted(bootstrap.PLAYLISTS_DIR.glob('*.xlsx'), key=lambda p: p.stem.lower()):
        try:
            wb = openpyxl.load_workbook(p, read_only=True)
            row = next(wb.worksheets[0].iter_rows(min_row=2, max_row=2, max_col=3, values_only=True), ())
            volumes = sum(1 for n in wb.sheetnames if n != RELEASES_SHEET)
            wb.close()
        except Exception:
            row, volumes = (), 0
        year = _cell_text(row[1]) if len(row) > 1 else ''
        match = IMAGE_URL_RE.search(str(row[2]) if len(row) > 2 else '')
        result.append({'title': p.stem, 'id': None, 'image_url': match.group(1) if match else None, 'image': None, 'year': year, 'volumes': volumes, 'source': 'xlsx'})
    return result

def setup_gspread():
    creds = gauth.load_credentials()
    if creds:
        return gspread.authorize(creds)
    if not CREDENTIALS_FILE.exists():
        print(f"Error: {CREDENTIALS_FILE} not found.")
        return None
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)

IMAGE_URL_RE = re.compile(r'=IMAGE\(\s*"([^"]+)"', re.IGNORECASE)

COVER_CACHE_DIR = bootstrap.CACHE_DIR / 'covers'

# Dos peticiones: titulos de las pestanas (para contar volumenes) y A2:C2 de la primera
# (ano y formula de la portada). No se pueden juntar: con `ranges` la API solo devuelve las
# pestanas que tocan el rango. Devuelve (url_portada, ano, volumenes).
def _read_header(client, spreadsheet_id):
    meta = client.http_client.request('get', SPREADSHEET_URL % spreadsheet_id,
                                      params={'fields': 'sheets.properties.title'}).json()
    volumes = sum(1 for sh in meta.get('sheets', []) if sh['properties']['title'] != RELEASES_SHEET)
    data = client.http_client.values_get(spreadsheet_id, 'A2:C2', params={'valueRenderOption': 'FORMULA'})
    row = (data.get('values') or [[]])[0]
    year = row[1] if len(row) > 1 else ''
    match = IMAGE_URL_RE.search(row[2] if len(row) > 2 else '')
    return (match.group(1) if match else None), str(year), volumes

def fetch_image(url, timeout=10):
    COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = COVER_CACHE_DIR / (hashlib.sha1(url.encode()).hexdigest() + '.img')
    if cached.exists():
        return cached.read_bytes()
    r = requests.get(url, headers={'User-Agent': 'music-manager/2.0'}, timeout=timeout)
    r.raise_for_status()
    cached.write_bytes(r.content)
    return r.content

# gspread.list_spreadsheet_files no filtra la papelera: preguntamos a Drive directamente.
def _list_sheets(client):
    files = []
    params = {'q': "mimeType='application/vnd.google-apps.spreadsheet' and trashed = false",
              'fields': 'nextPageToken,files(id,name)', 'pageSize': 1000}
    while True:
        res = client.http_client.request('get', DRIVE_FILES_API_V3_URL, params=params).json()
        files.extend(res.get('files', []))
        if not res.get('nextPageToken'):
            return files
        params['pageToken'] = res['nextPageToken']

# Papelera de Drive, no borrado definitivo: se recupera durante 30 dias.
def trash_sheet(client, name):
    for f in _list_sheets(client):
        if f['name'] == name:
            client.http_client.request('patch', f"{DRIVE_FILES_API_V3_URL}/{f['id']}", json={'trashed': True})
            return True
    return False

# details=False: solo nombres (rapido); la portada, el ano y los volumenes se piden despues
# por playlist con playlist_header, para que la estanteria se vaya llenando segun llegan.
def list_playlists(with_images=True, workers=8, details=True):
    client = setup_gspread()
    if not client:
        return list_xlsx_playlists()
    files = sorted(_list_sheets(client), key=lambda f: f['name'].lower())
    playlists = [{'title': f['name'], 'id': f['id'], 'image_url': None, 'image': None, 'year': '', 'volumes': 0, 'source': 'google'} for f in files]
    if not details:
        return list_xlsx_playlists() + playlists

    def fill(p):
        try:
            p['image_url'], p['year'], p['volumes'] = _read_header(client, p['id'])
            if with_images and p['image_url']:
                p['image'] = fetch_image(p['image_url'])
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(fill, playlists))
    return list_xlsx_playlists() + playlists

# spreadsheet_id evita volver a listar Drive por cada playlist (la lista rapida ya lo dio).
def playlist_header(name, spreadsheet_id=None):
    if xlsx_path(name):
        for p in list_xlsx_playlists():
            if p['title'] == name:
                return p['image_url'], p['year'], p['volumes']
    client = setup_gspread()
    if not client:
        return None, '', 0
    if not spreadsheet_id:
        spreadsheet_id = next((f['id'] for f in _list_sheets(client) if f['name'] == name), None)
    return _read_header(client, spreadsheet_id) if spreadsheet_id else (None, '', 0)

# ---------- crear y rellenar playlists (lo que hacia playlistHelper.gs) ----------
# Formato (anchos, casillas, ocultar columnas...) no tiene atajo en gspread: va por
# batch_update, una lista de "requests" de la API de Sheets. Indices desde 0, fin exclusivo.
RELEASES_SHEET = 'Releases'
VOLUME_HEADERS = ['Track #', 'Artist', 'Title', 'Duration', 'Cumulative', 'Add to Playlist', 'Notes']
VOLUME_WIDTHS = [60, 300, 400, 80, 80, 100, 150]

def _col_width(ws, col, px):
    return {'updateDimensionProperties': {
        'range': {'sheetId': ws.id, 'dimension': 'COLUMNS', 'startIndex': col, 'endIndex': col + 1},
        'properties': {'pixelSize': px}, 'fields': 'pixelSize'}}

def _grid(ws, row0, row1, col0, col1):
    rng = {'sheetId': ws.id, 'startRowIndex': row0, 'startColumnIndex': col0, 'endColumnIndex': col1}
    if row1 is not None:
        rng['endRowIndex'] = row1
    return rng

def create_playlist(client, name, folder_id=None):
    return client.create(name, folder_id=folder_id or None)

# Pestana Releases la primera, con cabeceras y anchos. Se llama cada vez, como el script.
def _releases_sheet(spreadsheet):
    try:
        ws = spreadsheet.worksheet(RELEASES_SHEET)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(RELEASES_SHEET, rows=100, cols=26, index=0)
    ws.update(values=[['NAME OF THE ALBUM', 'YEAR', 'COVER']], range_name='A1:C1')
    spreadsheet.batch_update({'requests': [
        _col_width(ws, 0, 320), _col_width(ws, 1, 100), _col_width(ws, 2, 220),
        {'updateSheetProperties': {'properties': {'sheetId': ws.id, 'index': 0}, 'fields': 'index'}},
    ]})
    return ws

def setup_sheet(spreadsheet, vol_num):
    _releases_sheet(spreadsheet)
    requests = []
    for i in range(1, vol_num + 1):
        title = f'V {i}'
        try:
            ws = spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title, rows=200, cols=26)
        ws.batch_clear(['A:G'])
        ws.update(values=[VOLUME_HEADERS], range_name='A1:G1')
        ws.update(values=[['Album', 'Year', 'CoverURL']], range_name='I1:K1')
        requests += [_col_width(ws, c, w) for c, w in enumerate(VOLUME_WIDTHS)]
        # quitar casillas y formato de un setup anterior
        requests.append({'setDataValidation': {'range': _grid(ws, 1, None, 0, 7)}})
        requests.append({'repeatCell': {'range': _grid(ws, 1, None, 0, 11),
                                        'cell': {'userEnteredFormat': {}}, 'fields': 'userEnteredFormat'}})
        requests.append({'updateDimensionProperties': {
            'range': {'sheetId': ws.id, 'dimension': 'COLUMNS', 'startIndex': 7, 'endIndex': 11},
            'properties': {'hiddenByUser': True}, 'fields': 'hiddenByUser'}})
    # la pestana vacia que Google crea por defecto sobra
    for ws in spreadsheet.worksheets():
        if ws.title in ('Sheet1', 'Hoja 1') and len(spreadsheet.worksheets()) > 1:
            requests.append({'deleteSheet': {'sheetId': ws.id}})
    spreadsheet.batch_update({'requests': requests})

def import_release(spreadsheet, vol_title, release_id, token=''):
    ws = spreadsheet.worksheet(vol_title)
    ws.batch_clear(['A2:G'])
    data = discogs.release(release_id, token)
    album = data.get('title', '')
    year = data.get('year', '')
    images = data.get('images') or []
    cover = images[0].get('uri', '') if images else ''
    back = images[1].get('uri', '') if len(images) > 1 else ''
    ws.update(values=[[album, year, cover, back]], range_name='I1:L1')

    rows = []
    cumulative = 0
    counter = 1
    for track in data.get('tracklist', []):
        if track.get('type_') != 'track':
            continue
        seconds = parse_duration(track.get('duration') or '0:00')
        cumulative += seconds
        position = track.get('position') or f'{counter:02d}'
        counter += 1
        artists = track.get('artists') or data.get('artists') or []
        # Sheets guarda las horas como fraccion de dia; con formato [h]:mm:ss se ven como duracion
        rows.append([position, ' & '.join(a['name'] for a in artists), track.get('title', ''),
                     seconds / 86400, cumulative / 86400, False, ''])
    if rows:
        ws.update(values=rows, range_name=f'A2:G{len(rows) + 1}')
        spreadsheet.batch_update({'requests': [
            {'repeatCell': {'range': _grid(ws, 1, len(rows) + 1, 3, 5),
                            'cell': {'userEnteredFormat': {'numberFormat': {'type': 'TIME', 'pattern': '[h]:mm:ss'}}},
                            'fields': 'userEnteredFormat.numberFormat'}},
            # la "casilla" de Sheets es una validacion booleana con interfaz
            {'setDataValidation': {'range': _grid(ws, 1, len(rows) + 1, 5, 6),
                                   'rule': {'condition': {'type': 'BOOLEAN'}, 'strict': True, 'showCustomUi': True}}},
            {'repeatCell': {'range': _grid(ws, 1, len(rows) + 1, 0, 7),
                            'cell': {'userEnteredFormat': {'horizontalAlignment': 'LEFT'}},
                            'fields': 'userEnteredFormat.horizontalAlignment'}},
        ]})
    _append_release(spreadsheet, album, year, cover)
    log.line(f'{vol_title}: {album} · {len(rows)} tracks')
    return album

def _append_release(spreadsheet, album, year, cover):
    ws = _releases_sheet(spreadsheet)
    row = max(len(ws.get_all_values()) + 1, 2)
    formula = '=IMAGE("' + cover.replace('"', '""') + '")' if cover else ''
    # USER_ENTERED: que la formula se evalue en vez de guardarse como texto
    ws.update(values=[[album, year, formula]], range_name=f'A{row}:C{row}', value_input_option='USER_ENTERED')
    spreadsheet.batch_update({'requests': [{'updateDimensionProperties': {
        'range': {'sheetId': ws.id, 'dimension': 'ROWS', 'startIndex': row - 1, 'endIndex': row},
        'properties': {'pixelSize': 180}, 'fields': 'pixelSize'}}]})

def import_list(spreadsheet, list_id, token='', progress=log.line):
    data = discogs.list_items(list_id, token)
    items = [it for it in data.get('items', []) if it.get('type') == 'release']
    if not items:
        raise RuntimeError('The list has no releases.')
    setup_sheet(spreadsheet, len(items))
    for i, item in enumerate(items, start=1):
        progress(f'Importing release {i}/{len(items)}...')
        import_release(spreadsheet, f'V {i}', item['id'], token)

# Detalle de una playlist para la ficha: temas por volumen, marcadas, descargadas y
# contraportada. Lee todos los volumenes, asi que solo se pide para el disco seleccionado.
def playlist_info(source):
    volumes = []
    marked = downloaded = 0
    back = ''
    for vol_title, rows in source.volumes():
        if vol_title == RELEASES_SHEET:
            continue
        header = rows[0] if rows else []
        if not back and len(header) > COL_BACK:
            back = header[COL_BACK]
        tracks = []
        for row_num, row in enumerate(rows[1:], start=2):
            if len(row) <= COL_CHECKBOX or not (row[COL_ARTIST].strip() or row[COL_TITLE].strip()):
                continue
            is_marked = row[COL_CHECKBOX].lower() == 'true'
            status = row[COL_STATUS] if len(row) > COL_STATUS else ''
            marked += is_marked
            downloaded += is_marked and 'Downloaded' in status
            tracks.append({'n': row[0].strip(), 'row': row_num, 'artist': row[COL_ARTIST], 'title': row[COL_TITLE],
                           'marked': is_marked, 'status': status})
        album = header[COL_ALBUM] if len(header) > COL_ALBUM else ''
        volumes.append({'title': vol_title, 'album': album, 'tracks': tracks})
    return {'volumes': volumes, 'marked': marked, 'downloaded': downloaded, 'back_cover_url': back or None}

# para limpiar el formato de duración, que tenga sentido
def parse_duration(duration_val):
    if not duration_val: return 0
    try:
        parts = list(map(int, str(duration_val).strip().split(':')))
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2: return parts[0] * 60 + parts[1]
    except ValueError: pass
    return 0

def process_playlist(source, base_download_dir):
    spreadsheet_name = source.name

    # 1. Creo la carpeta de descargas si no existe
    if not os.path.exists(base_download_dir):
        os.makedirs(base_download_dir)
    review = []
    pool = ThreadPoolExecutor(max_workers=THREADS)
    jobs = []
    
    # 2. Por cada volumen de la playlist, miro las filas y veo cuales estan checkeadas para descargar o eliminar
    for vol_title, rows in source.volumes():
        vol_match = re.search(r'\d+', vol_title)
        album_name = f"{spreadsheet_name} {vol_match.group(0)}" if vol_match else spreadsheet_name
        header = rows[0] if rows else []
        album_year = header[COL_YEAR] if len(header) > 9 else ''      # J1
        cover_url = header[COL_COVER] if len(header) > 10 else ''     # K1
        cover_bytes = None
        if cover_url:
            try:
                cover_bytes = fetch_image(cover_url)
            except Exception as e:
                log.line(f"Cover not available: {e}", "error")
        album_hint = f"{spreadsheet_name} {vol_match.group(0)}" if vol_match else None

        # 2.1 Si no hay filas o solo hay una (header), salto esta hoja
        if len(rows) < 2: continue
        
        # 2.2 Por cada fila (excepto la primera que es el header), miro a ver que hago
        for i in range(1, len(rows)):
            check_stop()
            row = rows[i]
            row_num = i + 1
            
            # Miro si la fila tiene cancion (si no hay checkbox, no hay cancion, asi que la salto)
            if len(row) <= COL_CHECKBOX: continue
            
            artist = clean_artist(row[COL_ARTIST])
            title = clean_title(row[COL_TITLE])
            track_no = row[0].strip()
            duration_str = row[COL_DURATION]
            is_checked = row[COL_CHECKBOX].lower() == 'true'
            status = row[COL_STATUS] if len(row) > COL_STATUS else ""
            
            filename = f"{artist} - {title}"
            safe_filename = sanitize_filename(filename)
            
            file_path = os.path.join(base_download_dir, safe_filename)
            mp3_path = file_path + ".mp3"

            # Si esta checkeada y no esta descargada, la descargo
            if is_checked and "Downloaded" not in status:
                exp_seconds = parse_duration(duration_str)
                # Pongo el trabajo (descargar una cancion) en la cola del pool de threads
                jobs.append(pool.submit(download_row, source, vol_title, row_num, artist, title, file_path, exp_seconds, album_hint,
                                        album_name, album_year, track_no, cover_bytes, review))
                
            # Si no esta checkeada pero esta descargada, la borro
            elif not is_checked and "Downloaded" in status and "Deleting" not in status:
                log.song((vol_title, row_num), f"[{vol_title}] {filename}")
                if os.path.exists(mp3_path):
                    try:
                        os.remove(mp3_path)
                        log.status("Deleted", "done")
                    except Exception as e:
                        log.status(f"Del Error: {e}", "error")
                
                source.set_status(vol_title, row_num, "")

    # Espero a que terminen todos los trabajos
    try:
        for job in jobs:
            job.result()
    finally:
        pool.shutdown(wait=True, cancel_futures=True)

    if review:
        log.line(f"\nTo review ({len(review)}):", "failed")
        for item in review:
            log.line("  " + item)


def download_row(source, vol_title, row_num, artist, title, file_path, exp_seconds, album_hint,
                 album_name, album_year, track_no, cover_bytes, review):
    check_stop()
    filename = f"{artist} - {title}"
    log.song((vol_title, row_num), f"[{vol_title}] {filename}")
    source.set_status(vol_title, row_num, "Downloading...")

    try:
        final_path, note = download_track(artist, title, file_path, expected_duration_sec=exp_seconds, tolerance=60, album_hint=album_hint)
    except SystemExit:
        source.set_status(vol_title, row_num, "")
        raise

    # si ha funcionado, pongo los tags
    if final_path:
        tag_file(final_path, artist, title, album_name, album_year, track_no, cover_bytes)
        source.set_status(vol_title, row_num, f"Downloaded ({note})" if note else "Downloaded")
        log.status(f"Done ({note})" if note else "Done", "done")
        if note:
            review.append(f"{filename}: {note}")
    else:
        source.set_status(vol_title, row_num, "Failed, Do it manually")
        log.status("Failed", "failed")
        review.append(f"{filename}: failed")
        log.summary(f"goal:       {filename}\nFAILED\n")