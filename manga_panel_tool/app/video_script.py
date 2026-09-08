"""
Etapa 3: Guion de video resumen del manga y diapositivas.

Parte del proyecto ya analizado (panel.extra["analysis"]) y de los
recortes guardados en panel_crops/, y produce:

- "slides": una lista ordenada (orden de lectura confirmado) de
  diapositivas con: imagen del panel, texto de resumen y duración
  calculada según la longitud del texto (tiempo de lectura).
- Un guion en texto (guion_video.txt) con sinopsis + cada diapositiva.
- Imágenes PNG por diapositiva (imagen del panel + resumen encima).

No modifica nada de las etapas anteriores: solo lee el modelo.
"""
import os
import json
import re
from typing import List, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage, QColor, QPainter, QFont, QTextDocument, QTextOption

# Velocidad de lectura asumida (caracteres por segundo) para subtítulos.
READING_CHARS_PER_SECOND = 14.0
MIN_SLIDE_SECONDS = 3.0

# Tamaño de la diapositiva exportada (16:9)
SLIDE_W = 1280
SLIDE_H = 720

# Área de imagen (arriba) y banda de texto (abajo)
TEXT_BAND_H = 170


# --------------------------------------------------------------------------
# Construcción de datos
# --------------------------------------------------------------------------
def default_panel_text(analysis: dict) -> str:
    """Texto de resumen por defecto para un panel, a partir de su análisis."""
    if not analysis:
        return ""
    parts = []
    desc = str(analysis.get("description") or "").strip()
    if desc:
        parts.append(desc)
    dialogue = str(analysis.get("dialogue") or "").strip()
    if dialogue:
        parts.append(f'«{dialogue}»')
    return " ".join(parts)


def collect_slides(project, crops_by_page: Dict[str, Dict[str, str]],
                   texts_by_panel: Optional[Dict[str, str]] = None) -> List[dict]:
    """Recorre todas las páginas/paneles en el orden de lectura confirmado y
    construye la lista de diapositivas.

    crops_by_page: page_id -> {panel_id: ruta del recorte}
    texts_by_panel: panel_id -> texto de resumen (opcional; si falta se usa
                    el del análisis guardado).
    """
    slides = []
    texts_by_panel = texts_by_panel or {}
    for page in project.pages:
        page_crops = crops_by_page.get(page.id, {})
        for panel in page.panels:
            text = texts_by_panel.get(panel.id) or default_panel_text(
                panel.extra.get("analysis") or {}
            )
            duration = compute_duration(text)
            slides.append({
                "page_id": page.id,
                "panel_id": panel.id,
                "image_path": page_crops.get(panel.id, ""),
                "text": text,
                "duration": duration,
                "page": os.path.basename(page.image_path),
            })
    return slides


def compute_duration(text: str) -> float:
    """Tiempo de lectura necesario: proporcional a la longitud del texto,
    con mínimo de MIN_SLIDE_SECONDS."""
    n = len((text or "").strip())
    return round(max(MIN_SLIDE_SECONDS, n / READING_CHARS_PER_SECOND), 1)


def total_duration(slides: List[dict]) -> float:
    return round(sum(s["duration"] for s in slides), 1)


def panels_text_for_ai(slides: List[dict]) -> str:
    """Textos numerados de los paneles, para pedir la sinopsis a la IA."""
    lines = []
    for i, s in enumerate(slides, start=1):
        lines.append(f"Viñeta {i}: {s['text'] or '(sin información)'}")
    return "\n".join(lines)


