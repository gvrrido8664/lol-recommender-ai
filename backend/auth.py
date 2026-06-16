from fastapi import Header, HTTPException, Depends
from backend.config import validar_token


async def verificar_token(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido (Authorization: Bearer <token>)")
    token = authorization.removeprefix("Bearer ")
    if not validar_token(token):
        raise HTTPException(status_code=401, detail="Token invalido")
    return token
