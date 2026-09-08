"""
Ventana principal de la aplicación.

Orquesta el modelo de datos (models.Project), la detección automática
(detection.detect_panels), el cálculo de orden por defecto
(ordering.compute_reading_order) y los widgets de interfaz (canvas.py).

Estructura de la interfaz:
- Barra de herramientas superior: cargar páginas, detectar, crear /
  eliminar / dividir / unir viñetas, mostrar flechas, guardar/abrir
  proyecto, navegación entre páginas.
- Panel lateral izquierdo: lista de páginas cargadas (miniaturas).
- Área central: la página actual con los recuadros de viñetas.
- Panel lateral derecho: lista del orden de lectura actual,
  reordenable arrastrando (drag & drop).
"""
import os
from typing import List, Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPixmap, QIcon, QImage, QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QToolBar,
    QFileDialog,
    QMessageBox,
    QCheckBox,
    QSplitter,
    QPushButton,
    QAbstractItemView,
    QStatusBar,
)

from PySide6.QtCore import QThread, Signal

from .models import Project, Page, Panel
from .detection import detect_panels
from .ordering import compute_reading_order
from .canvas import PageScene, PageGraphicsView, PanelItem, ArrowItem
from .ai_analysis import get_provider, empty_analysis
from .panel_crops import ensure_crops
from .analysis_review import AnalysisReviewWindow

THUMB_SIZE = 120


