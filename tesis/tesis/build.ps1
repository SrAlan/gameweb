# Compila tesis.md + capitulos/*.md -> tesis.docx usando Pandoc
param([switch]$Open)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$chapters = Get-ChildItem "capitulos\*.md" | Sort-Object Name | ForEach-Object { $_.FullName }

# Descarga el estilo APA si no existe
$cslArgs = @()
if (-not (Test-Path "apa.csl")) {
    try {
        Invoke-WebRequest "https://raw.githubusercontent.com/citation-style-language/styles/master/apa.csl" -OutFile "apa.csl" -TimeoutSec 30 -ErrorAction Stop
    } catch {
        Write-Host "Aviso: no se pudo descargar apa.csl, se usara el estilo por defecto de Pandoc." -ForegroundColor Yellow
    }
}
if (Test-Path "apa.csl") { $cslArgs = @("--csl=apa.csl") }

pandoc "tesis.md" @chapters `
  --from markdown+pipe_tables+citations `
  --citeproc `
  --bibliography=referencias.bib `
  @cslArgs `
  --toc --toc-depth=3 `
  -o "tesis.docx"

if ($LASTEXITCODE -eq 0) {
    Write-Host "OK -> tesis.docx generado correctamente." -ForegroundColor Green
    if ($Open) { Invoke-Item "tesis.docx" }
} else {
    Write-Host "ERROR: Pandoc devolvio el codigo $LASTEXITCODE" -ForegroundColor Red
}
