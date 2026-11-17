# TODO

## 2. Rediseno: restos
Estanteria, disco seleccionado, apertura, runner, settings y setup estan hechos (handoffs en
design_handoff_*). Queda:
- [ ] Canguro: `web/public/kangaroo.png` (PNG con fondo transparente) para Settings, y el icono
  24x24 en la cabecera de Playlists.
- [ ] Volver del runner con la animacion inversa (hoy: fundido y el disco vuelve seleccionado).
- [ ] Email de la cuenta junto a "Connected" en Settings (scope `userinfo.email` en gauth).
- [ ] Capturas nuevas para el README.
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
- [ ] Al llegar aqui, el estado de cada cancion pasa a vivir en Mulsa y se deja de escribir en la
  columna G de la hoja (hoy se escribe en la hoja de Google o en la copia xlsx).
- [ ] Escaneo de la carpeta de musica con mutagen: artista, titulo, album, duracion, bitrate,
  ruta. Guardarlo en SQLite (base local de un solo usuario).
- [ ] `GET /api/library?q=` con busqueda y filtros.
- [ ] Pantalla con buscador; abrir la carpeta o el fichero con el reproductor del sistema. Sin
  reproducir musica dentro de la app en la primera version.
- [ ] Vista de playlist con descargadas y pendientes juntas.
- [ ] Opcional: `host="0.0.0.0"` en `main.py` para ver la biblioteca desde el movil en la misma
  wifi (solo lectura).
