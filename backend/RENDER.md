"""
Script de deploy para Render (Web Service).

Configuracion en Render dashboard:
  - Build Command:   pip install -r backend/requirements.txt
  - Start Command:   cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
  - Root Directory:  (dejar vacio, es la raiz del repo)

Variables de entorno requeridas en Render:
  - DATABASE_URL    = postgresql://...
  - RIOT_API_KEY    = RGAPI-...
  - APP_TOKEN       = (token secreto que usara el cliente de escritorio)
  - PORT            = (Render lo inyecta automaticamente)
"""
