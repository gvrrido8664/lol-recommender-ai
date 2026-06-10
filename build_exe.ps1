# ==========================================
# BUILD - NEXUS v2.0
# ==========================================
# Uso: .\build_exe.ps1
#
# Requisito: pip install pyinstaller
#
# Salida: build_onedir\NEXUS\  (carpeta con todo)
#         installer_output\NEXUS_Setup_v2.0.exe  (si Inno Setup esta instalado)
# ==========================================

$ErrorActionPreference = "Stop"
$Nombre = "NEXUS"
$Version = "2.0"
$WorkDir = "build_temp"
$OutDir = "build_onedir"
$DataDir = "data"
$PythonExe = "venv\Scripts\python.exe"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  EMPAQUETANDO $Nombre v$Version" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

# ---------- 1. Verificar dependencias ----------
Write-Host "[1/5] Verificando dependencias..." -ForegroundColor Yellow
$deps = @("requests", "sklearn", "pandas", "numpy", "PIL", "joblib", "PySide6")
foreach ($dep in $deps) {
    try { & $PythonExe -c "import $dep" 2>$null } catch {
        Write-Host "  Instalando $dep..." -ForegroundColor Yellow
        & $PythonExe -m pip install $dep
    }
}
Write-Host "  OK" -ForegroundColor Green

# ---------- 2. Verificar archivos ----------
Write-Host "[2/5] Verificando datos..." -ForegroundColor Yellow
$archivos = @(
    "$DataDir/champion_data.json", "$DataDir/item_data.json",
    "$DataDir/rune_data.json", "$DataDir/summoner_data.json",
    "$DataDir/modelo_1v1.pkl", "$DataDir/lol_data.db"
)
foreach ($a in $archivos) {
    if (-not (Test-Path $a)) { Write-Host "  FALTA: $a" -ForegroundColor Red }
}
Write-Host "  OK" -ForegroundColor Green

# ---------- 3. Limpiar builds anteriores ----------
Write-Host "[3/5] Limpiando builds anteriores..." -ForegroundColor Yellow
if (Test-Path $OutDir) { Remove-Item -Recurse -Force $OutDir }
if (Test-Path $WorkDir) { Remove-Item -Recurse -Force $WorkDir }
Remove-Item "*.spec" -Force -ErrorAction SilentlyContinue
Write-Host "  OK" -ForegroundColor Green

# ---------- 4. Build (onedir) ----------
Write-Host "[4/5] Compilando con PyInstaller (--onedir)..." -ForegroundColor Yellow

