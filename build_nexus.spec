# -*- mode: python ; coding: utf-8 -*-
# Spec de PyInstaller para NEXUS. Optimizado para reducir falsos positivos de
# antivirus: modo onedir (no onefile), SIN UPX, con icono y metadata de version.
# Build:  pyinstaller build_nexus.spec   (o usar build_exe.ps1)
#
# OPTIMIZACION: solo collect_all para PySide6 (necesita DLLs/Qt plugins/binarios).
# numpy, pandas, scipy y sklearn usan hooks estandar de PyInstaller (ya incluidos
# en pyinstaller-hooks-contrib).  Esto evita el analisis recursivo de ~10.000
# modulos de tests y reduce el build de 6 min a ~2-3 min.
import os
import glob
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Datos a empaquetar: en data/ van modelos (.pkl), tags y json. Se EXCLUYEN los
# SQLite (*.db) porque la app usa PostgreSQL (no se necesitan y pesan ~18MB).
# De assets/ solo los .json: las imagenes son cache que se baja a %APPDATA% en runtime.
_datas = []
for _f in glob.glob("data/*"):
    if os.path.isfile(_f) and not _f.endswith(".db"):
        _datas.append((_f, "data"))
for _f in glob.glob("assets/*.json"):
    _datas.append((_f, "assets"))

# Secretos cifrados (API_KEY, DATABASE_URL). Generado por scripts/cifrar_secretos.py
# antes del build. Va a la raiz del bundle (se lee desde sys._MEIPASS en runtime).
# Cifrado con Fernet -> seguro incluirlo en el bundle (no es texto plano).
if os.path.isfile("secretos.bin"):
    _datas.append(("secretos.bin", "."))

# Solo PySide6 necesita collect_all (DLLs, shiboken, Qt plugins, QML, translations).
# numpy, pandas, scipy, sklearn -> hooks estandar (pyinstaller-hooks-contrib).
_binaries, _collected_datas, _hidden = [], [], []
for _pkg in ("PySide6",):
    try:
        b, d, h = collect_all(_pkg)
        _binaries += b; _collected_datas += d; _hidden += h
    except Exception:
        pass

hiddenimports = list(set(_hidden + [
    "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
    "psycopg2", "psycopg2.pool", "psycopg2.extras", "psycopg2.errors",
    "joblib",
    "sklearn.ensemble", "sklearn.ensemble._forest",
    "sklearn.tree", "sklearn.tree._tree",
    "sklearn.preprocessing", "sklearn.preprocessing._label",
    "sklearn.utils._typedefs",
    "sklearn.neighbors", "sklearn.linear_model",
    "sklearn.model_selection", "sklearn.feature_extraction",
    "pypresence", "requests", "urllib3",
    "cryptography", "cryptography.fernet",
    "cryptography.hazmat.primitives.kdf.pbkdf2",
    "cryptography.hazmat.primitives.hashes",
]))

_icon = "icono_app.ico" if os.path.isfile("icono_app.ico") else None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=_binaries,
    datas=_datas + _collected_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', '_tkinter', 'matplotlib', 'PyQt5', 'PyQt6', 'PySide6.QtQml', 'PySide6.QtQuick'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NEXUS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # CRITICO: UPX dispara antivirus -> desactivado
    console=False,        # GUI pura (--windowed)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,            # tambien aqui sin UPX
    upx_exclude=[],
    name='NEXUS',
)
