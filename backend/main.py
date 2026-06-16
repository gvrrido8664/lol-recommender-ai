"""
NEXUS Backend Proxy — FastAPI

Guarda API_KEY y DATABASE_URL server-side.
El cliente de escritorio habla con este backend por HTTPS usando un token de app.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import PORT
from backend.db import inicializar_db
from backend.routers import cache, drafts, emocional, lp, riot_proxy


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        inicializar_db()
        print("[backend] DB inicializada")
    except Exception as e:
        print(f"[backend] ⚠ Error inicializando DB: {e}")
    yield


app = FastAPI(
    title="NEXUS Backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(drafts.router)
app.include_router(lp.router)
app.include_router(emocional.router)
app.include_router(cache.router)
app.include_router(riot_proxy.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=PORT, reload=True)