class AnalysisWorker(QThread):
    """Ejecuta el análisis por IA de varios paneles en segundo plano.

    jobs: lista de dicts {"page", "panel", "crop_path", "index", "total"}
    """

    panel_done = Signal(object, object, dict)   # page, panel, analysis|{"error":...}
    finished_all = Signal()

    def __init__(self, provider, jobs, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.jobs = jobs
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        for job in self.jobs:
            if self._cancelled:
                break
            page = job["page"]
            panel = job["panel"]
            try:
                label = f"página {os.path.basename(page.image_path)}"
                analysis = self.provider.analyze_panel_image(
                    job["crop_path"], label, job["index"], job["total"]
                )
                if not analysis.get("confidence"):
                    analysis["confidence"] = {"seen": [], "written": [], "inferred": []}
            except Exception as exc:  # noqa: BLE001
                analysis = {"error": str(exc)}
            self.panel_done.emit(page, panel, analysis)
        self.finished_all.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Manga Panel Analyzer — Prototipo")
        self.resize(1400, 900)

        self.project = Project()
        self.current_page_index: int = -1
        self.current_pixmap: Optional[QPixmap] = None
        self.panel_items: dict = {}  # panel_id -> PanelItem
        self.arrow_items: List[ArrowItem] = []
        self.show_arrows = True
        self._syncing_order_list = False

        # --- Etapa 2: análisis con IA ---
        self.analysis_review_window: Optional[AnalysisReviewWindow] = None
        self.analysis_worker: Optional[AnalysisWorker] = None
        self.crops_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "panel_crops")
        self.crops_cache: dict = {}   # page_id -> {panel_id: crop_path}

        self._build_ui()
        self._build_toolbar()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def _build_ui(self):
        # --- panel izquierdo: páginas ---
        self.page_list = QListWidget()
        self.page_list.setIconSize(QPixmap(THUMB_SIZE, THUMB_SIZE).size())
        self.page_list.currentRowChanged.connect(self.on_page_selected)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.addWidget(QLabel("<b>Páginas cargadas</b>"))
        left_layout.addWidget(self.page_list)

        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("◀ Anterior")
        self.btn_next = QPushButton("Siguiente ▶")
        self.btn_prev.clicked.connect(self.go_prev_page)
        self.btn_next.clicked.connect(self.go_next_page)
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        left_layout.addLayout(nav_layout)

        # --- centro: lienzo ---
        self.scene = PageScene()
        self.scene.panel_changed_callback = self.on_panel_geometry_changed
        self.scene.selection_changed_callback = self.on_selection_changed
        self.view = PageGraphicsView(self.scene)
        self.view.panel_rect_created.connect(self.on_new_panel_rect)

        # --- panel derecho: orden de lectura ---
        self.order_list = QListWidget()
        self.order_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.order_list.setDefaultDropAction(Qt.MoveAction)
        self.order_list.model().rowsMoved.connect(self.on_order_list_reordered)
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.addWidget(QLabel("<b>Orden de lectura</b> (arrastra para reordenar)"))
        right_layout.addWidget(self.order_list)

        splitter = QSplitter()
        splitter.addWidget(left_container)
        splitter.addWidget(self.view)
        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 1)
        self.setCentralWidget(splitter)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Carga una o varias páginas para empezar.")

    def _build_toolbar(self):
        tb = QToolBar("Herramientas")
        tb.setMovable(False)
        self.addToolBar(tb)

        act_load = QAction("📂 Cargar páginas", self)
        act_load.triggered.connect(self.load_images)
        tb.addAction(act_load)

        act_detect = QAction("🔍 Detectar viñetas", self)
        act_detect.triggered.connect(self.run_detection_current_page)
        tb.addAction(act_detect)

        tb.addSeparator()

        self.act_add = QAction("➕ Nueva viñeta", self)
        self.act_add.setCheckable(True)
        self.act_add.toggled.connect(self.toggle_add_mode)
        tb.addAction(self.act_add)

        act_delete = QAction("🗑 Eliminar", self)
        act_delete.triggered.connect(self.delete_selected)
        tb.addAction(act_delete)

        act_split_v = QAction("✂ Dividir vertical", self)
        act_split_v.triggered.connect(lambda: self.split_selected("vertical"))
        tb.addAction(act_split_v)

        act_split_h = QAction("✂ Dividir horizontal", self)
        act_split_h.triggered.connect(lambda: self.split_selected("horizontal"))
        tb.addAction(act_split_h)

        act_merge = QAction("🔗 Unir viñetas", self)
        act_merge.triggered.connect(self.merge_selected)
        tb.addAction(act_merge)

        tb.addSeparator()

        self.chk_arrows = QCheckBox("Mostrar flechas de orden")
        self.chk_arrows.setChecked(True)
        self.chk_arrows.stateChanged.connect(self.toggle_arrows)
        tb.addWidget(self.chk_arrows)

        tb.addSeparator()

        act_open = QAction("📁 Abrir proyecto", self)
        act_open.triggered.connect(self.open_project)
        tb.addAction(act_open)

        act_save = QAction("💾 Guardar proyecto", self)
        act_save.triggered.connect(self.save_project)
        tb.addAction(act_save)

        tb.addSeparator()

        act_analyze = QAction("🧠 Analizar paneles", self)
        act_analyze.triggered.connect(self.start_panel_analysis)
        tb.addAction(act_analyze)

    # ------------------------------------------------------------------
    # Etapa 2: análisis de paneles con IA
    # ------------------------------------------------------------------
    def start_panel_analysis(self):
        """Analiza con IA todos los paneles, en el orden de lectura confirmado."""
        if not self.project.pages:
            QMessageBox.information(self, "Analizar", "Primero carga alguna página.")
            return
        total_panels = sum(len(p.panels) for p in self.project.pages)
        if total_panels == 0:
            QMessageBox.information(
                self, "Analizar", "No hay viñetas. Detecta o dibuja viñetas primero."
            )
            return
        if self.analysis_worker is not None and self.analysis_worker.isRunning():
            QMessageBox.information(self, "Analizar", "Ya hay un análisis en curso.")
            return

        try:
            provider = get_provider()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Proveedor de IA",
                f"No se pudo configurar el proveedor de IA:\n{exc}\n\n"
                "Configura OPENAI_API_KEY o GEMINI_API_KEY en el entorno.",
            )
            return

        # recortes (solo los recortes se envían a la IA; las imágenes
        # originales se conservan intactas)
        self.crops_cache = {}
        jobs = []
        running = 0
        for page in self.project.pages:
            try:
                crops = ensure_crops(page, self.crops_dir)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Analizar", f"Error al recortar paneles:\n{exc}")
                return
            self.crops_cache[page.id] = crops
            for panel in page.panels:
                crop = crops.get(panel.id)
                if not crop:
                    continue
                running += 1
                jobs.append({
                    "page": page,
                    "panel": panel,
                    "crop_path": crop,
                    "index": running,
                    "total": total_panels,
                })

        reply = QMessageBox.question(
            self, "Analizar paneles",
            f"Se enviarán {len(jobs)} paneles al proveedor de IA "
            f"'{provider.name}'.\n¿Continuar?",
        )
        if reply != QMessageBox.Yes:
            return

        self.statusBar().showMessage(f"Analizando 0/{len(jobs)} paneles…")
        self.analysis_worker = AnalysisWorker(provider, jobs, self)
        self.analysis_worker.panel_done.connect(self.on_panel_analyzed)
        self.analysis_worker.finished_all.connect(self.on_analysis_finished)
        self.analysis_worker.start()

    def on_panel_analyzed(self, page, panel, result):
        if "error" in result:
            self.statusBar().showMessage(
                f"Error analizando panel {panel.id}: {result['error']}", 8000
            )
            return
        panel.extra["analysis"] = result
        done = sum(
            1
            for p in self.project.pages
            for pl in p.panels
            if pl.extra.get("analysis")
        )
        self.statusBar().showMessage(
            f"Analizando paneles… ({done} con análisis)"
        )

    def on_analysis_finished(self):
        self.statusBar().showMessage("Análisis completado.")
        self.open_analysis_review()

    def _flat_panels_in_order(self):
        """Lista plana de (page, panel) siguiendo el orden de lectura de
        todas las páginas del proyecto (la confirmada por el usuario)."""
        flat = []
        for page in self.project.pages:
            for panel in page.panels:
                flat.append((page, panel))
        return flat

    def open_analysis_review(self):
        flat = self._flat_panels_in_order()
        crops = {}
        for page_id, page_crops in self.crops_cache.items():
            crops.update(page_crops)
        if self.analysis_review_window is None:
            self.analysis_review_window = AnalysisReviewWindow(self)
            self.analysis_review_window.on_save_analysis = self._store_analysis
            self.analysis_review_window.on_reanalyze = self._reanalyze_single_panel
        self.analysis_review_window.set_data(flat, crops)
        self.analysis_review_window.show()
        self.analysis_review_window.raise_()
        self.analysis_review_window.activateWindow()

    def _store_analysis(self, page, panel, analysis):
        panel.extra["analysis"] = analysis

    def _reanalyze_single_panel(self, page, panel, review_window):
        """Reenvía SOLO este panel a la IA y actualiza la revisión al acabar."""
        crops = self.crops_cache.get(page.id)
        if not crops:
            try:
                crops = ensure_crops(page, self.crops_dir)
                self.crops_cache[page.id] = crops
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Reanalizar", f"Error al recortar:\n{exc}")
                return
        crop = crops.get(panel.id)
        if not crop:
            QMessageBox.warning(self, "Reanalizar", "Recorte del panel no disponible.")
            return

        try:
            provider = get_provider()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Proveedor de IA", str(exc))
            return

        total = sum(len(p.panels) for p in self.project.pages)
        idx = next(
            (i for i, (pg, pl) in enumerate(self._flat_panels_in_order()) if pl.id == panel.id),
            0,
        ) + 1
        try:
            result = provider.analyze_panel_image(crop, os.path.basename(page.image_path), idx, total)
            if not result.get("confidence"):
                result["confidence"] = {"seen": [], "written": [], "inferred": []}
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Reanalizar", f"Error del proveedor de IA:\n{exc}")
            return
        review_window.on_reanalysis_done(page, panel, result)

    # ------------------------------------------------------------------
    # Carga de páginas
    # ------------------------------------------------------------------
    def load_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecciona una o varias páginas de manga",
            "",
            "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not paths:
            return

        for path in paths:
            img = QImage(path)
            if img.isNull():
                continue
            page = Page(image_path=path, width=img.width(), height=img.height())
            self.project.pages.append(page)

            item = QListWidgetItem(os.path.basename(path))
            thumb = QPixmap.fromImage(img).scaled(
                THUMB_SIZE, THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            item.setIcon(QIcon(thumb))
            self.page_list.addItem(item)

            self._detect_for_page(page)

        if self.current_page_index == -1:
            self.page_list.setCurrentRow(0)
        self.statusBar().showMessage(f"{len(paths)} página(s) cargada(s) y analizada(s).")

    def run_detection_current_page(self):
        """Vuelve a ejecutar la detección automática sobre la página actual,
        descartando cualquier corrección manual hecha en ella."""
        page = self.current_page()
        if page is None:
            QMessageBox.information(self, "Detectar", "Primero carga alguna página.")
            return
        if page.panels:
            resp = QMessageBox.question(
                self,
                "Detectar viñetas",
                "Esto reemplazará las viñetas actuales de esta página por una nueva "
                "detección automática. ¿Continuar?",
            )
            if resp != QMessageBox.Yes:
                return
        self._detect_for_page(page)
        self.show_current_page()

    def _detect_for_page(self, page: Page):
        boxes = detect_panels(page.image_path)
        order = compute_reading_order(boxes)
        panels = []
        for idx in order:
            x, y, w, h = boxes[idx]
            panels.append(Panel(x=x, y=y, w=w, h=h))
        page.panels = panels

    # ------------------------------------------------------------------
    # Mostrar / cambiar de página
    # ------------------------------------------------------------------
    def on_page_selected(self, row: int):
        if row < 0 or row >= len(self.project.pages):
            return
        self.current_page_index = row
        self.show_current_page()

    def go_prev_page(self):
        if self.current_page_index > 0:
            self.page_list.setCurrentRow(self.current_page_index - 1)

    def go_next_page(self):
        if self.current_page_index < len(self.project.pages) - 1:
            self.page_list.setCurrentRow(self.current_page_index + 1)

    def current_page(self) -> Optional[Page]:
        if 0 <= self.current_page_index < len(self.project.pages):
            return self.project.pages[self.current_page_index]
        return None

    def show_current_page(self):
        page = self.current_page()
        if page is None:
            return

        self.scene.clear()
        self.panel_items = {}
        self.arrow_items = []

        pix = QPixmap(page.image_path)
        self.current_pixmap = pix
        self.scene.addPixmap(pix)
        self.scene.setSceneRect(0, 0, pix.width(), pix.height())
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

        for panel in page.panels:
            self._create_panel_item(panel)

        self.refresh_numbers_and_order_list()
        self.statusBar().showMessage(
            f"Página {self.current_page_index + 1}/{len(self.project.pages)} — "
            f"{len(page.panels)} viñeta(s)"
        )

    def _create_panel_item(self, panel: Panel) -> PanelItem:
        rect = QRectF(panel.x, panel.y, panel.w, panel.h)
        item = PanelItem(panel.id, rect)
        item.set_selected_look(False)
        self.scene.addItem(item)
        self.panel_items[panel.id] = item
        return item

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_pixmap is not None:
            self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    # ------------------------------------------------------------------
    # Sincronización datos <-> lista de orden <-> lienzo
    # ------------------------------------------------------------------
    def refresh_numbers_and_order_list(self):
        page = self.current_page()
        if page is None:
            return

        # números sobre el lienzo
        for idx, panel in enumerate(page.panels, start=1):
            item = self.panel_items.get(panel.id)
            if item:
                item.set_number(idx)

        # lista de orden (derecha) — marca los paneles ya analizados
        self._syncing_order_list = True
        self.order_list.clear()
        for idx, panel in enumerate(page.panels, start=1):
            mark = " 🧠" if panel.extra.get("analysis") else ""
            text = f"{idx}.  Viñeta {panel.id}   ({int(panel.w)}×{int(panel.h)} px){mark}"
            list_item = QListWidgetItem(text)
            list_item.setData(Qt.UserRole, panel.id)
            self.order_list.addItem(list_item)
        self._syncing_order_list = False

        self._redraw_arrows()

    def _redraw_arrows(self):
        for arrow in self.arrow_items:
            self.scene.removeItem(arrow)
        self.arrow_items = []

        if not self.show_arrows:
            return

        page = self.current_page()
        if page is None:
            return

        centers = []
        for panel in page.panels:
            item = self.panel_items.get(panel.id)
            if item:
                centers.append(item.center())

        for p1, p2 in zip(centers, centers[1:]):
            arrow = ArrowItem(p1, p2)
            self.scene.addItem(arrow)
            self.arrow_items.append(arrow)

    def toggle_arrows(self, state):
        self.show_arrows = state == Qt.Checked.value or state == 2
        self._redraw_arrows()

    def on_order_list_reordered(self, *args):
        """El usuario arrastró un elemento en la lista de orden: sincroniza el modelo."""
        if self._syncing_order_list:
            return
        page = self.current_page()
        if page is None:
            return

        new_order_ids = [
            self.order_list.item(i).data(Qt.UserRole) for i in range(self.order_list.count())
        ]
        id_to_panel = {p.id: p for p in page.panels}
        page.panels = [id_to_panel[pid] for pid in new_order_ids if pid in id_to_panel]
        self.refresh_numbers_and_order_list()

    def on_panel_geometry_changed(self, panel_id: str, rect: QRectF):
        """El usuario movió o redimensionó una viñeta en el lienzo."""
        page = self.current_page()
        if page is None:
            return
        for panel in page.panels:
            if panel.id == panel_id:
                panel.x, panel.y, panel.w, panel.h = rect.x(), rect.y(), rect.width(), rect.height()
                break
        self._redraw_arrows()

    def on_selection_changed(self):
        pass  # punto de extensión (p.ej. resaltar en la lista de orden)

    # ------------------------------------------------------------------
    # Herramientas: crear / eliminar / dividir / unir
    # ------------------------------------------------------------------
    def toggle_add_mode(self, checked: bool):
        self.view.set_mode("add_panel" if checked else "select")
        self.statusBar().showMessage(
            "Modo 'Nueva viñeta': dibuja un recuadro sobre el lienzo."
            if checked
            else "Modo selección."
        )

    def on_new_panel_rect(self, rect: QRectF):
        page = self.current_page()
        if page is None:
            return
        panel = Panel(x=rect.x(), y=rect.y(), w=rect.width(), h=rect.height())
        page.panels.append(panel)
        self._create_panel_item(panel)
        self.refresh_numbers_and_order_list()
        self.act_add.setChecked(False)

    def _selected_panel_ids(self) -> List[str]:
        return [
            item.panel_id for item in self.scene.selectedItems() if isinstance(item, PanelItem)
        ]

    def delete_selected(self):
        page = self.current_page()
        if page is None:
            return
        ids = self._selected_panel_ids()
        if not ids:
            QMessageBox.information(self, "Eliminar", "Selecciona primero una o más viñetas.")
            return
        for pid in ids:
            item = self.panel_items.pop(pid, None)
            if item:
                self.scene.removeItem(item)
        page.panels = [p for p in page.panels if p.id not in ids]
        self.refresh_numbers_and_order_list()

    def split_selected(self, orientation: str):
        page = self.current_page()
        if page is None:
            return
        ids = self._selected_panel_ids()
        if len(ids) != 1:
            QMessageBox.information(
                self, "Dividir", "Selecciona exactamente una viñeta para dividirla."
            )
            return
        pid = ids[0]
        idx = next((i for i, p in enumerate(page.panels) if p.id == pid), None)
        if idx is None:
            return
        panel = page.panels[idx]

        if orientation == "vertical":
            half_w = panel.w / 2
            p1 = Panel(x=panel.x, y=panel.y, w=half_w, h=panel.h)
            p2 = Panel(x=panel.x + half_w, y=panel.y, w=panel.w - half_w, h=panel.h)
        else:
            half_h = panel.h / 2
            p1 = Panel(x=panel.x, y=panel.y, w=panel.w, h=half_h)
            p2 = Panel(x=panel.x, y=panel.y + half_h, w=panel.w, h=panel.h - half_h)

        old_item = self.panel_items.pop(pid, None)
        if old_item:
            self.scene.removeItem(old_item)

        page.panels[idx : idx + 1] = [p1, p2]
        self._create_panel_item(p1)
        self._create_panel_item(p2)
        self.refresh_numbers_and_order_list()
        self.statusBar().showMessage(
            "Viñeta dividida. Ajusta los bordes arrastrando las esquinas si hace falta."
        )

    def merge_selected(self):
        page = self.current_page()
        if page is None:
            return
        ids = self._selected_panel_ids()
        if len(ids) < 2:
            QMessageBox.information(
                self, "Unir", "Selecciona al menos dos viñetas (Ctrl+clic) para unirlas."
            )
            return

        indices = [i for i, p in enumerate(page.panels) if p.id in ids]
        insert_at = min(indices)
        selected_panels = [p for p in page.panels if p.id in ids]

        min_x = min(p.x for p in selected_panels)
        min_y = min(p.y for p in selected_panels)
        max_x = max(p.x + p.w for p in selected_panels)
        max_y = max(p.y + p.h for p in selected_panels)
        merged = Panel(x=min_x, y=min_y, w=max_x - min_x, h=max_y - min_y)

        for pid in ids:
            item = self.panel_items.pop(pid, None)
            if item:
                self.scene.removeItem(item)

        page.panels = [p for p in page.panels if p.id not in ids]
        page.panels.insert(min(insert_at, len(page.panels)), merged)
        self._create_panel_item(merged)
        self.refresh_numbers_and_order_list()

    # ------------------------------------------------------------------
    # Guardar / abrir proyecto
    # ------------------------------------------------------------------
    def save_project(self):
        if not self.project.pages:
            QMessageBox.information(self, "Guardar", "No hay páginas que guardar todavía.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar proyecto", "proyecto_manga.json", "JSON (*.json)"
        )
        if not path:
            return
        self.project.save(path)
        self.statusBar().showMessage(f"Proyecto guardado en {path}")

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir proyecto", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            self.project = Project.load(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error al abrir", str(exc))
            return

        self.page_list.clear()
        for page in self.project.pages:
            item = QListWidgetItem(os.path.basename(page.image_path))
            if os.path.exists(page.image_path):
                thumb = QPixmap(page.image_path).scaled(
                    THUMB_SIZE, THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                item.setIcon(QIcon(thumb))
            self.page_list.addItem(item)

        self.current_page_index = -1
        if self.project.pages:
            self.page_list.setCurrentRow(0)
        self.statusBar().showMessage(f"Proyecto cargado: {path}")
