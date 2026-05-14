import os
import zipfile
import subprocess
import sys


FILE_ID = "1Cai56Tqwj0lPzipKg-sKp4vP6xZw2i6Y"
DESTINO_ZIP = "datos_iniciales.zip"


def instalar_dependencias():
    print("📦 Paso 1: Instalando dependencias del sistema...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencias instaladas correctamente.")
    except Exception as e:
        print(f"❌ Error instalando dependencias: {e}")
        sys.exit(1)


def descargar_datos():
    print("\n☁️  Paso 2: Descargando base de datos y modelo IA desde Google Drive...")
    try:
        comando = [sys.executable, "-m", "gdown", "--id", FILE_ID, "-O", DESTINO_ZIP]
        subprocess.check_call(comando)
        print("✅ Descarga completada.")
    except Exception as e:
        print(f"❌ Error al descargar con gdown: {e}")
        sys.exit(1)


def extraer_datos():
    print("\n📂 Paso 3: Extrayendo archivos...")
    if not os.path.exists(DESTINO_ZIP):
        print("❌ No se encontró el archivo ZIP.")
        sys.exit(1)

    try:
        with zipfile.ZipFile(DESTINO_ZIP, "r") as zip_ref:
            zip_ref.extractall(".")
        print("✅ Extracción completada.")

        os.remove(DESTINO_ZIP)
        print("🧹 Archivo temporal eliminado.")
    except Exception as e:
        print(f"❌ Error al descomprimir: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 50)
    print("🚀 INICIANDO SETUP AUTOMÁTICO - LoL Recommender")
    print("=" * 50)

    instalar_dependencias()
    descargar_datos()
    extraer_datos()

    print("\n" + "=" * 50)
    print("🎉 ¡TODO LISTO! El entorno está preparado.")
    print("💻 Ya puedes ejecutar: python app.py")
    print("=" * 50)