def parse_ai_summary(raw: str, n_panels: int):
    """Extrae {'synopsis': str, 'panels': [str]} de la respuesta de la IA."""
    text = raw.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m2 = re.search(r"\{.*\}", text, re.DOTALL)
        if not m2:
            return None
        try:
            data = json.loads(m2.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    synopsis = str(data.get("synopsis") or "").strip()
    panels = data.get("panels") or []
    if isinstance(panels, str):
        panels = [panels]
    panels = [str(p).strip() for p in panels if str(p).strip()]
    if len(panels) != n_panels:
        # si la IA devolvió un número distinto, no reemplazar 1 a 1:
        # solo aceptar si coincide para no desalinear el guion
        panels = panels if len(panels) == n_panels else []
    return {"synopsis": synopsis, "panels": panels}


# --------------------------------------------------------------------------
# Guion en texto
# --------------------------------------------------------------------------
def format_timecode(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def export_script_txt(slides: List[dict], path: str, synopsis: str = "") -> None:
    lines = []
    lines.append("GUION — VIDEO RESUMEN DEL MANGA")
    lines.append("=" * 60)
    if synopsis:
        lines.append("")
        lines.append("SINOPSIS (narración de apertura)")
        lines.append("-" * 60)
        for chunk in _wrap(synopsis, 70):
            lines.append(chunk)
        lines.append(f"[duración sugerida: {compute_duration(synopsis)} s]")
    lines.append("")
    lines.append("DIAPOSITIVAS")
    lines.append("-" * 60)
    t = 0.0
    for i, s in enumerate(slides, start=1):
        start = format_timecode(t)
        end = format_timecode(t + s["duration"])
        t += s["duration"]
        lines.append(f"Diapositiva {i}  ({start} → {end}, {s['duration']} s)")
        lines.append(f"  Imagen: panel de {s['page']}")
        if s["text"]:
            for chunk in _wrap(s["text"], 70):
                lines.append(f"  Texto: {chunk}")
        else:
            lines.append("  Texto: (sin resumen)")
        lines.append("")
    lines.append(f"DURACIÓN TOTAL: {format_timecode(t)} ({total_duration(slides)} s)")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _wrap(text: str, width: int) -> List[str]:
    words = (text or "").split()
    if not words:
        return []
    lines, cur = [], words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


# --------------------------------------------------------------------------
# Render de diapositivas (imagen del panel + texto encima)
# --------------------------------------------------------------------------
def render_slide(image_path: str, text: str, index: int, out_path: str,
                 width: int = SLIDE_W, height: int = SLIDE_H,
                 text_band_h: int = TEXT_BAND_H) -> bool:
    """Compone una diapositiva 16:9: imagen del panel arriba centrada y una
    banda inferior con el texto de resumen (con ajuste de línea)."""
    img_area_h = height - text_band_h

    canvas = QImage(width, height, QImage.Format_RGB32)
    canvas.fill(QColor(18, 18, 22))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)

    # --- imagen del panel ---
    if image_path and os.path.exists(image_path):
        pix = QPixmap(image_path)
        if not pix.isNull():
            scaled = pix.scaled(
                width - 40, img_area_h - 30, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            x = (width - scaled.width()) // 2
            y = (img_area_h - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

    # --- banda de texto ---
    painter.fillRect(0, img_area_h, width, text_band_h, QColor(10, 10, 14))

    # número de diapositiva
    painter.setPen(QColor(150, 150, 160))
    painter.setFont(QFont("Segoe UI", 9))
    painter.drawText(14, img_area_h + 22, f"Diapositiva {index}")

    # texto de resumen con ajuste automático
    doc = QTextDocument()
    doc.setDefaultFont(QFont("Segoe UI", 13))
    doc.setTextWidth(width - 40)
    opt = QTextOption()
    opt.setWrapMode(QTextOption.WordWrap)
    doc.setDefaultTextOption(opt)
    doc.setPlainText(text or "(sin resumen)")

    # reducir la fuente si el texto no cabe en la banda
    font_size = 13
    while doc.size().height() > text_band_h - 42 and font_size > 8:
        font_size -= 1
        doc.setDefaultFont(QFont("Segoe UI", font_size))
        doc.setTextWidth(width - 40)

    painter.save()
    painter.translate(20, img_area_h + 34)
    painter.setPen(QColor(235, 235, 240))
    doc.drawContents(painter)
    painter.restore()

    painter.end()
    return canvas.save(out_path, "PNG")


def export_slides(slides: List[dict], out_dir: str) -> List[str]:
    """Exporta todas las diapositivas como PNG numeradas (001.png, ...)."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i, s in enumerate(slides, start=1):
        out = os.path.join(out_dir, f"{i:03d}.png")
        if render_slide(s["image_path"], s["text"], i, out):
            paths.append(out)
    return paths
