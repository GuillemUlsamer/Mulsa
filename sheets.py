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
from google.oauth2.service_account import Credentials
import requests

import bootstrap
import log
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
COL_YEAR = 9      # Column J
COL_COVER = 10    # Column K

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
    def volumes(self):
        self._ws = {ws.title: ws for ws in self.sheet.worksheets()}
        return [(title, ws.get_all_values()) for title, ws in self._ws.items()]

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
            wb.close()
        except Exception:
            row = ()
        year = _cell_text(row[1]) if len(row) > 1 else ''
        match = IMAGE_URL_RE.search(str(row[2]) if len(row) > 2 else '')
        result.append({'title': p.stem, 'id': None, 'image_url': match.group(1) if match else None, 'image': None, 'year': year, 'source': 'xlsx'})
    return result

def setup_gspread():
    if not CREDENTIALS_FILE.exists():
        print(f"Error: {CREDENTIALS_FILE} not found.")
        return None
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)

IMAGE_URL_RE = re.compile(r'=IMAGE\(\s*"([^"]+)"', re.IGNORECASE)

COVER_CACHE_DIR = bootstrap.CACHE_DIR / 'covers'

def _read_header(client, spreadsheet_id):
    params = {'valueRenderOption': 'FORMULA'}
    try:
        data = client.http_client.values_get(spreadsheet_id, 'A2:C2', params=params)
    except AttributeError:
        data = client.open_by_key(spreadsheet_id).values_get('A2:C2', params=params)
    row = (data.get('values') or [[]])[0]
    year = row[1] if len(row) > 1 else ''
    match = IMAGE_URL_RE.search(row[2] if len(row) > 2 else '')
    return (match.group(1) if match else None), str(year)

def fetch_image(url, timeout=10):
    COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = COVER_CACHE_DIR / (hashlib.sha1(url.encode()).hexdigest() + '.img')
    if cached.exists():
        return cached.read_bytes()
    r = requests.get(url, headers={'User-Agent': 'music-manager/2.0'}, timeout=timeout)
    r.raise_for_status()
    cached.write_bytes(r.content)
    return r.content

def list_playlists(with_images=True, workers=8):
    client = setup_gspread()
    if not client:
        return list_xlsx_playlists()
    files = sorted(client.list_spreadsheet_files(), key=lambda f: f['name'].lower())
    playlists = [{'title': f['name'], 'id': f['id'], 'image_url': None, 'image': None, 'year': '', 'source': 'google'} for f in files]

    def fill(p):
        try:
            p['image_url'], p['year'] = _read_header(client, p['id'])
            if with_images and p['image_url']:
                p['image'] = fetch_image(p['image_url'])
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(fill, playlists))
    return list_xlsx_playlists() + playlists

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