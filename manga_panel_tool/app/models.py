"""
Modelos de datos del proyecto.

Define las estructuras centrales (Panel, Page, Project) y su
serialización a/desde JSON.

Pensado para poder ampliarse sin romper el formato existente: tanto
`Panel` como `Page` tienen un diccionario `extra` donde los módulos
futuros (análisis con IA, OCR, resúmenes, rutas de audio, etc.) pueden
guardar su propia información sin tocar este archivo.
"""
import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any


@dataclass
class Panel:
    """Un panel (viñeta) dentro de una página.

    (x, y, w, h) están en coordenadas de píxel de la imagen original
    de la página (no de la vista en pantalla).
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    # Punto de extensión para módulos futuros: texto OCR, resumen del
    # panel, ruta de audio narrado, embeddings, etc.
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Panel":
        return Panel(
            id=d.get("id", uuid.uuid4().hex[:8]),
            x=float(d.get("x", 0.0)),
            y=float(d.get("y", 0.0)),
            w=float(d.get("w", 0.0)),
            h=float(d.get("h", 0.0)),
            extra=d.get("extra", {}) or {},
        )


@dataclass
class Page:
    """Una página del manga.

    El ORDEN de la lista `panels` ES el orden de lectura (índice 0 =
    primer panel a leer, índice 1 = segundo, etc). Reordenar la lista
    es la única fuente de verdad sobre el orden de lectura.
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    image_path: str = ""
    width: int = 0
    height: int = 0
    panels: List[Panel] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "image_path": self.image_path,
            "width": self.width,
            "height": self.height,
            "panels": [p.to_dict() for p in self.panels],
            "extra": self.extra,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Page":
        return Page(
            id=d.get("id", uuid.uuid4().hex[:8]),
            image_path=d.get("image_path", ""),
            width=int(d.get("width", 0)),
            height=int(d.get("height", 0)),
            panels=[Panel.from_dict(p) for p in d.get("panels", [])],
            extra=d.get("extra", {}) or {},
        )


@dataclass
class Project:
    version: int = 1
    pages: List[Page] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"version": self.version, "pages": [p.to_dict() for p in self.pages]}

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Project":
        return Project(
            version=d.get("version", 1),
            pages=[Page.from_dict(p) for p in d.get("pages", [])],
        )

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @staticmethod
    def load(path: str) -> "Project":
        with open(path, "r", encoding="utf-8") as f:
            return Project.from_dict(json.load(f))
