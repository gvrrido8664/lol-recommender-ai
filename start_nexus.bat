@echo off
echo Iniciando NEXUS (League Recommender AI)
echo =========================================

echo Iniciando Servidor Backend (Python)...
start "NEXUS Backend" cmd /k ".\venv\Scripts\python.exe api.py"

echo Iniciando Aplicacion Frontend (React)...
start "NEXUS Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ¡Servidores lanzados en ventanas separadas!
echo La pagina se encuentra en http://localhost:5173
echo.
pause
