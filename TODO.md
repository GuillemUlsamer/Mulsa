# TODO

## 2. Rediseno: la estanteria
Concepto: una playlist es un disco. Referencia: bingebrowse.net (videoclub 3D), pero sin escena 3D
ni camara: CSS puro (perspective, rotateX/rotateY, scroll-snap, backdrop-filter). Sin edicion de
marcas desde la app.
- [ ] Figma solo de la pantalla Playlists, dos estados: estanteria en reposo y disco seleccionado.
  Ahi se decide perspectiva, tamano de los discos y el panel de info.
- [ ] Backend: contraportada. `import_release` guarda la segunda imagen de Discogs (columna L junto
  a la portada); `/playlists` la devuelve. Hojas sin contraportada: reverso liso con el tracklist.
- [ ] Backend: `/playlists` sigue rapido como hoy; un `GET /playlists/{name}/info` con volumenes,
  marcadas y descargadas se pide solo para el disco seleccionado.
- [ ] Estanteria: baldas con ligera perspectiva, discos con grosor (dos caras + rotateY), escala al
  pasar el raton, etiqueta de supermercado debajo (nombre, ano, "12/24" descargadas) sobre la que
  cae la sombra del disco.
- [ ] Disco seleccionado: sale al centro con fondo oscuro y desenfocado, panel de info a la derecha,
  boton "Back cover" (no girar al hacer clic: el clic abre), flechas para pasar al siguiente.
- [ ] Entrar en el disco (Runner): `GET /playlists/{name}/tracks` por volumen (artista, titulo,
  duracion, marcada, estado). Pantalla partida: lista a la izquierda (marcadas resaltadas, el
  resto en gris) con selector de volumenes abajo; descarga a la derecha como ahora.
- [ ] Transiciones: abrir (la portada escala y hace fade a la pantalla partida) y volver (fade al
  disco, se cierra, estanteria). Si hay descarga en marcha, volver no la para.
- [ ] Settings: sencillo, con el canguro entero al lado. Vigilar anchuras por debajo de 1100 px.
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
