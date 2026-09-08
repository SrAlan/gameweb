"Etapa 3: interfaz de guion de video resumen y diapositivas."
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
    QTextEdit,
    QDoubleSpinBox,
    QMessageBox,
    QScrollArea,
    QFrame,
    QFileDialog,
    QInputDialog,
)

from .models import Page, Panel
from .video_script import (
    compute_duration,
    export_slides,
    export_script_txt,
    total_duration,
    format_timecode,
)


class SlideRow(QFrame):
    """Fila editable de una diapositiva: miniatura + texto + duración."""

    def __init__(self, slide: dict, index: int, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.slide = slide

        layout = QHBoxLayout(self)
        self.image_label = QLabel()
        self.image_label.setFixedWidth(220)
        self.image_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.image_label)

        right = QVBoxLayout()
        header = QLabel(f"<b>Diapositiva {index}</b> · panel de {slide['page']}")
        right.addWidget(header)

        self.text_edit = QTextEdit()
        self.text_edit.setFixedHeight(70)
        self.text_edit.setPlainText(slide["text"])
        right.addWidget(self.text_edit)

        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Duración (s):"))
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(1.0, 120.0)
        self.duration_spin.setSingleStep(0.5)
        self.duration_spin.setValue(slide["duration"])
        dur_row.addWidget(self.duration_spin)
        dur_row.addStretch(1)
        self.btn_reclock = QPushButton("⏱ Recalcular por texto")
        dur_row.addWidget(self.btn_reclock)
        right.addLayout(dur_row)

        layout.addLayout(right, 1)

        self.btn_reclock.clicked.connect(self.recalculate)
        self.text_edit.textChanged.connect(self._on_text_changed)
        self._on_text_changed()

        pix_path = slide.get("image_path") or ""
        if pix_path and os.path.exists(pix_path):
            self.image_label.setPixmap(
                QPixmap(pix_path).scaled(
                    220, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        else:
            self.image_label.setText("(sin imagen)")

    def _on_text_changed(self):
        pass  # la duración solo se recalcula con el botón (no molestar mientras escribe)

    def recalculate(self):
        self.duration_spin.setValue(compute_duration(self.text_edit.toPlainText()))

    def apply(self):
        """Escribe los valores de la fila de vuelta al diccionario slide."""
        self.slide["text"] = self.text_edit.toPlainText().strip()
        self.slide["duration"] = round(self.duration_spin.value(), 1)


class VideoScriptWindow(QDialog):
    """Ventana para revisar el guion y exportar diapositivas + guion .txt."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guion de video resumen — diapositivas")
        self.resize(900, 800)

        self.slides: List[dict] = []
        self.synopsis: str = ""
        self.rows: List[SlideRow] = []
        self.synopsis_source = ""   # "ia" | "local"

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # sinopsis
        layout.addWidget(QLabel("<b>Sinopsis (narración de apertura del video)</b>"))
        self.synopsis_edit = QTextEdit()
        self.synopsis_edit.setFixedHeight(90)
        self.synopsis_edit.setPlaceholderText(
            "Sinopsis del resumen. Se genera sola con IA (si hay API key) "
            "o a partir de los análisis; también puedes escribirla."
        )
        layout.addWidget(self.synopsis_edit)

        # lista de diapositivas
        layout.addWidget(QLabel("<b>Diapositivas (en orden de lectura)</b>"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.slides_container = QFrame()
        self.slides_layout = QVBoxLayout(self.slides_container)
        self.slides_layout.addStretch(1)
        scroll.setWidget(self.slides_container)
        layout.addWidget(scroll, 1)

        self.total_label = QLabel("Duración total: 00:00")
        layout.addWidget(self.total_label)

        # acciones
        actions = QHBoxLayout()
        self.btn_regen_synopsis = QPushButton("🧠 Regenerar sinopsis con IA")
        self.btn_export_slides = QPushButton("🖼 Exportar diapositivas (PNG)")
        self.btn_export_script = QPushButton("📄 Exportar guion (.txt)")
        actions.addWidget(self.btn_regen_synopsis)
        actions.addStretch(1)
        actions.addWidget(self.btn_export_slides)
        actions.addWidget(self.btn_export_script)
        layout.addLayout(actions)

        self.btn_export_slides.clicked.connect(self.export_slides_dialog)
        self.btn_export_script.clicked.connect(self.export_script_dialog)
        self.btn_regen_synopsis.clicked.connect(self._regen_synopsis)

        # callback inyectado por MainWindow
        self.on_regenerate_synopsis: Optional[Callable[["VideoScriptWindow"], None]] = None

    # ------------------------------------------------------------------
    def set_data(self, slides: List[dict], synopsis: str = "", synopsis_source: str = ""):
        self.slides = slides
        self.synopsis = synopsis
        self.synopsis_source = synopsis_source
        self.synopsis_edit.setPlainText(synopsis)
        self._rebuild_rows()

    def _rebuild_rows(self):
        for row in self.rows:
            row.setParent(None)
            row.deleteLater()
        self.rows = []
        for i, slide in enumerate(self.slides, start=1):
            row = SlideRow(slide, i)
            self.slides_layout.insertWidget(self.slides_layout.count() - 1, row)
            self.rows.append(row)
        self._update_total()

    def _update_total(self):
        self.total_label.setText(
            f"Duración total: {format_timecode(total_duration(self.slides))} "
            f"({total_duration(self.slides)} s)"
        )

    def collect(self):
        """Guarda el contenido de la UI en self.slides / self.synopsis."""
        self.synopsis = self.synopsis_edit.toPlainText().strip()
        for row in self.rows:
            row.apply()
        self._update_total()

    def _regen_synopsis(self):
        if self.on_regenerate_synopsis is None:
            QMessageBox.information(
                self, "Sinopsis", "No hay proveedor de IA disponible."
            )
            return
        self.collect()
        self.on_regenerate_synopsis(self)

    def apply_synopsis(self, synopsis: str, source: str):
        self.synopsis = synopsis
        self.synopsis_source = source
        self.synopsis_edit.setPlainText(synopsis)

    # ------------------------------------------------------------------
    def export_script_dialog(self):
        self.collect()
        if not self.slides:
            QMessageBox.information(self, "Exportar", "No hay diapositivas que exportar.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar guion", "guion_video.txt", "Texto (*.txt)"
        )
        if not path:
            return
        try:
            export_script_txt(self.slides, path, synopsis=self.synopsis)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Exportar guion", f"Error:\n{exc}")
            return
        QMessageBox.information(self, "Exportar guion", f"Guion guardado en:\n{path}")

    def export_slides_dialog(self):
        self.collect()
        if not self.slides:
            QMessageBox.information(self, "Exportar", "No hay diapositivas que exportar.")
            return
        out_dir = QFileDialog.getExistingDirectory(
            self, "Carpeta para las diapositivas", ""
        )
        if not out_dir:
            return
        try:
            paths = export_slides(self.slides, out_dir)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Exportar diapositivas", f"Error:\n{exc}")
            return
        QMessageBox.information(
            self, "Exportar diapositivas",
            f"{len(paths)} diapositivas exportadas en:\n{out_dir}"
        )
