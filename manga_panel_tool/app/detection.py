"""
Detección automática de paneles en una página de manga.

El algoritmo es deliberadamente simple y heurístico: NO necesita ser
perfecto (la interfaz está pensada para que el usuario corrija
cualquier fallo en segundos). Funciona razonablemente bien en páginas
típicas con márgenes/calles blancas entre viñetas y bordes oscuros.

Estrategia:
 1. Escala de grises + desenfoque para reducir ruido.
 2. Umbralización binaria para separar "tinta" (bordes + dibujo) del
    papel en blanco.
 3. Dilatación morfológica fuerte para que cada viñeta se convierta en
    UN solo blob sólido conectado (dibujo + bordes se fusionan),
    mientras que las calles (márgenes blancos puros) siguen separando
    los blobs entre sí.
 4. Se buscan los contornos externos de esos blobs y se filtran los
    que parecen una viñeta real (ni demasiado pequeños ni la página
    entera).
 5. Se devuelve el rectángulo delimitador de cada contorno.

Este módulo expone una única función pública, `detect_panels`, para
poder sustituirla en el futuro por algo más inteligente (p. ej. un
modelo de segmentación entrenado) sin tocar el resto de la app.
"""
from typing import List, Tuple

import cv2
import numpy as np

BBox = Tuple[int, int, int, int]  # x, y, w, h


def detect_panels(
    image_path: str,
    min_area_ratio: float = 0.02,
    max_area_ratio: float = 0.95,
) -> List[BBox]:
    """Detecta los rectángulos de las viñetas en una página de manga.

    Args:
        image_path: ruta a la imagen de la página.
        min_area_ratio: ignora blobs más pequeños que esta fracción del
            área de la página (ruido).
        max_area_ratio: ignora blobs más grandes que esta fracción del
            área de la página (evita detectar la página entera como
            una sola viñeta).

    Returns:
        Lista de tuplas (x, y, w, h). El orden de lectura NO se decide
        aquí, se calcula por separado en `ordering.py`.
    """
    img = cv2.imread(image_path)
    if img is None:
        return []

    h_img, w_img = img.shape[:2]
    page_area = float(h_img * w_img)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # Umbral de Otsu invertido: tinta/dibujo -> blanco (255), papel -> negro (0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Dilatamos para que el dibujo + los bordes de cada viñeta se
    # fusionen en un único blob sólido, mientras las calles (más
    # anchas) siguen separando viñetas distintas. Se usa un kernel
    # moderado: si es demasiado grande, viñetas con una calle estrecha
    # entre ellas terminan fusionadas (el usuario puede dividirlas a
    # mano con la herramienta "Dividir").
    kernel_size = max(3, int(min(w_img, h_img) * 0.006))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    dilated = cv2.dilate(binary, kernel, iterations=2)
    dilated = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes: List[BBox] = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        ratio = (w * h) / page_area
        if ratio < min_area_ratio or ratio > max_area_ratio:
            continue
        # descarta tiras finísimas (ruido / líneas sueltas)
        if w < 0.03 * w_img or h < 0.03 * h_img:
            continue
        boxes.append((x, y, w, h))

    boxes = _remove_contained_boxes(boxes)

    # pequeño margen hacia dentro para que el recuadro no invada la calle
    margin = max(2, kernel_size // 2)
    boxes = [
        (x + margin, y + margin, max(1, w - 2 * margin), max(1, h - 2 * margin))
        for x, y, w, h in boxes
    ]
    return boxes


def _remove_contained_boxes(boxes: List[BBox]) -> List[BBox]:
    """Elimina cajas que quedan (casi) totalmente dentro de otra caja mayor."""
    result = []
    for i, a in enumerate(boxes):
        ax, ay, aw, ah = a
        contained = False
        for j, b in enumerate(boxes):
            if i == j:
                continue
            bx, by, bw, bh = b
            if (bw * bh) <= (aw * ah):
                continue
            if (
                ax >= bx - 2
                and ay >= by - 2
                and ax + aw <= bx + bw + 2
                and ay + ah <= by + bh + 2
            ):
                contained = True
                break
        if not contained:
            result.append(a)
    return result
