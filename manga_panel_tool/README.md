# Manga Panel Analyzer — Prototipo v1

Aplicación de escritorio para analizar páginas de manga: carga páginas,
detecta automáticamente las viñetas, permite corregirlas a mano, define
el orden de lectura y guarda todo en un archivo JSON.

Esta primera versión cubre **exclusivamente** el flujo:

```
CARGAR PÁGINAS → DETECTAR VIÑETAS → CORREGIR VIÑETAS → ORDENAR → GUARDAR JSON
```

No incluye (todavía) análisis con IA, OCR, resúmenes, voz ni vídeo — el
código está organizado en módulos precisamente para añadir eso después
sin reescribir nada (ver [Ampliaciones futuras](#ampliaciones-futuras)).

## 1. Instalación

Requiere **Python 3.10 o superior**.

```bash
# 1. Entra en la carpeta del proyecto
cd manga_panel_tool

# 2. (Recomendado) crea un entorno virtual
python3 -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate

# 3. Instala las dependencias
pip install -r requirements.txt
```

Dependencias (todas ligeras y multiplataforma: Windows, macOS, Linux):

| Librería       | Para qué se usa                                   |
|----------------|----------------------------------------------------|
| `PySide6`      | Interfaz gráfica (oficial de Qt para Python)        |
| `opencv-python`| Detección automática de viñetas                     |
| `numpy`        | Soporte numérico usado por OpenCV                   |

## 2. Ejecución

```bash
python main.py
```

## 3. Cómo se usa

1. **Cargar páginas** — botón "📂 Cargar páginas". Puedes seleccionar
   varias imágenes a la vez (PNG, JPG, BMP, WEBP). Cada página se
   analiza automáticamente al cargarla.
2. **Ver la detección** — las viñetas detectadas aparecen con un
   recuadro rojo y un número (el orden de lectura sugerido, calculado
   de arriba a abajo y de derecha a izquierda, como es habitual en
   manga). Se dibujan flechas azules entre viñetas consecutivas.
3. **Corregir el orden** — en el panel derecho ("Orden de lectura")
   arrastra los elementos de la lista para cambiar el orden. Los
   números y las flechas del lienzo se actualizan al instante.
4. **Mover / redimensionar una viñeta** — haz clic sobre el recuadro y
   arrástralo para moverlo, o arrastra una de sus esquinas (los
   cuadraditos azules aparecen al seleccionarla) para redimensionarlo.
5. **Crear una viñeta manualmente** — activa "➕ Nueva viñeta" y dibuja
   un recuadro con el ratón sobre la página; se añadirá al final del
   orden de lectura.
6. **Eliminar una viñeta** — selecciónala (clic) y pulsa
   "🗑 Eliminar".
7. **Dividir una viñeta** — selecciónala y pulsa "✂ Dividir vertical"
   o "✂ Dividir horizontal" (se parte en dos mitades iguales; después
   puedes ajustar cada mitad arrastrando sus esquinas).
8. **Unir varias viñetas** — selecciona dos o más con Ctrl+clic y pulsa
   "🔗 Unir viñetas" (se sustituyen por un único recuadro que las
   engloba a todas).
9. **Pasar de página** — usa "◀ Anterior" / "Siguiente ▶", o haz clic
   directamente en una página de la lista de la izquierda. Cada
   página guarda sus propias correcciones de forma independiente.
10. **Guardar el proyecto** — botón "💾 Guardar proyecto". Genera un
    archivo `.json` con todas las páginas, viñetas, su geometría y su
    orden de lectura. "📁 Abrir proyecto" permite recuperarlo más
    tarde (nota: las rutas de las imágenes deben seguir siendo
    válidas).

### Atajo rápido de herramientas

| Acción                | Cómo hacerlo                                          |
|------------------------|-------------------------------------------------------|
| Seleccionar una viñeta | Clic sobre ella                                        |
| Selección múltiple     | Ctrl + clic sobre varias viñetas                       |
| Mover viñeta           | Arrastrar el cuerpo del recuadro                       |
| Redimensionar          | Arrastrar una esquina (visible al seleccionar)         |
| Reordenar lectura      | Arrastrar en la lista "Orden de lectura" (derecha)     |

## 4. Sobre la detección automática

El detector (`app/detection.py`) usa un método clásico de visión por
computador (umbralización + dilatación morfológica + contornos), **no**
un modelo de IA entrenado. Funciona razonablemente en páginas con
márgenes/calles blancas entre viñetas, pero puede:

- fusionar viñetas separadas por una calle muy estrecha,
- fallar con viñetas de forma muy irregular o sin borde definido,
- confundirse con páginas muy oscuras o con tramas complejas.

**Esto es intencional para esta v1**: en lugar de perseguir una
detección perfecta, el esfuerzo se puso en que corregir cualquier
error sea rápido (mover, dividir, unir, crear, eliminar). El botón
"🔍 Detectar viñetas" permite reintentar la detección automática en la
página actual en cualquier momento.

## 5. Formato del archivo JSON guardado

```json
{
  "version": 1,
  "pages": [
    {
      "id": "6aac9cf3",
      "image_path": "/ruta/a/pagina_01.png",
      "width": 700,
      "height": 1000,
      "panels": [
        { "id": "642dfc9e", "x": 29, "y": 719, "w": 647, "h": 257, "extra": {} }
      ],
      "extra": {}
    }
  ]
}
```

- El **orden de la lista `panels`** es el orden de lectura (índice 0 =
  primera viñeta a leer).
- `x, y, w, h` están en píxeles de la imagen original de la página.
- Cada `panel` y cada `page` tiene un diccionario `extra` vacío,
  reservado para los módulos futuros (ver siguiente sección).

## 6. Estructura del código

```
manga_panel_tool/
├── main.py                 # punto de entrada
├── requirements.txt
└── app/
    ├── models.py            # Panel, Page, Project + guardado/carga JSON
    ├── detection.py         # detección automática de viñetas (OpenCV)
    ├── ordering.py           # orden de lectura por defecto (heurístico)
    ├── canvas.py             # PanelItem, tiradores, flechas, vista central
    └── main_window.py        # ventana principal: conecta todo lo anterior
```

## 7. Ampliaciones futuras

El código está separado a propósito para que cada nueva funcionalidad
sea un módulo nuevo que lee del mismo `Project`/`Page`/`Panel`, sin
tocar la lógica ya existente:

- **Análisis de cada viñeta con IA** → nuevo módulo `app/ai_analysis.py`
  que reciba el recorte de imagen de cada `Panel` (usando su `x,y,w,h`
  sobre `page.image_path`) y guarde el resultado en `panel.extra["ai_description"]`.
- **OCR de los diálogos** → nuevo módulo `app/ocr.py`, mismo patrón:
  guardar el texto en `panel.extra["dialogue_text"]`.
- **Resumen automático** → un módulo que recorra `page.panels` en
  orden (¡ya está resuelto por este prototipo!) y use las
  descripciones/diálogos guardados en `extra` para generar un resumen
  por página o del capítulo completo.
- **Generación de voz** → a partir del resumen o de los diálogos,
  guardar rutas de audio en `panel.extra["audio_path"]`.
- **Creación de vídeo** → un módulo final que recorra
  `page.panels` en orden, recorte cada viñeta de la imagen original
  usando sus coordenadas, y las combine con el audio generado.

Como el orden de lectura, las coordenadas y las correcciones manuales
ya quedan resueltas y guardadas en el JSON, todos estos módulos
futuros pueden trabajar directamente sobre `Project.load(path)` sin
necesitar la interfaz gráfica.

## 8. Limitaciones conocidas de esta v1

- Los archivos de imagen deben mantenerse en la misma ruta si se
  quiere reabrir un proyecto guardado (no se copian dentro del JSON).
- La detección automática es heurística, no un modelo de IA (ver
  sección 4).
- No hay deshacer/rehacer (Ctrl+Z) todavía — es un buen candidato para
  una siguiente iteración.
