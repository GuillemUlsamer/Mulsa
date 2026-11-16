# TODO

## App
- [ ] Puerto de la API fijo (8765) en `main.py`: si esta ocupado la ventana abre en blanco. Elegir
  uno libre al arrancar (`socket` con puerto 0) y pasarselo a uvicorn y a `create_window`.

## 1. OAuth (quitar credentials.json)
- [ ] Registrar un cliente OAuth propio en Google Cloud (tipo Desktop) con scopes de Drive y Sheets.
- [ ] `api.py`: endpoint que abre el navegador del sistema con la URL de consentimiento y otro que
  recibe el callback en `127.0.0.1:8765`; guardar el token en `%LOCALAPPDATA%\Mulsa`.
- [ ] `sheets.py`: autenticar gspread con el token en vez del service account.
- [ ] Settings: boton "Sign in with Google" en lugar del campo de `credentials.json`. Mantener el
  service account como opcion avanzada para quien ya lo tenga.
- [ ] Ya no hace falta compartir la hoja con el `client_email`: actualizar README.

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
