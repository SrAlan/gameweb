"""
Cálculo del orden de lectura sugerido para un conjunto de viñetas.

La estrategia por defecto imita la maquetación tradicional del manga:
las filas se leen de arriba hacia abajo, y dentro de cada fila las
viñetas se leen de derecha a izquierda. Esto es solo un punto de
partida: el usuario siempre puede arrastrar las viñetas a cualquier
posición en la lista de orden de la interfaz.
"""
from typing import List, Tuple

BBox = Tuple[float, float, float, float]  # x, y, w, h


def compute_reading_order(boxes: List[BBox], right_to_left: bool = True) -> List[int]:
    """Devuelve una lista de índices sobre `boxes` en el orden sugerido."""
    if not boxes:
        return []

    items = list(enumerate(boxes))
    items.sort(key=lambda it: it[1][1] + it[1][3] / 2)  # por centro vertical

    rows: List[List[Tuple[int, BBox]]] = []
    for idx, box in items:
        y_center = box[1] + box[3] / 2
        placed = False
        for row in rows:
            row_centers = [b[1] + b[3] / 2 for _, b in row]
            row_avg = sum(row_centers) / len(row_centers)
            row_heights = [b[3] for _, b in row]
            tolerance = max(row_heights + [box[3]]) * 0.5
            if abs(y_center - row_avg) <= tolerance:
                row.append((idx, box))
                placed = True
                break
        if not placed:
            rows.append([(idx, box)])

    rows.sort(key=lambda row: sum(b[1] + b[3] / 2 for _, b in row) / len(row))

    order: List[int] = []
    for row in rows:
        row.sort(key=lambda it: it[1][0], reverse=right_to_left)
        order.extend(idx for idx, _ in row)
    return order