& $PythonExe -m PyInstaller --onedir `
    --name $Nombre `
    --windowed `
    --icon "$PSScriptRoot\icono_app.ico" `
    --distpath $OutDir `
    --workpath $WorkDir `
    --add-data "$DataDir;data" `
    --add-data "icono_app.ico;." `
    --add-data "assets\campeones.json;assets" `
    --hidden-import sklearn.ensemble `
    --hidden-import sklearn.tree `
    --hidden-import sklearn.neighbors `
    --hidden-import sklearn.preprocessing `
    --hidden-import joblib `
    --hidden-import pandas `
    --hidden-import PIL._imaging `
    --hidden-import urllib3 `
    --hidden-import PySide6.QtWidgets `
    --hidden-import PySide6.QtGui `
    --hidden-import PySide6.QtCore `
    --exclude-module PySide6.Qt3DAnimation `
    --exclude-module PySide6.Qt3DCore `
    --exclude-module PySide6.Qt3DExtras `
    --exclude-module PySide6.Qt3DInput `
    --exclude-module PySide6.Qt3DLogic `
    --exclude-module PySide6.Qt3DRender `
    --exclude-module PySide6.QtCharts `
    --exclude-module PySide6.QtDataVisualization `
    --exclude-module PySide6.QtDesigner `
    --exclude-module PySide6.QtHelp `
    --exclude-module PySide6.QtHttpServer `
    --exclude-module PySide6.QtLocation `
    --exclude-module PySide6.QtMultimedia `
    --exclude-module PySide6.QtMultimediaWidgets `
    --exclude-module PySide6.QtNetworkAuth `
    --exclude-module PySide6.QtNfc `
    --exclude-module PySide6.QtPositioning `
    --exclude-module PySide6.QtQuick `
    --exclude-module PySide6.QtQuick3D `
    --exclude-module PySide6.QtQuickControls2 `
    --exclude-module PySide6.QtQuickTest `
    --exclude-module PySide6.QtQuickWidgets `
    --exclude-module PySide6.QtRemoteObjects `
    --exclude-module PySide6.QtScxml `
    --exclude-module PySide6.QtSensors `
    --exclude-module PySide6.QtSerialBus `
    --exclude-module PySide6.QtSerialPort `
    --exclude-module PySide6.QtSpatialAudio `
    --exclude-module PySide6.QtStateMachine `
    --exclude-module PySide6.QtTextToSpeech `
    --exclude-module PySide6.QtUiTools `
    --exclude-module PySide6.QtWebChannel `
    --exclude-module PySide6.QtWebEngineCore `
    --exclude-module PySide6.QtWebEngineQuick `
    --exclude-module PySide6.QtWebEngineWidgets `
    --exclude-module PySide6.QtWebSockets `
    --exclude-module PySide6.QtWebView `
    app.py

if ($LASTEXITCODE -ne 0) { Write-Host "ERROR compilando" -ForegroundColor Red; exit 1 }

# Copiar asset y data dirs extra que PyInstaller no empaqueta bien
$AppDir = "$OutDir\$Nombre"
if (Test-Path $AppDir) {
    # Copiar assets completos (iconos se descargan al vuelo en app.py)
    if (-not (Test-Path "$AppDir\assets")) {
        New-Item -ItemType Directory -Path "$AppDir\assets" -Force | Out-Null
    }
    # Limpiar .spec
    Remove-Item "*.spec" -Force -ErrorAction SilentlyContinue

    # ---- POST-PROCESSING: eliminar bloat de PySide6 ----
    $PySideDir = "$AppDir\_internal\PySide6"

    # 1. QML (25 MB) - no lo usamos
    if (Test-Path "$PySideDir\qml") {
        Remove-Item -Recurse -Force "$PySideDir\qml"
        Write-Host "  Eliminado: qml\"
    }

    # 2. WebEngine resources (101 MB) - no lo usamos
    if (Test-Path "$PySideDir\resources") {
        Remove-Item -Recurse -Force "$PySideDir\resources"
        Write-Host "  Eliminado: resources\ (WebEngine)"
    }

    # 3. Traducciones: solo mantener es y en
    $TransDir = "$PySideDir\translations"
    if (Test-Path $TransDir) {
        Get-ChildItem $TransDir -Filter "*.qm" | ForEach-Object {
            $keep = $_.Name -match '_es\.qm$|_en\.qm$'
            if (-not $keep) {
                Remove-Item $_.FullName -Force
            }
        }
        Write-Host "  Traducciones limpiadas (solo es/en)"
    }

    # 4. Metatypes (14 MB) - solo para IDE, no para runtime
    if (Test-Path "$PySideDir\metatypes") {
        Remove-Item -Recurse -Force "$PySideDir\metatypes"
        Write-Host "  Eliminado: metatypes\"
    }

    # 5. .pyi stubs (5 MB) - solo para IDE, no para runtime
    Get-ChildItem "$PySideDir" -Filter "*.pyi" -Recurse | Remove-Item -Force
    Write-Host "  Eliminados: .pyi stubs"

    # 6. Modulos .pyd que no necesitamos (si alguno quedo)
    $modulosInnecesarios = @(
        "Qt3DAnimation", "Qt3DCore", "Qt3DExtras", "Qt3DInput", "Qt3DLogic", "Qt3DRender",
        "QtBluetooth", "QtCharts", "QtDataVisualization", "QtDesigner",
        "QtGraphs", "QtGraphsWidgets",
        "QtHelp", "QtHttpServer", "QtLocation",
        "QtMultimedia", "QtMultimediaWidgets",
        "QtNetworkAuth", "QtNfc",
        "QtPdf", "QtPdfWidgets",
        "QtPositioning",
        "QtQuick", "QtQuick3D", "QtQuickControls2", "QtQuickTest", "QtQuickWidgets",
        "QtRemoteObjects", "QtScxml", "QtSensors",
        "QtSerialBus", "QtSerialPort", "QtSpatialAudio",
        "QtStateMachine", "QtTextToSpeech", "QtUiTools",
        "QtWebChannel", "QtWebEngineCore", "QtWebEngineQuick", "QtWebEngineWidgets",
        "QtWebSockets", "QtWebView"
    )
    foreach ($mod in $modulosInnecesarios) {
        $pydPath = "$PySideDir\$mod.pyd"
        if (Test-Path $pydPath) { Remove-Item $pydPath -Force }
    }
    Write-Host "  Modulos .pyd innecesarios eliminados"

    # 7. include/ (1 MB) - headers C, no para runtime
    if (Test-Path "$PySideDir\include") {
        Remove-Item -Recurse -Force "$PySideDir\include"
        Write-Host "  Eliminado: include\"
    }

    Write-Host "  Post-processing completado" -ForegroundColor Green
}

Write-Host "  LISTO: $AppDir" -ForegroundColor Green

# ---------- 5. Instalador con Inno Setup (si esta disponible) ----------
Write-Host "[5/5] Generando instalador..." -ForegroundColor Yellow

$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) {
    & $iscc installer.iss
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Instalador creado en installer_output\" -ForegroundColor Green
    } else {
        Write-Host "  Error al compilar instalador" -ForegroundColor Red
    }
} else {
    Write-Host "  Inno Setup no instalado. Salteando instalador." -ForegroundColor Yellow
    Write-Host "  Descargalo: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    Write-Host "  Luego ejecuta: ISCC.exe installer.iss" -ForegroundColor Yellow
}

# ---------- Fin ----------
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  BUILD COMPLETADO" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "DISTRIBUIR:" -ForegroundColor Green
Write-Host "  1. Opcion A: Comprimir $AppDir en .zip y compartir" -ForegroundColor Green
Write-Host "  2. Opcion B: Ejecutar ISCC.exe installer.iss para crear .exe instalador" -ForegroundColor Green
Write-Host ""
Write-Host "NOTA: El modo --onedir evita falsos positivos del antivirus" -ForegroundColor Yellow
Write-Host "      porque no extrae nada en memoria (a diferencia de --onefile)" -ForegroundColor Yellow
