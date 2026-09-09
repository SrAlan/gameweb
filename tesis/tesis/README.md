# Tesis - Desafios de Accesibilidad Turistica en el Templo San Buenaventura de Yaguaron (2026)
Universidad Americana - Licenciatura en Gestion de Hoteleria y Turismo.
Autores: Romina Elizabeth Rolon Villalba - Jessica Jazmin Benitez Quinonez. Tutora: Prof. Lic. Fabiola.

## Estructura
tesis.md (portada/resumen/introduccion) + capitulos/*.md -> Pandoc (build.ps1) -> tesis.docx
fuentes/ = PDFs y normativa descargada; notas/ = notas de trabajo; referencias.bib = bibliografia BibTeX (APA via Pandoc).

## Compilar
.\build.ps1            # genera tesis.docx
.\build.ps1 -Open      # genera y abre en Word

## Citas
En el texto: [@ley4934] o [@omt_turismo_accesible, p. 15]. La bibliografia se genera automaticamente al final.

## Git + IA
git diff; git add .; git commit -m "Revision del marco teorico"
Instruir a la IA por partes, p. ej.: "Lee capitulos/capitulo2.md y fuentes/marco_teorico.md. Propón cambios, pero no modifiques las citas."
El archivo tesis.docx compilado NO se versiona.
