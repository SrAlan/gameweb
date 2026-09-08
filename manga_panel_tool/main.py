"""
Manga Panel Analyzer — Prototipo v1

Flujo de esta primera versión:
    CARGAR PÁGINAS -> DETECTAR VIÑETAS -> CORREGIR VIÑETAS -> ORDENAR -> GUARDAR JSON

Ejecutar con:
    python main.py

Ver README.md para instrucciones de instalación completas.
"""
import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Manga Panel Analyzer")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
