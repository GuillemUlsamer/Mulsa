# Mulsa: contexto para seguir desarrollando (con o sin IA)

Este fichero resume todo lo que hay que saber del proyecto y de como se trabaja en el. Va en la
raiz del repo. Si lo lee un asistente (Claude Code carga CLAUDE.md solo), debe seguir las reglas
de la seccion "Como trabajo". Ultima actualizacion: noviembre 2026, version 3.2.x.

## Que es

Mulsa es una app de escritorio (Windows) para construir playlists de musica a partir de hojas de
Google Sheets: marcas canciones en la hoja (tambien desde el movil), Mulsa las busca en Soulseek
a traves de slskd, las descarga, convierte a MP3 320, etiqueta (ID3 con portada) y escribe el
estado en la hoja. Las playlists se crean desde la app a partir de releases o listas de Discogs.
La interfaz es una estanteria de discos (cajas de CD en 3D con CSS), con una ficha por disco y
un "runner" que es el interior de la caja (libreto con los temas + log de descarga).

- Repo: https://github.com/GuillemUlsamer/Mulsa (rama `main`; releases por tag `vX.Y.Z`,
  GitHub Actions construye el instalador con PyInstaller + Inno Setup).
- Usuarios: Guillem y algun amigo. No hay servidor: todo corre en el PC del usuario.

## Arquitectura

```
main.py          arranca uvicorn en un hilo (puerto libre) y abre una ventana pywebview (marco
                 nativo, titulo vacio, maximizada) con http://127.0.0.1:<puerto>
api.py           FastAPI montada en /api; sirve web/dist/web/browser en /. Endpoints: playlists
                 (lista rapida + /header por playlist, /info, /cover, /back-cover), run/stop/
                 status/log/summary, events (SSE), settings, auth google, picker, playlists
                 new/setup/import-list/import-release/volumes, delete, pick-folder/file, open-url
web/             Angular 22 standalone, signals, sin NgModules. Componentes: page (marco comun:
                 cabecera con slots [back] y [actions], contenido, pie), shelf (estanteria),
                 record (disco seleccionado + apertura), playlists, runner, settings, setup.
                 api.ts es el servicio: HTTP, SSE (events()), cache de playlists, go() (fundido
                 + navegacion). web/public/picker.html es el selector de Google Drive, abierto
                 en el navegador del sistema (WebView2 no deja cookies al Picker).
manager.py       una ejecucion: ensure_slskd, origen (GoogleSource o XlsxSource), process_playlist
sheets.py        origenes (volumes()/set_status()), listado de playlists, playlist_info, creacion
                 y relleno de hojas (setup_sheet, import_release, import_list), xlsx import
downloader.py    estrategia de busquedas (Exact/Album/Loose/Title/Artist/Queued retry/Last resort)
matching.py      puntuacion y filtrado de candidatos (strict mode, single-word, remix penalty...)
slskd_client.py  API de slskd, conversion FLAC->MP3, memoria de usuarios (users.json)
tagging.py       limpieza de nombres, ID3 v2.3, file_duration
gauth.py         OAuth de Google (drive.file), token en %LOCALAPPDATA%\Mulsa\google_token.json
discogs.py       API de Discogs con las claves de la app (assets/discogs_client.json) o token
log.py           canal de eventos pipeline -> UI (song/status/line), fichero mulsa.log, summary
bootstrap.py     primer arranque: descarga slskd, slskd.yml, config.json; rutas de APP_DIR
```

Datos del usuario en `%LOCALAPPDATA%\Mulsa`: `config.json` (soulseek_username, music_dir,
share_dir, listen_port, drive_folder_id/name...), `google_token.json`, `users.json`, `mulsa.log`,
`playlists\*.xlsx` (copias de playlists importadas), `tools\slskd`.

Formato de hoja (lo lee Python): pestana `Releases` primera (A: album, B: ano, C: `=IMAGE(url)`;
A2:C2 da la portada y el ano de la playlist); pestanas `V 1..N` con A pos, B artista, C titulo,
D duracion, E acumulado, F casilla, G estado, I1 album, J1 ano, K1 portada, L1 contraportada.

## Ficheros que NO estan en git (hay que copiarlos a mano a un PC nuevo)

- `assets/google_client.json`: cliente OAuth de escritorio de Google Cloud (proyecto numero
  822697319414, scope drive.file, app publicada "en produccion" sin verificacion).
- `assets/discogs_client.json`: `{"key","secret"}` de la aplicacion Discogs "Mulsa".
- Ambos van tambien como secretos del repo en GitHub (GOOGLE_CLIENT_JSON, DISCOGS_CLIENT_JSON);
  el workflow de release los escribe en assets/ antes de PyInstaller.
