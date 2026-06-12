import webview
import threading
import subprocess
import uvicorn
import time
import os
import sys

def run_backend():
    """Ejecuta el servidor FastAPI en un hilo paralelo."""
    # Deshabilitamos logs para que no ensucie la consola del lanzador
    uvicorn.run("api:app", host="127.0.0.1", port=8000, log_level="warning")

def start_desktop():
    print("Iniciando Vite (Frontend)...")
    # Iniciamos el servidor de desarrollo de Vite
    frontend_process = subprocess.Popen(
        "npm run dev",
        cwd=os.path.join(os.path.dirname(__file__), "frontend"),
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    print("Iniciando FastAPI (Backend)...")
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()

    # Damos tiempo a Vite para compilar y levantar el puerto 5173
    print("Esperando a que los servidores arranquen (3 segundos)...")
    time.sleep(3)

    print("Abriendo aplicación de escritorio nativa...")
    # Creamos la ventana nativa apuntando a localhost:5173
    window = webview.create_window(
        title='LoL Esports Analytics', 
        url='http://localhost:5173', 
        width=1366, 
        height=800,
        resizable=True,
        min_size=(1024, 768),
        background_color='#05080f'  # Mismo color de fondo de la app web
    )
    
    # Iniciamos el bucle nativo de la UI. 
    # Esto bloquea la ejecución hasta que cierras la ventana.
    webview.start(debug=False)

    print("Cerrando aplicación y limpiando procesos...")
    # Al cerrar la ventana, matamos a Vite
    subprocess.call(['taskkill', '/F', '/T', '/PID', str(frontend_process.pid)])
    sys.exit(0)

if __name__ == '__main__':
    start_desktop()
