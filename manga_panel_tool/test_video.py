from PySide6.QtGui import QGuiApplication
app = QGuiApplication([])

from app.models import Project
from app.video_script import collect_slides, export_script_txt, export_slides, total_duration, format_timecode
from app.panel_crops import ensure_crops

p = Project.load("proyecto_manga.json")
crops = {}
for page in p.pages:
    try:
        crops[page.id] = ensure_crops(page, "panel_crops")
    except Exception as e:
        crops[page.id] = {}
        print("crop warn:", repr(e))

slides = collect_slides(p, crops)
print("slides:", len(slides), "total:", total_duration(slides), "->", format_timecode(total_duration(slides)))
export_script_txt(slides, "guion_video_test.txt")
print("txt OK")
paths = export_slides(slides, "diapositivas_test")
print("png OK:", len(paths), paths[:2])