- `NOTES.md`: chuleta personal de comandos.
- `web/public/kangaroo.png` (pendiente, mascota para Settings).

## Desarrollo

```
pip install -r requirements.txt ; cd web; npm ci; cd ..
python -m uvicorn api:app --reload --port 8765      # backend
cd web; ng serve                                    # frontend en :4200 (proxy a 8765)
cd web; ng build; cd ..; python main.py             # ventana nativa (dialogos de fichero, Picker)
```
Release: PR a main, merge, `git tag vX.Y.Z`, `git push origin vX.Y.Z`.

## Decisiones tomadas (y por que)

- Google con `drive.file` (no sensible, gratis, sin pantalla de aviso): Mulsa solo ve las hojas
  que el usuario elige en el Picker o que ella crea. Listar Drive entero necesitaria un scope
  restringido con auditoria de pago. Elegir una carpeta NO da acceso a su contenido; la carpeta
  solo se guarda como destino para crear playlists nuevas.
- El service account (`credentials.json`) queda como opcion avanzada; `is_configured` acepta
  token OAuth o credentials.json.
- El estado de cada cancion se sigue escribiendo en la hoja (columna G) o en la copia xlsx.
  Pasara a vivir en Mulsa (SQLite) cuando exista la biblioteca (TODO bloque 3).
- Discogs: claves de aplicacion embebidas (60 req/min compartidas); el token personal del usuario
  esta soportado pero oculto (lineas comentadas en settings/api/bootstrap).
- Las URLs de imagen de Discogs llevan la ruta original en base64 (`R-<release>-...`); el
  script `_test/backfill_backcovers.py` lo uso para rellenar contraportadas de hojas antiguas.
- Ventana: se probo sin marco (frameless) y se descarto: pywebview en Windows no da snap ni
  maximizado correcto. Marco nativo con titulo vacio.
- Puerto de la API dinamico (socket puerto 0) y `wait_for` antes de abrir la ventana.
- `GoogleSource.volumes()` usa `values_batch_get` (una peticion para todas las pestanas);
  `setup_sheet` agrupa en ~5 peticiones; `/playlists` devuelve nombres rapido y la estanteria
  pide `/header` por disco (carga progresiva). `playlistsStale` en vez de vaciar la cache.
- `playlist_info` devuelve `row` por tema para casar los eventos del log (`song_id = [vol, fila]`).

## Diseno

Sistema: Roboto Condensed 400/700 (empaquetada en web/public/fonts), fondo #F9F9FA, texto
#1F242E, muted #5B6472, faint #8A93A0, bordes #DBE0E6, papel #ECEEF1, radio 2px, botones 24px
(blanco con borde, o primario #1F242E), estados done #1E8E5A / verify #B7791F / failed #D93025.
Las entregas de diseno (HTML de referencia + README con medidas) estan en `docs/design/`
(zips): 1 estanteria, 2 disco seleccionado, 3 runner + apertura, 4 settings y setup. Las
pantallas se disenaron con una herramienta tipo Figma a partir de prompts; el flujo que funciono:
prompt describiendo contexto, tokens y restricciones -> handoff -> implementar -> retoques.
Caja de CD: seis caras con preserve-3d; la tapa gira sobre el borde izquierdo al abrir; disco con
la portada como etiqueta; apertura ~2 s y FLIP (Web Animations API) hacia las columnas del runner.

## Pendiente

Ver `TODO.md`: canguro en Settings, capturas del README, biblioteca local (SQLite + buscador),
y reorganizar `web/src/app` en pages/components/services cuando crezca.

## Como trabajo (reglas para un asistente)

- Hablar en castellano, sin emojis, sin introducciones ("buena pregunta", etc.). Directo.
- Guillem esta aprendiendo full-stack: explicar el concepto cuando algo es nuevo, paso a paso,
  y dejarle hacer los cambios simples a el ("dime como" = guia; "hazlo" = escribirlo).
- No editar ficheros hasta que lo pida. Si hace una pregunta, responder sin ejecutar nada.
- Diffs minimos. Comentarios con `#` / `//` en su propia linea, nunca inline ni docstrings
  `"""` para comentar ficheros. 2 espacios en `web/`. Ficheros sin CRLF.
- Reutilizar antes de crear; preguntar antes de crear un fichero nuevo.
- `TODO.md` solo contiene lo pendiente: lo hecho se borra, no se tacha. `NOTES.md` es su
  chuleta personal (gitignored).
- Flujo git: rama por tema, PR a `main`, tag para release. Nunca forzar push.
- Las claves (google_client.json, discogs_client.json) no van a git; GitHub bloquea el push.
- Sin edicion de marcas desde la app: la hoja de Google sigue siendo la interfaz del movil.
