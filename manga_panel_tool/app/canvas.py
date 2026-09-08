"""
Componentes gráficos del lienzo central (QGraphicsScene/View).

- PanelItem: rectángulo interactivo que representa una viñeta. Se
  puede mover (arrastrando el cuerpo), redimensionar (arrastrando las
  esquinas) y seleccionar (clic / Ctrl+clic para selección múltiple,
  usada para unir viñetas).
- ArrowItem: flecha simple entre los centros de dos viñetas
  consecutivas, para visualizar el orden de lectura.
- PageGraphicsView: la QGraphicsView central. Gestiona el modo
  "herramienta" (seleccionar / crear viñeta nueva) y emite señales
  Qt hacia la ventana principal para que esta actualice el modelo de
  datos.
"""
import math
from typing import Dict, Optional

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QBrush, QColor, QPen, QPolygonF, QFont, QPainterPath
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
    QGraphicsItem,
    QGraphicsPathItem,
)

HANDLE_SIZE = 12
MIN_PANEL_SIZE = 15


class _Handle(QGraphicsRectItem):
    """Cuadradito en una esquina de un PanelItem, usado para redimensionarlo."""

    def __init__(self, corner: str, parent_panel: "PanelItem"):
        super().__init__(-HANDLE_SIZE / 2, -HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE, parent_panel)
        self.corner = corner
        self.panel = parent_panel
        self.setBrush(QBrush(QColor("#ffffff")))
        self.setPen(QPen(QColor("#1e88e5"), 2))
        self.setZValue(20)
        self.setAcceptHoverEvents(True)
        cursor = Qt.SizeFDiagCursor if corner in ("tl", "br") else Qt.SizeBDiagCursor
        self.setCursor(cursor)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, False)

    def mousePressEvent(self, event):
        event.accept()

    def mouseMoveEvent(self, event):
        self.panel.resize_from_handle(self.corner, event.scenePos())
        event.accept()

    def mouseReleaseEvent(self, event):
        self.panel.commit_change()
        event.accept()


class PanelItem(QGraphicsRectItem):
    """Rectángulo interactivo que representa una viñeta detectada o manual."""

    def __init__(self, panel_id: str, rect: QRectF):
        super().__init__(rect)
        self.panel_id = panel_id
        self.setAcceptHoverEvents(True)
        self.setZValue(5)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self._drag_start: Optional[QPointF] = None
        self._rect_start: Optional[QRectF] = None

        self.number_bg = QGraphicsRectItem(self)
        self.number_bg.setPen(QPen(Qt.NoPen))
        self.number_bg.setBrush(QBrush(QColor(20, 20, 20, 220)))
        self.number_bg.setZValue(15)

        self.number_text = QGraphicsSimpleTextItem(self)
        self.number_text.setBrush(QBrush(QColor("white")))
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        self.number_text.setFont(font)
        self.number_text.setZValue(16)

        self.handles: Dict[str, _Handle] = {
            c: _Handle(c, self) for c in ("tl", "tr", "bl", "br")
        }

        self._normal_pen = QPen(QColor("#e53935"), 3)
        self._selected_pen = QPen(QColor("#43a047"), 4)
        self.setPen(self._normal_pen)
        self.setBrush(QBrush(QColor(255, 235, 59, 40)))

        self.update_decorations()

    # ---- apariencia -----------------------------------------------
    def set_number(self, n: int):
        self.number_text.setText(str(n))
        self.update_decorations()

    def set_selected_look(self, selected: bool):
        self.setPen(self._selected_pen if selected else self._normal_pen)
        for h in self.handles.values():
            h.setVisible(selected)

    def update_decorations(self):
        r = self.rect()
        pad = 4
        tw = self.number_text.boundingRect().width()
        th = self.number_text.boundingRect().height()
        bx, by = r.x() + 6, r.y() + 6
        self.number_bg.setRect(bx - pad, by - pad, tw + 2 * pad, th + 2 * pad)
        self.number_text.setPos(bx, by)

        positions = {
            "tl": r.topLeft(),
            "tr": r.topRight(),
            "bl": r.bottomLeft(),
            "br": r.bottomRight(),
        }
        for corner, pos in positions.items():
            self.handles[corner].setPos(pos)

    def center(self) -> QPointF:
        return self.rect().center()

    # ---- interacción: mover el cuerpo ------------------------------
    def mousePressEvent(self, event):
        scene = self.scene()
        if event.modifiers() & Qt.ControlModifier:
            self.setSelected(not self.isSelected())
            if scene:
                scene.selection_changed_callback()
            event.accept()
            return

        if scene:
            for other in list(scene.selectedItems()):
                if other is not self:
                    other.setSelected(False)
        self.setSelected(True)
        if scene:
            scene.selection_changed_callback()
        self._drag_start = event.scenePos()
        self._rect_start = QRectF(self.rect())
        event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_start is not None and self._rect_start is not None:
            delta = event.scenePos() - self._drag_start
            new_rect = QRectF(self._rect_start)
            new_rect.translate(delta)
            self.setRect(new_rect)
            self.update_decorations()
        event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        self._rect_start = None
        self.commit_change()
        event.accept()

    def commit_change(self):
        scene = self.scene()
        if scene and hasattr(scene, "panel_changed_callback"):
            scene.panel_changed_callback(self.panel_id, self.rect())

    # ---- redimensionar desde una esquina ---------------------------
    def resize_from_handle(self, corner: str, scene_pos: QPointF):
        r = QRectF(self.rect())
        if corner == "tl":
            r.setTopLeft(scene_pos)
        elif corner == "tr":
            r.setTopRight(scene_pos)
        elif corner == "bl":
            r.setBottomLeft(scene_pos)
        elif corner == "br":
            r.setBottomRight(scene_pos)
        r = r.normalized()
        if r.width() >= MIN_PANEL_SIZE and r.height() >= MIN_PANEL_SIZE:
            self.setRect(r)
            self.update_decorations()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.set_selected_look(bool(value))
        return super().itemChange(change, value)


