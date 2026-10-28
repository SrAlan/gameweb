# Web de la demo — Tattoo Studio Simulator

Página para presentar la demo y descargarla, pensada para enviarla a cualquiera: portada con el botón de descarga, galería de capturas como en las tiendas (miniaturas, flechas y ampliar al hacer clic), la novedad destacada (dibujar tus diseños), tarjetas con lo que se hace en el juego, tres pasos para empezar y dudas rápidas plegables. Sin detalles técnicos.

```
index.html     La página
assets/        Capturas del juego
game/          Aquí va el .rar de la demo
serve.py       Servidor local para verla (opcional)
```

## Poner la descarga

1. En Godot: *Proyecto → Exportar… → Añadir… → Windows Desktop* y exporta el ejecutable (con el `.pck` al lado o incrustado).
2. Comprime la carpeta exportada en un `.rar` llamado **`TattooStudioSimulator-Demo.rar`**.
3. Cópialo dentro de `game/`.

Si prefieres otro nombre, cámbialo en `index.html`, en la línea:

```js
const DOWNLOAD_FILE = "game/TattooStudioSimulator-Demo.rar";
```

## Verla en el equipo

Basta con abrir `index.html`. Con el servidor (`python serve.py` → <http://localhost:8000>) la página además comprueba que el archivo está: si falta, el botón dice «Próximamente»; si está, muestra su tamaño.

## Subirla

Se sube tal cual a cualquier hosting de páginas estáticas (GitHub Pages, Netlify…). Ojo: GitHub no acepta archivos de más de 100 MB en el repositorio; si el .rar pesa más, súbelo a otro sitio (Google Drive, itch.io, Mega…) y pon ese enlace en `DOWNLOAD_FILE`.
