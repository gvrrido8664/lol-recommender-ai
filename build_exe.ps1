# ==========================================
# BUILD - LoL Recommender v1.0
# ==========================================
# Ejecutar en PowerShell con:
#   .\build_exe.ps1
#
# Requisito: pip install pyinstaller
#
# Salida: distribucion\LoL_Recommender_v1.0.exe
# ==========================================

$ErrorActionPreference = "Stop"

$Nombre = "LoL_Recommender_v1.0"
$DistDir = "distribucion"
$DataDir = "data"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  EMPAQUETANDO $Nombre" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

# ---------- Verificar dependencias ----------
Write-Host "[1/4] Verificando dependencias..." -ForegroundColor Yellow
$deps = @("requests", "sklearn", "pandas", "numpy", "PIL", "joblib", "PySide6")
foreach ($dep in $deps) {
    try { python -c "import $dep" 2>$null } catch {
        Write-Host "  Instalando $dep..." -ForegroundColor Yellow
        pip install $dep
    }
}
Write-Host "  OK" -ForegroundColor Green

# ---------- Verificar archivos ----------
Write-Host "[2/4] Verificando datos..." -ForegroundColor Yellow
$archivos = @(
    "$DataDir/champion_data.json", "$DataDir/item_data.json",
    "$DataDir/rune_data.json", "$DataDir/summoner_data.json",
    "$DataDir/modelo_1v1.pkl", "$DataDir/lol_data.db"
)
foreach ($a in $archivos) {
    if (-not (Test-Path $a)) { Write-Host "  FALTA: $a" -ForegroundColor Red }
}
Write-Host "  OK" -ForegroundColor Green

# ---------- Build ----------
Write-Host "[3/4] Compilando .exe..." -ForegroundColor Yellow

if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }

python -m PyInstaller --onefile `
    --name $Nombre `
    --windowed `
    --distpath $DistDir `
    --workpath "build_temp" `
    --add-data "$DataDir/champion_data.json;$DataDir" `
    --add-data "$DataDir/item_data.json;$DataDir" `
    --add-data "$DataDir/rune_data.json;$DataDir" `
    --add-data "$DataDir/summoner_data.json;$DataDir" `
    --add-data "$DataDir/modelo_1v1.pkl;$DataDir" `
    --add-data "$DataDir/lol_data.db;$DataDir" `
    --add-data "assets\campeones.json;assets" `
    --hidden-import sklearn.ensemble `
    --hidden-import sklearn.tree `
    --hidden-import sklearn.neighbors `
    --hidden-import sklearn.preprocessing `
    --hidden-import joblib `
    --hidden-import pandas `
    --hidden-import PIL._imaging `
    --hidden-import urllib3 `
    --collect-all PySide6 `
    app.py

if ($LASTEXITCODE -ne 0) { Write-Host "ERROR" -ForegroundColor Red; exit 1 }

# ---------- Limpiar ----------
Write-Host "[4/4] Limpiando..." -ForegroundColor Yellow
if (Test-Path "build_temp") { Remove-Item -Recurse -Force "build_temp" }
Remove-Item "*.spec" -Force -ErrorAction SilentlyContinue

Write-Host "======================================" -ForegroundColor Green
Write-Host "  LISTO: $DistDir\$Nombre.exe" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""
Write-Host "PARA COMPARTIR:" -ForegroundColor Cyan
Write-Host "  Envia la carpeta $DistDir al usuario final."
Write-Host "  No necesita Python ni nada mas."
Write-Host ""
Write-Host "LIMITACIONES:" -ForegroundColor Yellow
Write-Host "  - Pesa ~200 MB (PySide6 + sklearn incluidos)"
Write-Host "  - Windows Defender puede dar falso positivo"
Write-Host "  - No se actualiza solo (hay que redistribuir)"
Write-Host "  - El radar en vivo requiere tener LoL abierto"
Write-Host "  - Solo Windows (PyInstaller)"