def make_arrow_path(p1: QPointF, p2: QPointF) -> QPainterPath:
    """Crea el QPainterPath de una flecha (línea + punta triangular) de p1 a p2."""
    path = QPainterPath(p1)
    path.lineTo(p2)

    angle = math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
    arrow_size = 14
    a1 = p2 - QPointF(
        math.cos(angle - math.pi / 7) * arrow_size,
        math.sin(angle - math.pi / 7) * arrow_size,
    )
    a2 = p2 - QPointF(
        math.cos(angle + math.pi / 7) * arrow_size,
        math.sin(angle + math.pi / 7) * arrow_size,
    )
    head = QPolygonF([p2, a1, a2])
    path.addPolygon(head)
    return path


class ArrowItem(QGraphicsPathItem):
    """Flecha visual entre los centros de dos viñetas consecutivas."""

    def __init__(self, p1: QPointF, p2: QPointF):
        super().__init__(make_arrow_path(p1, p2))
        self.setPen(QPen(QColor("#1e88e5"), 3))
        self.setBrush(QBrush(QColor("#1e88e5")))
        self.setZValue(3)


class PageScene(QGraphicsScene):
    """Escena con callbacks hacia la ventana principal (inyectados por ella)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.panel_changed_callback = lambda panel_id, rect: None
        self.selection_changed_callback = lambda: None


class PageGraphicsView(QGraphicsView):
    """Vista central que muestra la página y permite crear viñetas nuevas."""

    panel_rect_created = Signal(QRectF)

    def __init__(self, scene: PageScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(self.renderHints())
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.mode = "select"  # "select" | "add_panel"
        self._draft_item: Optional[QGraphicsRectItem] = None
        self._draft_start: Optional[QPointF] = None

    def set_mode(self, mode: str):
        self.mode = mode
        self.setDragMode(
            QGraphicsView.NoDrag if mode == "add_panel" else QGraphicsView.RubberBandDrag
        )

    def mousePressEvent(self, event):
        if self.mode == "add_panel" and event.button() == Qt.LeftButton:
            self._draft_start = self.mapToScene(event.pos())
            self._draft_item = QGraphicsRectItem(QRectF(self._draft_start, self._draft_start))
            self._draft_item.setPen(QPen(QColor("#43a047"), 3, Qt.DashLine))
            self._draft_item.setBrush(QBrush(QColor(67, 160, 71, 60)))
            self.scene().addItem(self._draft_item)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.mode == "add_panel" and self._draft_item is not None and self._draft_start is not None:
            current = self.mapToScene(event.pos())
            self._draft_item.setRect(QRectF(self._draft_start, current).normalized())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.mode == "add_panel" and self._draft_item is not None:
            rect = self._draft_item.rect()
            self.scene().removeItem(self._draft_item)
            self._draft_item = None
            self._draft_start = None
            if rect.width() >= MIN_PANEL_SIZE and rect.height() >= MIN_PANEL_SIZE:
                self.panel_rect_created.emit(rect)
            event.accept()
            return
        super().mouseReleaseEvent(event)
