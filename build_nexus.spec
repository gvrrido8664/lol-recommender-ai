# -*- mode: python ; coding: utf-8 -*-
# Spec de PyInstaller para NEXUS. Optimizado para reducir falsos positivos de
# antivirus: modo onedir (no onefile), SIN UPX, con icono y metadata de version.
# Build:  pyinstaller build_nexus.spec   (o usar build_exe.ps1)
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Datos a empaquetar: solo los que existen en el repo (data = modelos/tags; assets = estaticos)
_datas = []
for _d in ("data", "assets"):
    if os.path.isdir(_d):
        _datas.append((_d, _d))

# collect_all para paquetes con datos/binarios que PyInstaller no detecta solo
_binaries, _collected_datas, _hidden = [], [], []
for _pkg in ("PySide6", "numpy", "pandas", "scipy", "sklearn"):
    try:
        b, d, h = collect_all(_pkg)
        _binaries += b; _collected_datas += d; _hidden += h
    except Exception:
        pass

hiddenimports = list(set(_hidden + [
    "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
    "psycopg2", "joblib",
    "sklearn.ensemble", "sklearn.tree", "sklearn.preprocessing", "sklearn.utils._typedefs",
    "pypresence", "requests", "urllib3",
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
    excludes=['tkinter', '_tkinter', 'matplotlib', 'PyQt5', 'PyQt6'],
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
