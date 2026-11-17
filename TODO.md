# TODO

## 2. Rediseno: restos
- [ ] Canguro entero para Settings: guardar el dibujo como `web/public/kangaroo.png` (PNG con fondo
  transparente, cuerpo entero, unos 600 px de alto; si pesa mas de ~200 KB, reducirlo como se
  hizo con logo.png). No hay que tocar codigo: `settings.html` ya lo pide y lo oculta si no
  existe; `ng build` lo copia a la raiz del dist. Ocupa la mitad derecha, apoyado en el borde
  inferior (`.mascot` en settings.scss).
- [ ] Capturas nuevas para el README.

## 3. Biblioteca dentro de la app
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
