import os
import zipfile
import subprocess
import sys

# El ID de tu archivo datos_iniciales.zip en Google Drive
FILE_ID = "1Cai56Tqwj0lPzipKg-sKp4vP6xZw2i6Y"
DESTINO_ZIP = "datos_iniciales.zip"

def instalar_dependencias():
    print("📦 Paso 1: Instalando dependencias del sistema...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        # Asegurarnos de que gdown esté instalado para el siguiente paso
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown"])
    except Exception as e:
        print(f"❌ Error instalando dependencias: {e}")
        sys.exit(1)

def descargar_datos():
    print("\n☁️  Paso 2: Descargando base de datos y modelo IA desde Google Drive (~150MB+)...")
    try:
        # Ejecutamos gdown como un comando de terminal independiente
        # Esto evita problemas de importación en tiempo real y gestiona mejor la red
        comando = [sys.executable, "-m", "gdown", "--id", FILE_ID, "-O", DESTINO_ZIP]
        subprocess.check_call(comando)
    except Exception as e:
        print(f"❌ Error al descargar con gdown: {e}")
        sys.exit(1)

def extraer_datos():
    print("\n📂 Paso 3: Extrayendo archivos...")
    if not os.path.exists(DESTINO_ZIP):
        print("❌ No se encontró el archivo ZIP.")
        return

    try:
        with zipfile.ZipFile(DESTINO_ZIP, 'r') as zip_ref:
            zip_ref.extractall(".") # Extrae en la carpeta actual
        print("✅ Extracción completada.")
        
        # Limpieza: Borramos el ZIP para no ocupar espacio doble
        os.remove(DESTINO_ZIP)
        print("🧹 Archivo temporal eliminado.")
    except Exception as e:
        print(f"❌ Error al descomprimir: {e}")

if __name__ == "__main__":
    print("="*50)
    print("🚀 INICIANDO SETUP AUTOMÁTICO - LoL Recommender")
    print("="*50)
    
    instalar_dependencias()
    descargar_datos()
    extraer_datos()
    
    print("\n" + "="*50)
    print("🎉 ¡TODO LISTO! El entorno está preparado.")
    print("💻 Ya puedes ejecutar: python app.py")
    print("="*50)