import os
import zipfile
import subprocess
import sys


FILE_ID = "1Cai56Tqwj0lPzipKg-sKp4vP6xZw2i6Y"
FILE_ID_BACKUP = "1Cai56Tqwj0lPzipKg-sKp4vP6xZw2i6Y"
DESTINO_ZIP = "datos_iniciales.zip"


def _log(msg, callback=None):
    if callback:
        callback(msg)
    else:
        print(msg)


def instalar_dependencias(log_callback=None, progress_callback=None):
    _log("Paso 1: Instalando dependencias del sistema...", log_callback)
    if progress_callback:
        progress_callback(0)
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if progress_callback:
            progress_callback(100)
        _log("Dependencias instaladas correctamente.", log_callback)
        return True
    except Exception as e:
        _log(f"Error instalando dependencias: {e}", log_callback)
        return False


def descargar_datos(log_callback=None, progress_callback=None):
    _log("Paso 2: Descargando base de datos y modelo IA...", log_callback)
    if progress_callback:
        progress_callback(0)

    sources = [
        ("Google Drive (principal)", FILE_ID),
        ("Google Drive (alternativo)", FILE_ID_BACKUP),
    ]

    for label, file_id in sources:
        _log(f"Intentando descarga desde: {label}", log_callback)
        try:
            comando = [sys.executable, "-m", "gdown", "--id", file_id, "-O", DESTINO_ZIP]
            subprocess.check_call(comando)
            if os.path.exists(DESTINO_ZIP) and os.path.getsize(DESTINO_ZIP) > 1024:
                if progress_callback:
                    progress_callback(100)
                _log("Descarga completada.", log_callback)
                return True
        except Exception as e:
            _log(f"Fallo con {label}: {e}", log_callback)

    _log("Todas las fuentes de descarga fallaron.", log_callback)
    return False


def extraer_datos(log_callback=None, progress_callback=None):
    _log("Paso 3: Extrayendo archivos...", log_callback)
    if not os.path.exists(DESTINO_ZIP):
        _log("No se encontro el archivo ZIP.", log_callback)
        return False

    try:
        if progress_callback:
            progress_callback(0)
        with zipfile.ZipFile(DESTINO_ZIP, "r") as zip_ref:
            zip_ref.extractall(".")
        if progress_callback:
            progress_callback(100)
        _log("Extraccion completada.", log_callback)

        os.remove(DESTINO_ZIP)
        _log("Archivo temporal eliminado.", log_callback)

        from src.db_manager import DATA_DIR
        modelo_path = os.path.join(DATA_DIR, "modelo_ia.pkl")
        if os.path.exists(modelo_path):
            _log("Base de datos verificada.", log_callback)
        else:
            _log("AVISO: No se encontro modelo_ia.pkl. Los modelos IA no se cargaron.", log_callback)
        return True
    except Exception as e:
        _log(f"Error al descomprimir: {e}", log_callback)
        return False


def verificar_datos_iniciales():
    from src.db_manager import DATA_DIR
    modelo_path = os.path.join(DATA_DIR, "modelo_ia.pkl")
    tags_path = os.path.join(DATA_DIR, "tags_campeones.json")
    return os.path.exists(modelo_path) and os.path.exists(tags_path)


if __name__ == "__main__":
    if not verificar_datos_iniciales():
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            print("=" * 50)
            print("INICIANDO SETUP AUTOMATICO - LoL Recommender")
            print("=" * 50)
            ok1 = instalar_dependencias()
            if not ok1: sys.exit(1)
            ok2 = descargar_datos()
            if not ok2: sys.exit(1)
            ok3 = extraer_datos()
            if not ok3: sys.exit(1)
            print("\n" + "=" * 50)
            print("TODO LISTO! El entorno esta preparado.")
            print("Ya puedes ejecutar: python app.py")
            print("=" * 50)
        else:
            app = QApplication(sys.argv)
            app.setApplicationName("NEXUS Setup")
            from src.setup_wizard import SetupWizard
            wizard = SetupWizard()
            wizard.exec()
            if wizard.success:
                sys.exit(0)
            else:
                sys.exit(1)
    else:
        print("Los datos iniciales ya existen. No es necesario ejecutar setup.")
        print("Para rehacer la configuracion, borra la carpeta data/ y vuelve a ejecutar.")
