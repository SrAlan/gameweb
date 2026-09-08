"Interfaz de revisión del análisis de paneles (Etapa 2)."
"""
Muestra cada panel (recorte) junto con la información generada por la IA,
en el orden de lectura confirmado por el usuario. Permite:
- Editar manualmente cualquier campo ("Editar" / "Guardar cambios").
- Reanalizar un panel individual ("Reanalizar panel").
- Navegar por todos los paneles: ← Panel anterior / Panel siguiente →.

La ventana no conoce detalles de la IA: delega el reanálisis en una
función callback (inyectada por MainWindow), manteniendo el sistema modular.
"""
import os
from typing import Callable, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QMessageBox,
    QScrollArea,
    QFrame,
)

from .models import Page, Panel
from .ai_analysis import empty_analysis

# campos lista -> QLineEdit separado por comas; campos texto -> QTextEdit
LIST_FIELDS = ("characters", "actions", "emotions")
TEXT_FIELDS = ("description", "dialogue", "important_details")

FIELD_LABELS = {
    "description": "Descripción:",
    "characters": "Personajes:",
    "actions": "Acciones:",
    "emotions": "Emociones:",
    "dialogue": "Diálogo:",
    "important_details": "Detalles importantes:",
}


class PanelAnalysisView(QFrame):
    """Vista de un panel: imagen + campos editables."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self.title_label = QLabel("<b>Panel</b>")
        layout.addWidget(self.title_label)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(320, 240)
        layout.addWidget(self.image_label)

        self.confidence_label = QLabel("")
        self.confidence_label.setWordWrap(True)
        self.confidence_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.confidence_label)

        self._inputs = {}
        for key in ("description", "characters", "actions", "emotions",
                    "dialogue", "important_details"):
            layout.addWidget(QLabel(FIELD_LABELS[key]))
            if key in LIST_FIELDS:
                widget = QLineEdit()
            else:
                widget = QTextEdit()
                widget.setFixedHeight(70)
            layout.addWidget(widget)
            self._inputs[key] = widget

        self.set_editable(False)

    # ------------------------------------------------------------------
    def set_editable(self, editable: bool):
        for widget in self._inputs.values():
            widget.setEnabled(editable)

    def _list_value(self, key: str) -> List[str]:
        raw = self._inputs[key].text().strip()
        if not raw:
            return []
        return [part.strip() for part in raw.split(",") if part.strip()]

    # ------------------------------------------------------------------
    def load_panel(self, page: Page, panel: Panel, index: int, total: int,
                   crop_path: Optional[str]):
        self.title_label.setText(
            f"<b>Panel {index + 1} de {total}</b> &nbsp;·&nbsp; id: {panel.id} "
            f"&nbsp;·&nbsp; página: {os.path.basename(page.image_path)}"
        )
        if crop_path and os.path.exists(crop_path):
            pix = QPixmap(crop_path)
            self.image_label.setPixmap(
                pix.scaled(500, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.image_label.setText("(recorte no disponible)")

        analysis = dict(panel.extra.get("analysis") or empty_analysis())
        for key in TEXT_FIELDS:
            self._inputs[key].setPlainText(str(analysis.get(key, "") or ""))
        for key in LIST_FIELDS:
            self._inputs[key].setText(", ".join(analysis.get(key) or []))
        self.show_confidence(analysis)

    def show_confidence(self, analysis: dict):
        conf = analysis.get("confidence") or {}
        parts = []
        for key in ("seen", "written", "inferred"):
            items = [str(x) for x in (conf.get(key) or []) if str(x).strip()]
            if items:
                name = {"seen": "Se ve claramente", "written": "Aparece escrito",
                        "inferred": "Inferido"}[key]
                parts.append(f"<b>{name}:</b> {', '.join(items)}")
        self.confidence_label.setText(" &nbsp;·&nbsp; ".join(parts))

    # ------------------------------------------------------------------
    def collect_analysis(self) -> dict:
        analysis = empty_analysis()
        for key in TEXT_FIELDS:
            analysis[key] = self._inputs[key].toPlainText().strip()
        for key in LIST_FIELDS:
            analysis[key] = self._list_value(key)
        return analysis


class AnalysisReviewWindow(QDialog):
    """Revisión paneles → datos estructurados, en orden de lectura."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Análisis de paneles — revisión")
        self.resize(760, 860)

        # lista plana, en orden de lectura, de tuplas (page, panel)
        self.items: List[tuple] = []
        self.crops: dict = {}          # panel_id -> ruta del recorte
        self.current_index: int = 0

        # callbacks inyectados por MainWindow
        self.on_save_analysis: Optional[Callable[[Page, Panel, dict], None]] = None
        self.on_reanalyze: Optional[Callable[[Page, Panel, "AnalysisReviewWindow"], None]] = None

        self._build_ui()
        self._show_current()

    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        # navegación
        nav = QHBoxLayout()
        self.btn_prev = QPushButton("← Panel anterior")
        self.btn_next = QPushButton("Panel siguiente →")
        self.pos_label = QLabel("Panel 0 de 0")
        self.pos_label.setAlignment(Qt.AlignCenter)
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.pos_label, 1)
        nav.addWidget(self.btn_next)
        layout.addLayout(nav)

        # vista con scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.panel_view = PanelAnalysisView()
        scroll.setWidget(self.panel_view)
        layout.addWidget(scroll, 1)

        # botones de acción
        actions = QHBoxLayout()
        self.btn_edit = QPushButton("✏ Editar")
        self.btn_save = QPushButton("💾 Guardar cambios")
        self.btn_save.setEnabled(False)
        self.btn_reanalyze = QPushButton("🔄 Reanalizar panel")
        actions.addWidget(self.btn_edit)
        actions.addWidget(self.btn_save)
        actions.addStretch(1)
        actions.addWidget(self.btn_reanalyze)
        layout.addLayout(actions)

        self.btn_prev.clicked.connect(self.go_prev)
        self.btn_next.clicked.connect(self.go_next)
        self.btn_edit.clicked.connect(self.toggle_edit)
        self.btn_save.clicked.connect(self.save_changes)
        self.btn_reanalyze.clicked.connect(self.reanalyze_current)

    # ------------------------------------------------------------------
    def set_data(self, items: List[tuple], crops: dict):
        """items: lista de (page, panel) en el orden de lectura confirmado."""
        self.items = items
        self.crops = crops or {}
        self.current_index = 0
        self._show_current()

    # ------------------------------------------------------------------
    def go_prev(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._show_current()

    def go_next(self):
        if self.current_index < len(self.items) - 1:
            self.current_index += 1
            self._show_current()

    def _show_current(self):
        total = len(self.items)
        if total == 0:
            self.pos_label.setText("No hay paneles")
            self.panel_view.title_label.setText("<b>Sin paneles</b>")
            return
        page, panel = self.items[self.current_index]
        self.panel_view.load_panel(
            page, panel, self.current_index, total,
            self.crops.get(panel.id),
        )
        self.panel_view.set_editable(False)
        self.btn_edit.setText("✏ Editar")
        self.btn_save.setEnabled(False)
        self.pos_label.setText(f"Panel {self.current_index + 1} de {total}")
        self.btn_prev.setEnabled(self.current_index > 0)
        self.btn_next.setEnabled(self.current_index < total - 1)

    # ------------------------------------------------------------------
    def toggle_edit(self):
        editing = self.btn_save.isEnabled()
        if editing:  # estaba editando: guardar y salir del modo edición
            self.save_changes()
        else:
            self.panel_view.set_editable(True)
            self.btn_save.setEnabled(True)
            self.btn_edit.setText("Cancelar edición")

    def save_changes(self):
        if not self.items:
            return
        page, panel = self.items[self.current_index]
        analysis = self.panel_view.collect_analysis()
        if self.on_save_analysis:
            self.on_save_analysis(page, panel, analysis)
        # refrescar vista
        self.panel_view.load_panel(
            page, panel, self.current_index, len(self.items),
            self.crops.get(panel.id),
        )
        self.panel_view.set_editable(False)
        self.btn_edit.setText("✏ Editar")
        self.btn_save.setEnabled(False)

    def reanalyze_current(self):
        if not self.items or self.on_reanalyze is None:
            return
        # guardar primero cualquier edición pendiente
        if self.btn_save.isEnabled():
            self.save_changes()
        page, panel = self.items[self.current_index]
        self.btn_reanalyze.setEnabled(False)
        self.btn_reanalyze.setText("⏳ Analizando…")
        try:
            self.on_reanalyze(page, panel, self)
        finally:
            self.btn_reanalyze.setEnabled(True)
            self.btn_reanalyze.setText("🔄 Reanalizar panel")

    # Llamado por MainWindow cuando termina el reanálisis de este panel
    def on_reanalysis_done(self, page: Page, panel: Panel, analysis: dict):
        if self.on_save_analysis:
            self.on_save_analysis(page, panel, analysis)
        self._show_current()

    def closeEvent(self, event):
        if self.btn_save.isEnabled():  # cambios sin guardar
            resp = QMessageBox.question(
                self, "Cambios sin guardar",
                "Hay cambios sin guardar en este panel. ¿Guardarlos antes de salir?",
            )
            if resp == QMessageBox.Yes:
                self.save_changes()
        event.accept()
