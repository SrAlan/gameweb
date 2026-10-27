# Web de la demo — Tattoo Studio Simulator

Página para enseñar y jugar la demo en el navegador: ventana del juego con pantalla completa, recargar y abrir en otra pestaña, y debajo la información del juego (qué es, cómo se juega, controles, modos, capturas y notas de la demo).

```
index.html     La página
assets/        Capturas del juego
game/          Aquí va la exportación web (game.html y el resto de archivos)
serve.py       Servidor local para probarla
```

## Poner el juego

1. En Godot: *Proyecto → Exportar… → Añadir… → Web*. Si es la primera vez, instala las plantillas de exportación cuando lo pida.
2. *Ruta de exportación*: `game.html` (dentro de una carpeta cualquiera).
3. Exporta y copia **todos** los archivos que salen (`game.html`, `game.js`, `game.wasm`, `game.pck`, `game.png`…) dentro de `game/`.

Notas de la exportación:
- La web usa el renderizador **Compatibility** (Godot lo hace solo al exportar para web). Algunos efectos se ven algo distintos que en escritorio.
- Si en la exportación dejas activado **Thread Support**, el servidor tiene que mandar las cabeceras COOP/COEP (lo hace `serve.py`; en itch.io, marca *SharedArrayBuffer support*). Sin hilos no hacen falta.
- El modo **Amigos** no funciona en la web (usa conexiones UDP directas que los navegadores no permiten). La página ya lo avisa.

## Probarla en el equipo

Los juegos web de Godot no se pueden abrir con doble clic en el archivo. En esta carpeta:

```
python serve.py
```

y abre <http://localhost:8000>. Si `game/game.html` aún no está, la página lo dice al pulsar «Jugar la demo».

## Subirla

Se puede subir tal cual a cualquier hosting de páginas estáticas (GitHub Pages, Netlify, itch.io como HTML…). Si la exportación usa hilos, el hosting tiene que mandar las cabeceras `Cross-Origin-Opener-Policy: same-origin` y `Cross-Origin-Embedder-Policy: require-corp`.
