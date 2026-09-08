"""Recortes de paneles para el análisis por IA."""
import os

import cv2

from .models import Panel


def panel_crop_path(panels_dir: str, panel_id: str) -> str:
    return os.path.join(panels_dir, f"{panel_id}.png")


def ensure_crops(page, panels_dir: str) -> dict:
    """Genera (si no existen ya) los recortes PNG de todos los paneles de la
    página y devuelve {panel_id: ruta_al_recorte}.

    page: objeto Page con .image_path y .panels
    """
    os.makedirs(panels_dir, exist_ok=True)
    img = cv2.imread(page.image_path)
    if img is None:
        raise RuntimeError(f"No se pudo leer la imagen: {page.image_path}")

    paths = {}
    for panel in page.panels:
        out = panel_crop_path(panels_dir, panel.id)
        if not os.path.exists(out):
            h, w = img.shape[:2]
            x0 = max(0, int(panel.x))
            y0 = max(0, int(panel.y))
            x1 = min(w, int(panel.x + panel.w))
            y1 = min(h, int(panel.y + panel.h))
            crop = img[y0:y1, x0:x1]
            if crop.size == 0:
                continue
            cv2.imwrite(out, crop)
        paths[panel.id] = out
    return paths
