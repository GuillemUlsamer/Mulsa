# TODO

## 1. Playlists sin service account
Google Sheets sigue siendo donde se marcan canciones (movil) y donde se escribe el estado; eso no
se toca hasta que exista la biblioteca (bloque 4). Lo que cambia es de donde salen las playlists.
- [ ] `sheets.py`: separar "de donde vienen las filas y donde se escribe el estado" (origen) del
  pipeline de descarga. Origen Google = lo de ahora. Sin cambio de comportamiento.
- [ ] Importar xlsx: boton Import en Playlists, `pick-file`, copia a `%LOCALAPPDATA%\Mulsa\playlists\`,
  lectura con `openpyxl` con la misma disposicion (una pestana por volumen, A2:C2 ano y portada).
  El estado se escribe en la columna G de la copia, igual que en la hoja. Reimportar actualiza las
  marcas sin perder estados. Las xlsx salen en la lista de playlists junto a las de Google.
- [ ] `gauth.py`: login OAuth con `drive.file` (no sensible, sin verificacion ni pantalla de aviso,
  gratis), navegador del sistema con `run_local_server`, token en `%LOCALAPPDATA%\Mulsa`, logout.
  Settings: fila "Google account" con Sign in / Sign out. El service account queda como opcion
  avanzada hasta que todo el mundo este migrado.
- [ ] Selector de Google (Picker) dentro de la ventana: Angular carga `api.js`, pide el token a la
  API y abre el selector; los IDs elegidos van a `POST /api/playlists/google`. Con `drive.file`
  solo se ven las hojas elegidas o creadas por Mulsa. Comprobar si elegir una carpeta da acceso a
  su contenido (probablemente no).
- [ ] "New playlist" desde Mulsa: crea la hoja en el Drive del usuario con cabeceras, anchos y
  checkboxes (lo que hoy hace "Set up" del Apps Script); al crearla Mulsa, la ve sin selector.
- [ ] Limpieza: README, `requirements.txt` (`openpyxl`, `google-auth-oauthlib`), `Mulsa.spec`
  (JSON del cliente OAuth en `datas`).

## 2. Rediseno
- [ ] Decidir el concepto antes de Figma: catalogo de discos / reproductor antiguo, no SaaS.
- [ ] Reunir 2-3 referencias (Dribbble, Mobbin, Godly: "music library", "record collection",
  "brutalist app") y guardar capturas.
- [ ] Fijar el sistema: una tipografia con caracter (probar monoespaciada para datos o display
  para titulos), paleta de 3 colores con un acento fuerte, y una decision sobre bordes y
  sombras (todo recto con lineas de 1px o todo redondeado, nada a medias).
- [ ] Figma: montar las tres pantallas con componentes reales para ver si el acento convive con
  las portadas.
- [ ] Donde mas se gana: tarjeta de playlist (portada grande) y lista del runner (estados con
  color, progreso visual en vez de texto).
- [ ] Leer Refactoring UI.

## 3. Discogs y setup dentro de la app (sustituye al Apps Script)
- [ ] "Set up": crear volumenes con cabeceras y anchos de columna con gspread.
- [ ] "Import release": pedir el release a la API de Discogs y escribir las filas en la hoja.
- [ ] "Import list": una lista completa, un volumen por release.
- [ ] Hoja Releases (catalogo de albumes con nombre, ano y portada).
- [ ] El Apps Script puede quedarse como opcion para importar desde el movil; las dos vias
  escriben en la misma hoja. La hoja sigue siendo la interfaz para marcar canciones desde el
  telefono: no se toca.

## 4. Biblioteca dentro de la app
- [ ] Escaneo de la carpeta de musica con mutagen: artista, titulo, album, duracion, bitrate,
  ruta. Guardarlo en SQLite (base local de un solo usuario).
- [ ] `GET /api/library?q=` con busqueda y filtros.
- [ ] Pantalla con buscador; abrir la carpeta o el fichero con el reproductor del sistema. Sin
  reproducir musica dentro de la app en la primera version.
- [ ] Vista de playlist con descargadas y pendientes juntas.
- [ ] Opcional: `host="0.0.0.0"` en `main.py` para ver la biblioteca desde el movil en la misma
  wifi (solo lectura).
